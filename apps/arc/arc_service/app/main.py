from fastapi import FastAPI, APIRouter, UploadFile, File, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import uuid4
from fastapi.responses import JSONResponse, FileResponse
import io
import os
import openai
import pdfplumber
from docx import Document
import logging
import re
from sqlalchemy.orm import Session
from .models import UserArcData
from .db import SessionLocal
import tiktoken
import jwt
from fastapi.middleware.cors import CORSMiddleware
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed

app = FastAPI(title="Career Ark (Arc) Service", description="API for Career Ark data extraction, deduplication, and application material generation.")
router = APIRouter(prefix="/api/arc")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

logger = logging.getLogger("arc_service")
logging.basicConfig(level=logging.INFO)

JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175,https://c5-frontend-pied.vercel.app").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# --- Models ---
class CVUploadResponse(BaseModel):
    taskId: str

class CVStatusResponse(BaseModel):
    status: str
    extractedDataSummary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class Role(BaseModel):
    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    successes: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    training: Optional[List[str]] = None

class ArcData(BaseModel):
    work_experience: Optional[List[Role]] = None
    education: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    # Add more fields as needed

class GenerateRequest(BaseModel):
    jobAdvert: str
    arcData: Dict[str, Any]

class GenerateResponse(BaseModel):
    cv: str
    coverLetter: str

class KeywordsRequest(BaseModel):
    jobDescription: str

class KeywordsResponse(BaseModel):
    keywords: list[str]

# --- In-memory stores for demo purposes ---
tasks = {}
user_arc_data = {}

# --- Deduplication & Merging Logic Stubs ---
def deduplicate_and_merge_work_experience(existing: list, new: list) -> list:
    """
    Deduplicate and merge work experience entries.
    Rules: Same company + similar role title + overlapping dates.
    TODO: Implement fuzzy/semantic matching and merging logic.
    """
    # Placeholder: naive append
    return (existing or []) + (new or [])

def deduplicate_and_merge_education(existing: list, new: list) -> list:
    """
    Deduplicate and merge education entries.
    Rules: Same institution + same degree + same field + overlapping dates.
    TODO: Implement fuzzy/semantic matching and merging logic.
    """
    return (existing or []) + (new or [])

def deduplicate_and_merge_skills(existing: list, new: list) -> list:
    """
    Deduplicate and merge skills by name/category.
    TODO: Implement case-insensitive and semantic deduplication.
    """
    return list(set((existing or []) + (new or [])))

def deduplicate_and_merge_projects(existing: list, new: list) -> list:
    """
    Deduplicate and merge projects by name/description/tech.
    TODO: Implement fuzzy/semantic matching and merging logic.
    """
    return (existing or []) + (new or [])

def deduplicate_and_merge_certifications(existing: list, new: list) -> list:
    """
    Deduplicate and merge certifications by credential ID or name/org.
    TODO: Implement matching and merging logic.
    """
    return (existing or []) + (new or [])

def deduplicate_and_merge_achievements(existing: list, new: list) -> list:
    """
    Deduplicate and merge achievements by semantic similarity within parent entity.
    TODO: Implement semantic deduplication.
    """
    return (existing or []) + (new or [])

