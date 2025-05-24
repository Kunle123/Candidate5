from fastapi import FastAPI, APIRouter, UploadFile, File, Depends, HTTPException, Request, Path, Body
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from uuid import uuid4
from fastapi.responses import FileResponse
import io
import os
import openai
import pdfplumber
from docx import Document
import logging
import jwt
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .models import UserArcData, CVTask, TaskStatusEnum
from .db import SessionLocal
import tiktoken
import re
import spacy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any

app = FastAPI(title="Career Ark (Arc) Service", description="API for Career Ark data extraction, deduplication, and application material generation.")
router = APIRouter(prefix="/api/arc")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Update logging configuration to enable verbose logging for the Ark service
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("arc")
logger.setLevel(logging.DEBUG)

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

tasks = {}

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

# --- Models ---
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

class CVStatusResponse(BaseModel):
    status: str
    extractedDataSummary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

def extract_text_from_pdf(file: UploadFile):
    try:
        with pdfplumber.open(file.file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        file.file.seek(0)
        if not text.strip():
            logger.error("[PDF EXTRACT] No text extracted from PDF file.")
        return text
    except Exception as e:
        logger.error(f"[PDF EXTRACT] Exception during PDF extraction: {e}")
        file.file.seek(0)
        return ""

def extract_text_from_docx(file: UploadFile):
    try:
        doc = Document(file.file)
        text = "\n".join([para.text for para in doc.paragraphs])
        file.file.seek(0)
        if not text.strip():
            logger.error("[DOCX EXTRACT] No text extracted from DOCX file.")
        return text
    except Exception as e:
        logger.error(f"[DOCX EXTRACT] Exception during DOCX extraction: {e}")
        file.file.seek(0)
        return ""

SECTION_HEADERS = [
    r"work experience", r"professional experience", r"employment history",
    r"education", r"academic background",
    r"skills", r"technical skills",
    r"projects", r"certifications", r"training"
]

section_header_regex = re.compile(rf"^({'|'.join(SECTION_HEADERS)})[:\s]*$", re.IGNORECASE | re.MULTILINE)

def split_cv_by_sections(text):
    matches = list(section_header_regex.finditer(text))
    if not matches:
        logger.info("[SECTION SPLIT] No section headers found. Treating entire CV as one section.")
        return [("full", text)]
    sections = []
    for i, match in enumerate(matches):
        start = match.start()
        header = match.group(1).strip().lower()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        logger.info(f"[SECTION SPLIT] Found section header: '{header}' (chars {start}-{end})")
        sections.append((header, section_text))
    return sections

def nlp_chunk_text(text, max_tokens=40000, model="gpt-4-turbo"):
    nlp = spacy.load("en_core_web_sm")
    enc = tiktoken.encoding_for_model(model)
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
    chunks = []
    current_chunk = []
    current_tokens = 0
    for sent in sentences:
        sent_tokens = len(enc.encode(sent))
        if current_tokens + sent_tokens > max_tokens and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sent]
            current_tokens = sent_tokens
        else:
            current_chunk.append(sent)
            current_tokens += sent_tokens
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    logger.info(f"[NLP CHUNKING] Created {len(chunks)} chunks (max {max_tokens} tokens each)")
    for i, chunk in enumerate(chunks):
        logger.info(f"[NLP CHUNKING] Chunk {i+1} token count: {len(enc.encode(chunk))}")
    return chunks

def filter_non_empty_entries(entries, key_fields=None, section_name=None):
    if not entries:
        logger.info(f"[FILTER] {section_name}: No entries to filter.")
        return []
    if key_fields is None:
        key_fields = ['company', 'title', 'description', 'start_date', 'end_date']
    filtered = []
    for entry in entries:
        if any(
            isinstance(entry.get(field), str) and entry.get(field).strip()
            for field in key_fields
        ):
            filtered.append(entry)
        else:
            logger.info(f"[FILTER] {section_name}: Filtered out empty/whitespace entry: {entry}")
    logger.info(f"[FILTER] {section_name}: {len(filtered)} of {len(entries)} entries kept after filtering.")
    return filtered

