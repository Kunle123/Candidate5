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

app = FastAPI(title="Career Ark (Arc) Service", description="API for Career Ark data extraction, deduplication, and application material generation.")
router = APIRouter(prefix="/api/arc")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

logger = logging.getLogger("arc_service")
logging.basicConfig(level=logging.INFO)

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
    def dedup_list_of_dicts(existing_list, new_list, key_fields):
        if not existing_list:
            existing_list = []
        if not new_list:
            new_list = []
        seen = set()
        result = []
        for item in existing_list + new_list:
            if isinstance(item, dict):
                key = tuple(item.get(f) for f in key_fields)
            else:
                key = item
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    return ArcData(
        work_experience=dedup_list_of_dicts(
            getattr(existing, 'work_experience', []),
            getattr(new, 'work_experience', []),
            key_fields=["company", "title", "start_date", "end_date"]
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
    # Require Bearer token for authentication (reverted to original logic)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return "demo_user_id"

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

def parse_cv_with_ai(text: str) -> ArcData:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = (
        "Extract all unique, detailed information from this CV text as a JSON object. "
        "All property names and string values must be enclosed in double quotes. Do not use single quotes or omit quotes. "
        "Return ONLY valid JSON, with no extra text, comments, or explanations.\n"
        "The JSON should have a 'work_experience' array (each item: company, title, start_date, end_date, description, successes, skills, training), "
        "an 'education' array (each item: institution, degree, year), 'skills' (array of strings), 'projects' (array of objects), and 'certifications' (array of objects).\n"
        "Do NOT summarize or omit any unique information. If an item is unique, keep it.\n\n"
        "CV Text:\n" + text[:6000]  # Truncate to avoid context overflow
    )
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
        except Exception as e:
            logger.error(f"AI parsing failed: {e}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            # Fallback: try to extract JSON object from the response
            match = re.search(r'\{.*\}', response.choices[0].message.content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception as e2:
                    logger.error(f"Fallback JSON parse also failed: {e2}")
                    data = {}
            else:
                data = {}
        # Fallback: convert string entries in education, projects, certifications to objects
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

# --- Endpoint: Upload CV ---
@router.post("/cv", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
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
    # Deduplicate and merge with existing data
    existing = user_arc_data.get(user_id, ArcData())
    merged = merge_arc_data(existing, new_arc_data)
    user_arc_data[user_id] = merged
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
async def get_arc_data(user_id: str = Depends(get_current_user)):
    return user_arc_data.get(user_id, ArcData())

@router.put("/data", response_model=ArcData)
@router.post("/data", response_model=ArcData)
async def update_arc_data(data: ArcData = Body(...), user_id: str = Depends(get_current_user)):
    # Deduplicate and merge with existing data
    existing = user_arc_data.get(user_id, ArcData())
    merged = merge_arc_data(existing, data)
    user_arc_data[user_id] = merged
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
You are an expert CV and cover letter writer. Given the following job posting and candidate data, generate a highly detailed, tailored CV and a matching cover letter.

Instructions:
1. Always start from the full, detailed ArcData profile, preserving all unique experiences, achievements, skills, and details.
2. Be as detailed as possible. Include all relevant information, bullet points, and descriptions for each role, project, and achievement.
3. Do not omit or summarize unless information is clearly duplicated.
4. Customize the professional summary to highlight experiences, skills, and goals that match the job description. Use keywords from the job posting.
5. Align work experience: reorder bullet points to emphasize relevant duties and achievements, use similar language as the job ad, and quantify results where possible.
6. Match the skills section to the job posting, removing unrelated skills.
7. Adjust job titles for clarity if needed.
8. Add relevant keywords from the job posting throughout the CV.
9. Highlight relevant certifications/training, moving them higher if important.
10. Emphasize achievements that align with the company's goals.
11. Mirror the company's language and culture cues.
12. Adjust the order of sections for maximum relevance.
13. Generate a targeted cover letter that matches the tailored CV.

All property names and string values in the JSON must be enclosed in double quotes. Do not use single quotes or omit quotes. Return ONLY valid JSON, with no extra text, comments, or explanations.

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
        except Exception as e:
            logger.error(f"AI CV/cover letter JSON parse failed: {e}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            match = re.search(r'\{.*\}', response.choices[0].message.content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception as e2:
                    logger.error(f"Fallback JSON parse also failed: {e2}")
                    data = {}
            else:
                data = {}
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
        "Return ONLY a JSON array of keywords, with no extra text, comments, or explanations. "
        "Prioritize essential skills, technologies, certifications, and role-specific terms. "
        "Do not include generic words like 'job', 'candidate', or 'requirements'.\n\n"
        f"Job Description:\n{req.jobDescription[:4000]}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.2,
            response_format={"type": "json_array"}
        )
        import json
        try:
            keywords = json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Keyword extraction JSON parse failed: {e}")
            logger.error(f"Raw response: {response.choices[0].message.content}")
            # Fallback: try to extract JSON array from the response
            match = re.search(r'\[.*\]', response.choices[0].message.content, re.DOTALL)
            if match:
                try:
                    keywords = json.loads(match.group(0))
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

app.include_router(router) 