# --- Helper: Merge ArcData ---
def merge_arc_data(existing: ArcData, new: ArcData) -> ArcData:
    """
    Merge new ArcData into existing ArcData, preserving all unique data.
    - If a field (e.g., work_experience, education, skills, etc.) already exists, keep the existing entry unless the new entry is unique.
    - Do not remove or overwrite existing data unless it is an exact duplicate.
    - Only add new, unique entries.
    - ArcData should only ever be deleted by an explicit admin or user delete function (not implemented here).
    """
    def dedup_list_of_dicts(existing_list, new_list, key_fields, bullet_fields=None):
        if not existing_list:
            existing_list = []
        if not new_list:
            new_list = []
        seen = set()
        result = []
        for item in existing_list + new_list:
            # Convert Pydantic models to dicts for hashing
            if hasattr(item, 'dict'):
                item_dict = item.dict()
            else:
                item_dict = item
            if isinstance(item_dict, dict):
                key = tuple(item_dict.get(f) for f in key_fields)
                # If bullet_fields are specified, include each bullet point in the key
                if bullet_fields:
                    for bullet_field in bullet_fields:
                        if bullet_field in item_dict and isinstance(item_dict[bullet_field], list):
                            for bullet in item_dict[bullet_field]:
                                bullet_key = key + (bullet,)
                                if bullet_key not in seen:
                                    seen.add(bullet_key)
                                    # Add a copy of the item with only this bullet
                                    item_copy = dict(item_dict)
                                    item_copy[bullet_field] = [bullet]
                                    result.append(item_copy)
                        else:
                            if key not in seen:
                                seen.add(key)
                                result.append(item_dict)
                else:
                    if key not in seen:
                        seen.add(key)
                        result.append(item_dict)
            else:
                if item_dict not in seen:
                    seen.add(item_dict)
                    result.append(item_dict)
        return result

    def merge_work_experience(existing_list, new_list):
        # Index existing jobs by (company, title, start_date, end_date)
        job_key = lambda job: (
            job.get("company"), job.get("title"), job.get("start_date"), job.get("end_date")
        )
        existing_jobs = {job_key(job): dict(job) for job in existing_list or []}
        for new_job in new_list or []:
            key = job_key(new_job)
            if key in existing_jobs:
                # Merge bullet points (successes)
                existing_successes = set(existing_jobs[key].get("successes", []) or [])
                new_successes = set(new_job.get("successes", []) or [])
                merged_successes = list(existing_successes.union(new_successes))
                existing_jobs[key]["successes"] = merged_successes
                # Optionally merge other fields (e.g., description, skills, training) if needed
            else:
                existing_jobs[key] = dict(new_job)
        return list(existing_jobs.values())

    return ArcData(
        work_experience=merge_work_experience(
            getattr(existing, 'work_experience', []),
            getattr(new, 'work_experience', [])
        ),
        education=dedup_list_of_dicts(
            getattr(existing, 'education', []),
            getattr(new, 'education', []),
            key_fields=["institution", "degree", "year"]
        ),
        skills=list(set((existing.skills or []) + (new.skills or []))),
        projects=dedup_list_of_dicts(
            getattr(existing, 'projects', []),
            getattr(new, 'projects', []),
            key_fields=["name", "description"]
        ),
        certifications=dedup_list_of_dicts(
            getattr(existing, 'certifications', []),
            getattr(new, 'certifications', []),
            key_fields=["name", "issuer", "year"]
        ),
        # Add more fields as needed
    )
# ArcData is only deleted by explicit admin/user request (not implemented here)

# --- Helper: Auth ---
def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id") or payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user_id")
        return user_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