def flatten_work_experience(ai_work_experience):
    flat = []
    for entry in ai_work_experience:
        company = entry.get("company")
        date_range = entry.get("date_range")
        # Split date_range into start_date and end_date if possible
        start_date, end_date = None, None
        if date_range and "–" in date_range:
            parts = [p.strip() for p in date_range.split("–")]
            if len(parts) == 2:
                start_date, end_date = parts
        roles = entry.get("roles", [])
        for role in roles:
            flat.append({
                "company": company,
                "title": role.get("title"),
                "start_date": start_date,
                "end_date": end_date,
                "description": "\n".join(role.get("description", [])) if isinstance(role.get("description"), list) else role.get("description", "")
            })
    return flat

def parse_cv_with_ai_chunk(text):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt_instructions = (
        "You are a professional CV/resume parser specialized in extracting structured information from various CV formats. Your task is to extract key information from the provided CV and organize it into a standardized JSON format.\n"
        "\nFollow these specific guidelines:\n"
        "1. WORK EXPERIENCE EXTRACTION:\n"
        "   - Identify all work experiences throughout the document\n"
        "   - Group experiences by company and date range\n"
        "   - When the same role appears in multiple sections (summary and detailed sections):\n"
        "     * Combine all descriptions into one comprehensive entry\n"
        "     * Be flexible with job titles - if titles vary slightly but date ranges and company match, treat as the same role\n"
        "     * If a role has multiple titles at the same company during the same period, include all titles separated by ' / '\n"
        "   - For roles with overlapping date ranges at different companies, create separate entries\n"
        "   - Format each point in the description to start on a new line\n"
        "   - Ensure all experiences are listed in reverse chronological order (most recent first)\n"
        "   - Standardize date formats to 'MMM YYYY' (e.g., 'Jan 2021') or 'Present' for current roles\n"
        "2. EDUCATION EXTRACTION:\n"
        "   - Extract all education entries with institution, degree, field, dates, and descriptions\n"
        "   - Format consistently even if original CV has varying levels of detail\n"
        "   - If field is not explicitly stated but can be inferred from degree name, extract it\n"
        "3. SKILLS EXTRACTION:\n"
        "   - Extract all skills mentioned throughout the document\n"
        "   - Include certifications as skills AND as separate certification entries\n"
        "   - Deduplicate skills that appear multiple times\n"
        "   - Prioritize technical skills, methodologies, and domain expertise\n"
        "4. PROJECTS EXTRACTION:\n"
        "   - Extract all projects mentioned throughout the document\n"
        "   - Include project name and comprehensive description\n"
        "   - Distinguish between regular job responsibilities and distinct projects\n"
        "   - If project names are not explicitly stated, create descriptive names based on the content\n"
        "5. CERTIFICATIONS EXTRACTION:\n"
        "   - Extract all certifications with name, issuer, and year when available\n"
        "   - Include certifications even if they also appear in the skills section\n"
        "   - If issuer or year is not explicitly stated but can be reasonably inferred, provide the information\n"
        "   - For certifications without clear dates, use the most recent job date before the certification is mentioned as an estimate\n"
        "\nOutput the extracted information in the following JSON format:\n"
        "{\n  'work_experience': [ ... ],\n  'education': [ ... ],\n  'skills': [ ... ],\n  'projects': [ ... ],\n  'certifications': [ ... ]\n}\n"
        "\nEnsure your extraction is thorough and captures all relevant information from the CV, even if it appears in different sections or formats. The goal is to create a comprehensive career chronicle that can be used to generate future CVs.\n"
        "\nCV Text:\n"
    )
    prompt = prompt_instructions + text
    logger.info(f"[AI CHUNK] Raw text sent to OpenAI for this chunk:\n{text[:500]} ... (truncated)")
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1800,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        raw_response = response.choices[0].message.content
        logger.info(f"[AI CHUNK] Raw AI output for this chunk: {raw_response}")
        import json
        try:
            data = json.loads(raw_response)
        except Exception as e:
            logger.error(f"AI parsing failed: {e}")
            logger.error(f"Raw response: {raw_response}")
            match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception as e2:
                    logger.error(f"Fallback JSON parse also failed: {e2}")
                    data = {}
            else:
                data = {}
        # Defensive: remove raw_ai_output if present
        if "raw_ai_output" in data:
            del data["raw_ai_output"]
        for key in ["education", "projects", "certifications"]:
            if key in data and isinstance(data[key], list):
                new_list = []
                for entry in data[key]:
                    if isinstance(entry, str):
                        new_list.append({"description": entry})
                    else:
                        new_list.append(entry)
                data[key] = new_list
        # Flatten work_experience if needed
        if "work_experience" in data and isinstance(data["work_experience"], list):
            if data["work_experience"] and isinstance(data["work_experience"][0], dict) and "roles" in data["work_experience"][0]:
                data["work_experience"] = flatten_work_experience(data["work_experience"])
        try:
            arc_data = ArcData(**data)
        except Exception as e:
            logger.error(f"ArcData construction failed: {e}")
            arc_data = ArcData()  # Return empty ArcData on error
        # Remove raw_ai_output from arc_data
        if hasattr(arc_data, 'raw_ai_output'):
            delattr(arc_data, 'raw_ai_output')
        return arc_data
    except Exception as e:
        logger.error(f"AI parsing failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {e}")