def extract_text_from_pdf(file: UploadFile):
    with pdfplumber.open(file.file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    file.file.seek(0)
    return text

def extract_text_from_docx(file: UploadFile):
    doc = Document(file.file)
    text = "\n".join([para.text for para in doc.paragraphs])
    file.file.seek(0)
    return text

# --- Helper: Ensure List Fields in ArcData ---
def ensure_list_fields(data):
    # Fix work_experience[].skills and work_experience[].successes
    if "work_experience" in data and isinstance(data["work_experience"], list):
        for role in data["work_experience"]:
            for field in ["skills", "successes"]:
                if field in role and isinstance(role[field], str):
                    # Split on commas and strip whitespace
                    role[field] = [s.strip() for s in role[field].split(",") if s.strip()]
    return data

SECTION_HEADERS = [
    r"work experience", r"professional experience", r"employment history",
    r"education", r"academic background",
    r"skills", r"technical skills",
    r"projects", r"certifications", r"training"
]

section_header_regex = re.compile(rf"^({'|'.join(SECTION_HEADERS)})[:\s]*$", re.IGNORECASE | re.MULTILINE)

def split_cv_by_sections(text):
    # Find all section headers and their positions
    matches = list(section_header_regex.finditer(text))
    if not matches:
        return [("full", text)]
    sections = []
    for i, match in enumerate(matches):
        start = match.start()
        header = match.group(1).strip().lower()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        sections.append((header, section_text))
    return sections

def chunk_work_experience_section(section_text, max_chunk_chars=3000):
    # Split by job entries (simple heuristic: lines with years or company names)
    jobs = re.split(r"\n(?=\s*\S.*(\d{4}|company|employer|position|role))", section_text, flags=re.IGNORECASE)
    # Further chunk if needed
    chunks = []
    current = ""
    for job in jobs:
        if len(current) + len(job) > max_chunk_chars and current:
            chunks.append(current)
            current = job
        else:
            current += ("\n" if current else "") + job
    if current:
        chunks.append(current)
    return chunks

def count_tokens(text, model="gpt-3.5-turbo"):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

def chunk_texts_by_tokens(texts, max_tokens=4000, model="gpt-3.5-turbo"):
    """
    Group a list of texts (e.g., jobs or sections) into chunks not exceeding max_tokens.
    If a single text exceeds max_tokens, split it by paragraphs.
    """
    chunks = []
    current_chunk = []
    current_tokens = 0
    for text in texts:
        tokens = count_tokens(text, model)
        if tokens > max_tokens:
            # Split this text further by paragraphs
            paras = text.split("\n\n")
            para_chunks = chunk_texts_by_tokens(paras, max_tokens, model)
            chunks.extend(para_chunks)
            continue
        if current_tokens + tokens > max_tokens and current_chunk:
            chunks.append(current_chunk)
            current_chunk = [text]
            current_tokens = tokens
        else:
            current_chunk.append(text)
            current_tokens += tokens
    if current_chunk:
        chunks.append(current_chunk)
    return ["\n\n".join(chunk) for chunk in chunks]

def parse_cv_with_ai_chunk(text):
    # Use the existing parse_cv_with_ai logic, but for a single chunk
    # (Copy the body of parse_cv_with_ai here, but without token truncation logic)
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt_instructions = (
        "You are an expert CV parser. Extract all unique, detailed information from this CV text as a JSON object. "
        "Handle a wide variety of CV formats, layouts, and section names. "
        "Use UK English spelling and conventions throughout. "
        "All property names and string values must be enclosed in double quotes. Do not use single quotes or omit quotes. "
        "Return ONLY valid JSON, with no extra text, comments, or explanations.\n"
        "The JSON should have a 'work_experience' array (each item: company, title, start_date, end_date, description, successes, skills, training), "
        "an 'education' array (each item: institution, degree, year), 'skills' (array of strings), 'projects' (array of objects), and 'certifications' (array of objects).\n"
        "For each work experience, extract as much detail as possible, including ALL achievements, bullet points, and unique sentences.\n"
        "If the CV uses non-standard section names or order, do your best to map them to the correct fields.\n"
        "Do NOT summarise, merge, or omit ANY unique bullet point or achievement. If an item is unique, keep it as a separate bullet point, even if it is similar to others.\n\n"
        "CV Text:\n"
    )
    prompt = prompt_instructions + text
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1800,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        import json
        try:
            data = json.loads(response.choices[0].message.content)
            data = ensure_list_fields(data)
        except Exception as e:
            logger.error(f"AI parsing failed: {e}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            match = re.search(r'\{.*\}', response.choices[0].message.content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    data = ensure_list_fields(data)
                except Exception as e2:
                    logger.error(f"Fallback JSON parse also failed: {e2}")
                    try:
                        with open("ai_parse_error_output.txt", "w", encoding="utf-8") as f:
                            f.write(response.choices[0].message.content)
                        logger.error("Raw AI output saved to ai_parse_error_output.txt for debugging.")
                    except Exception as file_err:
                        logger.error(f"Failed to save raw AI output: {file_err}")
                    data = {}
            else:
                try:
                    with open("ai_parse_error_output.txt", "w", encoding="utf-8") as f:
                        f.write(response.choices[0].message.content)
                    logger.error("Raw AI output saved to ai_parse_error_output.txt for debugging.")
                except Exception as file_err:
                    logger.error(f"Failed to save raw AI output: {file_err}")
                data = {}
        for key in ["education", "projects", "certifications"]:
            if key in data and isinstance(data[key], list):
                new_list = []
                for entry in data[key]:
                    if isinstance(entry, str):
                        new_list.append({"description": entry})
                    else:
                        new_list.append(entry)
                data[key] = new_list
        return ArcData(**data)
    except Exception as e:
        logger.error(f"AI parsing failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {e}")

def parse_cv_with_ai(text: str) -> ArcData:
    sections = split_cv_by_sections(text)
    arc_datas = []
    with ThreadPoolExecutor() as executor:
        futures = []
        for header, section_text in sections:
            if header in ["work experience", "professional experience", "employment history"]:
                # Split work experience into jobs (by job entries)
                jobs = re.split(r"\n(?=\s*\S.*(\d{4}|company|employer|position|role))", section_text, flags=re.IGNORECASE)
                # Chunk jobs by tokens
                job_chunks = chunk_texts_by_tokens(jobs, max_tokens=4000)
                for chunk in job_chunks:
                    futures.append(executor.submit(parse_cv_with_ai_chunk, chunk))
            else:
                # For other sections, chunk if needed
                section_chunks = chunk_texts_by_tokens([section_text], max_tokens=4000)
                for chunk in section_chunks:
                    futures.append(executor.submit(parse_cv_with_ai_chunk, chunk))
        for future in as_completed(futures):
            arc_datas.append(future.result())
    # Merge all ArcData objects
    merged = arc_datas[0] if arc_datas else ArcData()
    for arc_data in arc_datas[1:]:
        merged = merge_arc_data(merged, arc_data)
    return merged

# --- Dependency: Database Session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoint: Upload CV ---
@router.post("/cv", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    task_id = str(uuid4())
    tasks[task_id] = {"status": "pending", "user_id": user_id}
    filename = file.filename.lower()
    try:
        if filename.endswith(".pdf"):
            text = extract_text_from_pdf(file)
        elif filename.endswith(".docx"):
            text = extract_text_from_docx(file)
        else:
            logger.error(f"Unsupported file type uploaded: {filename}")
            raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX are supported.")
        new_arc_data = parse_cv_with_ai(text)
    except Exception as e:
        logger.error(f"Error in /cv upload endpoint: {e}")
        tasks[task_id] = {"status": "failed", "user_id": user_id, "error": str(e)}
        raise
    # Deduplicate and merge with existing data from DB
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj:
        existing = ArcData(**db_obj.arc_data)
        merged = merge_arc_data(existing, new_arc_data)
        db_obj.arc_data = merged.dict()
    else:
        merged = new_arc_data
        db_obj = UserArcData(user_id=user_id, arc_data=merged.dict())
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    tasks[task_id] = {
        "status": "completed",
        "user_id": user_id,
        "extractedDataSummary": {"workExperienceCount": len(merged.work_experience or []), "skillsFound": len(merged.skills or [])}
    }
    return {"taskId": task_id}

# --- Endpoint: Poll CV Processing Status ---
@router.get("/cv/status/{taskId}", response_model=CVStatusResponse)
async def poll_cv_status(taskId: str, user_id: str = Depends(get_current_user)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": task["status"],
        "extractedDataSummary": task.get("extractedDataSummary"),
        "error": task.get("error")
    }

# --- Endpoint: Arc Data Management ---
@router.get("/data", response_model=ArcData)
async def get_arc_data(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj:
        return db_obj.arc_data
    return ArcData()

@router.put("/data", response_model=ArcData)
@router.post("/data", response_model=ArcData)
async def update_arc_data(data: ArcData = Body(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj:
        # Merge with existing data
        merged = merge_arc_data(ArcData(**db_obj.arc_data), data)
        db_obj.arc_data = merged.dict()
    else:
        merged = data
        db_obj = UserArcData(user_id=user_id, arc_data=merged.dict())
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return merged

# --- Endpoint: Generate Application Materials ---
@router.post("/generate", response_model=GenerateResponse)
async def generate_materials(req: GenerateRequest, user_id: str = Depends(get_current_user)):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = f"""
You are an expert CV and cover letter writer. Use UK English spelling and conventions throughout. Given the following job posting and candidate data, generate a highly detailed, tailored CV and a matching cover letter.

Instructions:
1. Always start from the full, detailed ArcData profile, preserving all unique experiences, achievements, skills, and details.
2. Be as detailed as possible. Include all relevant information, bullet points, and descriptions for each role, project, and achievement.
3. Do not omit or summarise unless information is clearly duplicated.
4. Customise the professional summary to highlight experiences, skills, and goals that match the job description. Use keywords from the job posting.
5. Align work experience: reorder bullet points to emphasise relevant duties and achievements, use similar language as the job ad, and quantify results where possible.
6. List all work experience in strict reverse chronological order, with the most recent position first.
7. Match the skills section to the job posting, removing unrelated skills.
8. Adjust job titles for clarity if needed.
9. Add relevant keywords from the job posting throughout the CV.
10. Highlight relevant certifications/training, moving them higher if important.
11. Emphasise achievements that align with the company's goals.
12. Mirror the company's language and culture cues.
13. Adjust the order of sections for maximum relevance.
14. Generate a targeted cover letter that matches the tailored CV.

Return ONLY a JSON object with two properties: "cv" (the tailored CV as a string) and "coverLetter" (the cover letter as a string). Do not return any other fields, explanations, or extra text. All property names and string values must be enclosed in double quotes.

Job Posting:
{req.jobAdvert[:4000]}

Candidate Data (ArcData):
{str(req.arcData)[:4000]}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        import json
        try:
            data = json.loads(response.choices[0].message.content)
            # Defensive: Ensure both 'cv' and 'coverLetter' are present and are strings
            if not (isinstance(data, dict) and isinstance(data.get("cv"), str) and isinstance(data.get("coverLetter"), str)):
                logger.error(f"AI CV/cover letter response missing required fields. Raw response: {response.choices[0].message.content}")
                raise HTTPException(status_code=500, detail="AI did not return the expected cv and coverLetter fields.")
        except Exception as e:
            logger.error(f"AI CV/cover letter JSON parse failed: {e}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            match = re.search(r'\{.*\}', response.choices[0].message.content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    if not (isinstance(data, dict) and isinstance(data.get("cv"), str) and isinstance(data.get("coverLetter"), str)):
                        logger.error(f"AI CV/cover letter response missing required fields (fallback). Raw response: {response.choices[0].message.content}")
                        raise HTTPException(status_code=500, detail="AI did not return the expected cv and coverLetter fields (fallback).")
                except Exception as e2:
                    logger.error(f"Fallback JSON parse also failed: {e2}")
                    raise HTTPException(status_code=500, detail="AI CV/cover letter generation failed: Could not parse response.")
            else:
                raise HTTPException(status_code=500, detail="AI CV/cover letter generation failed: No JSON object found in response.")
        return GenerateResponse(**data)
    except Exception as e:
        logger.error(f"AI CV/cover letter generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI CV/cover letter generation failed: {e}")

# --- Endpoint: Download Processed CV or Extracted Data ---
@router.get("/cv/download/{taskId}")
async def download_processed_cv(taskId: str, user_id: str = Depends(get_current_user)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    # TODO: Return actual processed file or data
    # For now, return a dummy text file
    dummy_content = f"Processed CV data for task {taskId}"
    return FileResponse(io.BytesIO(dummy_content.encode()), media_type="text/plain", filename=f"processed_cv_{taskId}.txt")

# --- Endpoint: List User's Uploaded CVs/Tasks ---
@router.get("/cv/tasks")
async def list_cv_tasks(user_id: str = Depends(get_current_user)):
    user_tasks = [ {"taskId": tid, **{k:v for k,v in t.items() if k != "user_id"}} for tid, t in tasks.items() if t["user_id"] == user_id ]
    return {"tasks": user_tasks}

# --- Endpoint: Delete a CV or Task ---
@router.delete("/cv/{taskId}")
async def delete_cv_task(taskId: str, user_id: str = Depends(get_current_user)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    del tasks[taskId]
    # TODO: Remove associated data from user_arc_data if needed
    return {"success": True}

# --- Endpoint: Extract Keywords from Job Description ---
@router.post("/ai/keywords", response_model=KeywordsResponse)
async def extract_keywords(req: KeywordsRequest, user_id: str = Depends(get_current_user)):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = (
        "Extract up to 20 of the most important recruiter-focused keywords from the following job description. "
        "Use UK English spelling and conventions throughout. "
        "Return ONLY a JSON object with a single property 'keywords', which is an array of keywords, and no extra text, comments, or explanations. "
        "Prioritise essential skills, technologies, certifications, and role-specific terms. "
        "Do not include generic words like 'job', 'candidate', or 'requirements'.\n\n"
        f"Job Description:\n{req.jobDescription[:4000]}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        import json
        try:
            data = json.loads(response.choices[0].message.content)
            keywords = data.get("keywords", [])
        except Exception as e:
            logger.error(f"Keyword extraction JSON parse failed: {e}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            # Fallback: try to extract JSON object from the response
            match = re.search(r'\{.*\}', response.choices[0].message.content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    keywords = data.get("keywords", [])
                except Exception as e2:
                    logger.error(f"Fallback JSON parse also failed: {e2}")
                    keywords = []
            else:
                keywords = []
        return KeywordsResponse(keywords=keywords)
    except Exception as e:
        logger.error(f"Keyword extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Keyword extraction failed: {e}")

# --- Health Check Endpoint ---
@router.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/health")
async def root_health():
    return {"status": "ok"}

# --- Error handler example ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

openai_api_key_startup = os.getenv("OPENAI_API_KEY")
if openai_api_key_startup:
    print("OPENAI_API_KEY at startup:", openai_api_key_startup[:6] + "..." + openai_api_key_startup[-4:])
else:
    print("OPENAI_API_KEY at startup: None")

# --- Career Ark Endpoints ---

# In-memory user data for demo
career_ark_data = {}

def get_user_ark(user_id):
    if user_id not in career_ark_data:
        career_ark_data[user_id] = {
            "work_experience": [],
            "education": [],
            "training": []
        }
    return career_ark_data[user_id]

@router.get("")
async def get_all_arc_data(user_id: str = Depends(get_current_user)):
    """Fetch all career data for the logged-in user."""
    return get_user_ark(user_id)

@router.post("/work_experience")
async def add_work_experience(entry: dict = Body(...), user_id: str = Depends(get_current_user)):
    ark = get_user_ark(user_id)
    entry = dict(entry)
    entry["id"] = str(uuid4())
    ark["work_experience"].append(entry)
    return entry

@router.post("/education")
async def add_education(entry: dict = Body(...), user_id: str = Depends(get_current_user)):
    ark = get_user_ark(user_id)
    entry = dict(entry)
    entry["id"] = str(uuid4())
    ark["education"].append(entry)
    return entry

@router.post("/training")
async def add_training(entry: dict = Body(...), user_id: str = Depends(get_current_user)):
    ark = get_user_ark(user_id)
    entry = dict(entry)
    entry["id"] = str(uuid4())
    ark["training"].append(entry)
    return entry

@router.patch("/work_experience/{id}")
async def update_work_experience(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user)):
    ark = get_user_ark(user_id)
    for entry in ark["work_experience"]:
        if entry["id"] == id:
            entry.update(update)
            return entry
    raise HTTPException(status_code=404, detail="Work experience not found")

@router.patch("/education/{id}")
async def update_education(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user)):
    ark = get_user_ark(user_id)
    for entry in ark["education"]:
        if entry["id"] == id:
            entry.update(update)
            return entry
    raise HTTPException(status_code=404, detail="Education not found")

@router.patch("/training/{id}")
async def update_training(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user)):
    ark = get_user_ark(user_id)
    for entry in ark["training"]:
        if entry["id"] == id:
            entry.update(update)
            return entry
    raise HTTPException(status_code=404, detail="Training not found")

@app.get("/debug/ai-parse-error")
def get_ai_parse_error_file():
    return FileResponse("ai_parse_error_output.txt", media_type="text/plain")

app.include_router(router) 