# --- Dependency: Database Session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoint: Upload CV ---
class CVUploadResponse(BaseModel):
    taskId: str

@router.post("/cv", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    import uuid
    task_id = str(uuid.uuid4())
    logger.info(f"[CV UPLOAD] Received file: filename={file.filename}, content_type={file.content_type}")
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if not db_obj:
        db_obj = UserArcData(user_id=user_id, arc_data={})
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
    db_task = CVTask(id=task_id, user_id=user_id, status=TaskStatusEnum.pending)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    filename = file.filename.lower()
    try:
        logger.info(f"[CV UPLOAD] Processing file: {filename}")
        if filename.endswith(".pdf"):
            logger.info("[CV UPLOAD] File is PDF, extracting text...")
            text = extract_text_from_pdf(file)
        elif filename.endswith(".docx"):
            logger.info("[CV UPLOAD] File is DOCX, extracting text...")
            text = extract_text_from_docx(file)
        else:
            logger.error(f"[CV UPLOAD] Unsupported file type: {filename}")
            db_task.status = TaskStatusEnum.failed
            db_task.error = f"Unsupported file type uploaded: {filename}"
            db.commit()
            raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX are supported.")
        logger.info(f"[CV UPLOAD] Extracted text from file (first 500 chars):\n{text[:500]}")
        sections = split_cv_by_sections(text)
        logger.info(f"[CV UPLOAD] Found {len(sections)} section(s) in CV.")
        chunk_outputs = []
        ai_raw_chunks = []
        total_chunks = 0
        with ThreadPoolExecutor() as executor:
            futures = []
            for section_idx, (header, section_text) in enumerate(sections):
                nlp_chunks = nlp_chunk_text(section_text, max_tokens=800)
                logger.info(f"[CV UPLOAD] Section {section_idx+1} ('{header}') split into {len(nlp_chunks)} chunk(s).")
                for chunk_idx, chunk in enumerate(nlp_chunks):
                    logger.info(f"[CV UPLOAD] Section {section_idx+1} Chunk {chunk_idx+1} content (first 200 chars): {chunk[:200]}")
                    futures.append(executor.submit(parse_cv_with_ai_chunk, chunk))
                total_chunks += len(nlp_chunks)
            logger.info(f"[CV UPLOAD] Total NLP chunks to process: {total_chunks}")
            for future in as_completed(futures):
                arc_data = future.result()
                logger.info(f"[CV UPLOAD] AI chunk output: {arc_data}")
                arc_data_dict = arc_data.dict()
                arc_data_dict.pop("raw_ai_output", None)
                if not any(arc_data_dict.values()):
                    logger.warning(f"[CV UPLOAD] WARNING: Empty or skipped chunk output: {arc_data_dict}")
                chunk_outputs.append(arc_data_dict)
                if hasattr(arc_data, 'raw_ai_output'):
                    ai_raw_chunks.append(getattr(arc_data, 'raw_ai_output'))
        logger.info(f"[CV UPLOAD] Number of AI chunk outputs: {len(chunk_outputs)}")
        logger.info(f"[CV UPLOAD] All AI chunk outputs: {chunk_outputs}")
        combined = {"work_experience": [], "education": [], "skills": [], "projects": [], "certifications": []}
        for chunk in chunk_outputs:
            for key in combined.keys():
                value = chunk.get(key)
                if value:
                    if isinstance(value, list):
                        combined[key].extend(value)
                    else:
                        combined[key].append(value)
        # --- Preserve order for all lists as in the input JSON ---
        def deduplicate_preserve_order(seq):
            seen = set()
            return [x for x in seq if not (x in seen or seen.add(x))]
        filtered = {}
        filtered["work_experience"] = deduplicate_job_roles(filter_non_empty_entries(combined["work_experience"], ["company", "title", "description", "start_date", "end_date"], section_name="work_experience"))
        filtered["education"] = filter_non_empty_entries(combined["education"], ["institution", "degree", "field", "start_date", "end_date"], section_name="education")
        # Deduplicate skills while preserving order
        filtered["skills"] = deduplicate_preserve_order([s for s in combined["skills"] if s])
        filtered["projects"] = filter_non_empty_entries(combined["projects"], ["name", "description"], section_name="projects")
        filtered["certifications"] = filter_non_empty_entries(combined["certifications"], ["name", "issuer", "year"], section_name="certifications")
        # --- Split description into details for work_experience and education ---
        for entry in filtered.get("work_experience", []):
            entry["details"] = split_description_to_details(entry.get("description", ""))
        for entry in filtered.get("education", []):
            entry["details"] = split_description_to_details(entry.get("description", ""))
        # --- Optionally map projects.name to title and certifications.year to date ---
        for entry in filtered.get("projects", []):
            if "name" in entry:
                entry["title"] = entry["name"]
        for entry in filtered.get("certifications", []):
            if "year" in entry:
                entry["date"] = entry["year"]
        for key in list(filtered.keys()):
            if not filtered[key]:
                filtered[key] = None
        logger.info(f"[CV UPLOAD] Filtered data: {filtered}")
        # The order of all lists is now guaranteed to match the input JSON (except for deduplication, which preserves first occurrence order)
        new_arc_data = ArcData(**filtered)
        db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        arc_data_dict = new_arc_data.dict()
        arc_data_dict["raw_text"] = text
        arc_data_dict["ai_raw_chunks"] = ai_raw_chunks
        logger.info(f"[CV UPLOAD] Final arc_data_dict to be saved: {arc_data_dict}")
        if db_obj:
            db_obj.arc_data = arc_data_dict
        else:
            db_obj = UserArcData(user_id=user_id, arc_data=arc_data_dict)
            db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        db_task.status = TaskStatusEnum.completed
        db_task.extracted_data_summary = {"workExperienceCount": len(new_arc_data.work_experience or []), "skillsFound": len(new_arc_data.skills or [])}
        db.commit()
    except Exception as e:
        logger.error(f"Error in /cv upload endpoint: {e}")
        db_task.status = TaskStatusEnum.failed
        db_task.error = str(e)
        db.commit()
        raise
    return {"taskId": task_id}

def deduplicate_job_roles(job_roles):
    import re
    unique_roles = {}
    for role in job_roles:
        key = (role.get("title", ""), role.get("company", ""), role.get("start_date", ""), role.get("end_date", ""))
        desc = role.get("description", "")
        if key in unique_roles:
            existing_role = unique_roles[key]
            existing_desc = existing_role.get("description", "")
            # Split into sentences, remove duplicates, and preserve order
            def split_sentences(text):
                return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
            all_sentences = split_sentences(existing_desc) + split_sentences(desc)
            seen = set()
            unique_sentences = []
            for s in all_sentences:
                if s not in seen:
                    unique_sentences.append(s)
                    seen.add(s)
            combined_description = " ".join(unique_sentences)
            existing_role["description"] = combined_description
            logger.info(f"Combined descriptions for duplicate job role: {role}")
        else:
            unique_roles[key] = role
    return list(unique_roles.values())

def split_description_to_details(description):
    if not description:
        return []
    # Split on newlines and strip whitespace
    return [line.strip() for line in description.splitlines() if line.strip()]

# --- Endpoint: Chunk ---
@router.post("/chunk")
async def test_parse_cv_with_ai_chunk_new(request: Request, user_id: str = Depends(get_current_user)):
    body = await request.json()
    text = body.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' in request body.")
    # Minimal logic for demo; real logic can be restored as needed
    return {"parsed": {"text": text}, "raw": text}

# --- Endpoint: List User's Uploaded CVs/Tasks ---
@router.get("/cv/tasks")
async def list_cv_tasks(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_tasks = db.query(CVTask).filter(CVTask.user_id == user_id).all()
    return {"tasks": [
        {
            "taskId": str(task.id),
            "status": task.status,
            "extractedDataSummary": task.extracted_data_summary,
            "error": task.error,
            "created_at": task.created_at,
            "updated_at": task.updated_at
        } for task in db_tasks
    ]}

# --- Endpoint: Delete a CV or Task ---
@router.delete("/cv/{taskId}")
async def delete_cv_task(taskId: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    # Optionally, remove associated data from user_arc_data if needed
    return {"success": True}

# --- Endpoint: Download Processed CV ---
@router.get("/cv/download/{taskId}")
async def download_processed_cv(taskId: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if not db_user_arc or not db_user_arc.arc_data:
        raise HTTPException(status_code=404, detail="No extracted data found for user")
    import json
    data_bytes = json.dumps(db_user_arc.arc_data, indent=2).encode()
    return FileResponse(io.BytesIO(data_bytes), media_type="application/json", filename=f"extracted_cv_{taskId}.json")

@router.get("/cv/status/{taskId}", response_model=CVStatusResponse)
async def poll_cv_status(taskId: str = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": db_task.status,
        "extractedDataSummary": db_task.extracted_data_summary,
        "error": db_task.error
    }

@router.get("/cv/text/{taskId}")
async def get_raw_text(taskId: str = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
        if not db_task:
            logger.error(f"Task {taskId} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        if "raw_text" not in arc_data:
            logger.warning(f"raw_text not persisted for user {user_id}, task {taskId}")
            raise HTTPException(status_code=501, detail="raw_text is not stored persistently. Please advise how you want to handle this.")
        return {"raw_text": arc_data["raw_text"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_raw_text: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cv/ai-raw/{taskId}")
async def get_ai_raw(taskId: str = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
        if not db_task:
            logger.error(f"Task {taskId} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        if "ai_raw_chunks" not in arc_data:
            logger.warning(f"ai_raw_chunks not persisted for user {user_id}, task {taskId}")
            raise HTTPException(status_code=501, detail="ai_raw_chunks is not stored persistently. Please advise how you want to handle this.")
        return {"ai_raw_chunks": arc_data["ai_raw_chunks"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_ai_raw: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cv/ai-combined/{taskId}")
async def get_ai_combined(taskId: str = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
        if not db_task:
            logger.error(f"Task {taskId} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        if "ai_combined" not in arc_data:
            logger.warning(f"ai_combined not persisted for user {user_id}, task {taskId}")
            raise HTTPException(status_code=501, detail="ai_combined is not stored persistently. Please advise how you want to handle this.")
        return {"ai_combined": arc_data["ai_combined"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_ai_combined: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cv/ai-filtered/{taskId}")
async def get_ai_filtered(taskId: str = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
        if not db_task:
            logger.error(f"Task {taskId} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        if "ai_filtered" not in arc_data:
            logger.warning(f"ai_filtered not persisted for user {user_id}, task {taskId}")
            raise HTTPException(status_code=501, detail="ai_filtered is not stored persistently. Please advise how you want to handle this.")
        return {"ai_filtered": arc_data["ai_filtered"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_ai_filtered: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/cv/arcdata/{taskId}")
async def get_arcdata(taskId: str = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
        if not db_task:
            logger.error(f"Task {taskId} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Task not found")
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        if "arcdata" not in arc_data:
            logger.warning(f"arcdata not persisted for user {user_id}, task {taskId}")
            raise HTTPException(status_code=501, detail="arcdata is not stored persistently. Please advise how you want to handle this.")
        return {"arcdata": arc_data["arcdata"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_arcdata: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/data")
async def get_arc_data(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            # Return an empty profile if no data exists
            return {
                "work_experience": [],
                "education": [],
                "skills": [],
                "projects": [],
                "certifications": []
            }
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        # Ensure all required fields are present
        return {
            "work_experience": arc_data.get("work_experience", []),
            "education": arc_data.get("education", []),
            "skills": arc_data.get("skills", []),
            "projects": arc_data.get("projects", []),
            "certifications": arc_data.get("certifications", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_arc_data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/data")
async def update_arc_data(data: dict = Body(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        if not isinstance(data, dict):
            logger.error(f"Input data is malformed: {data}")
            raise HTTPException(status_code=400, detail="Input data is malformed")
        db_user_arc.arc_data = data
        db.commit()
        db.refresh(db_user_arc)
        return db_user_arc.arc_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_arc_data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/work_experience")
async def add_work_experience(entry: dict = Body(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        work_experience = arc_data.get("work_experience", [])
        if not isinstance(work_experience, list):
            logger.error(f"work_experience for user {user_id} is malformed: {work_experience}")
            raise HTTPException(status_code=400, detail="work_experience is malformed")
        # Assign a unique id to the new entry if not present
        import uuid
        if "id" not in entry:
            entry["id"] = str(uuid.uuid4())
        work_experience.append(entry)
        arc_data["work_experience"] = work_experience
        db_user_arc.arc_data = arc_data
        db.commit()
        db.refresh(db_user_arc)
        return entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in add_work_experience: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/work_experience/{id}")
async def update_work_experience(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        work_experience = arc_data.get("work_experience", [])
        if not isinstance(work_experience, list):
            logger.error(f"work_experience for user {user_id} is malformed: {work_experience}")
            raise HTTPException(status_code=400, detail="work_experience is malformed")
        found = False
        for entry in work_experience:
            if entry.get("id") == id:
                entry.update(update)
                found = True
                break
        if not found:
            logger.error(f"Work experience entry with id {id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Work experience entry not found")
        arc_data["work_experience"] = work_experience
        db_user_arc.arc_data = arc_data
        db.commit()
        db.refresh(db_user_arc)
        return update
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_work_experience: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/education")
async def add_education(entry: dict = Body(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        education = arc_data.get("education", [])
        if not isinstance(education, list):
            logger.error(f"education for user {user_id} is malformed: {education}")
            raise HTTPException(status_code=400, detail="education is malformed")
        # Assign a unique id to the new entry if not present
        import uuid
        if "id" not in entry:
            entry["id"] = str(uuid.uuid4())
        education.append(entry)
        arc_data["education"] = education
        db_user_arc.arc_data = arc_data
        db.commit()
        db.refresh(db_user_arc)
        return entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in add_education: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/education/{id}")
async def update_education(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        education = arc_data.get("education", [])
        if not isinstance(education, list):
            logger.error(f"education for user {user_id} is malformed: {education}")
            raise HTTPException(status_code=400, detail="education is malformed")
        found = False
        for entry in education:
            if entry.get("id") == id:
                entry.update(update)
                found = True
                break
        if not found:
            logger.error(f"Education entry with id {id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Education entry not found")
        arc_data["education"] = education
        db_user_arc.arc_data = arc_data
        db.commit()
        db.refresh(db_user_arc)
        return update
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_education: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/training")
async def add_training(entry: dict = Body(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        training = arc_data.get("training", [])
        if not isinstance(training, list):
            training = []
        import uuid
        if "id" not in entry:
            entry["id"] = str(uuid.uuid4())
        training.append(entry)
        arc_data["training"] = training
        db_user_arc.arc_data = arc_data
        db.commit()
        db.refresh(db_user_arc)
        return entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in add_training: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.patch("/training/{id}")
async def update_training(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        training = arc_data.get("training", [])
        if not isinstance(training, list):
            logger.error(f"training for user {user_id} is malformed: {training}")
            raise HTTPException(status_code=400, detail="training is malformed")
        found = False
        for entry in training:
            if entry.get("id") == id:
                entry.update(update)
                found = True
                break
        if not found:
            logger.error(f"Training entry with id {id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Training entry not found")
        arc_data["training"] = training
        db_user_arc.arc_data = arc_data
        db.commit()
        db.refresh(db_user_arc)
        return update
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in update_training: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/work_experience/{id}")
async def delete_work_experience(id: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
        if not db_user_arc or not db_user_arc.arc_data:
            logger.error(f"UserArcData not found for user {user_id}")
            raise HTTPException(status_code=404, detail="No extracted data found for user")
        arc_data = db_user_arc.arc_data
        if not isinstance(arc_data, dict):
            logger.error(f"arc_data for user {user_id} is malformed: {arc_data}")
            raise HTTPException(status_code=400, detail="arc_data is malformed")
        work_experience = arc_data.get("work_experience", [])
        if not isinstance(work_experience, list):
            logger.error(f"work_experience for user {user_id} is malformed: {work_experience}")
            raise HTTPException(status_code=400, detail="work_experience is malformed")
        found = False
        for entry in work_experience:
            if entry.get("id") == id:
                work_experience.remove(entry)
                found = True
                break
        if not found:
            logger.error(f"Work experience entry with id {id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail="Work experience entry not found")
        arc_data["work_experience"] = work_experience
        db_user_arc.arc_data = arc_data
        db.commit()
        db.refresh(db_user_arc)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_work_experience: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/logs")
async def get_logs(user_id: str = Depends(get_current_user)):
    try:
        # In a real implementation, you would fetch logs from a logging service or file
        # For now, we'll return a placeholder message
        return {"message": "Logs are not yet implemented. This endpoint will return logs for debugging purposes."}
    except Exception as e:
        logger.error(f"Unexpected error in get_logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"} 