from fastapi import FastAPI, APIRouter, UploadFile, File, Depends, HTTPException, Body, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import uuid4
from fastapi.responses import FileResponse
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import spacy

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

# In-memory stores for demo purposes
# (You may want to use a persistent store in production)
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

# --- Dependency: Database Session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def extract_text_from_pdf(file: UploadFile):
    with pdfplumber.open(file.file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return text

def extract_text_from_docx(file: UploadFile):
    doc = Document(file.file)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def split_cv_by_sections(text):
    # Simple section splitting by headers (customize as needed)
    section_header_regex = re.compile(r"^(work experience|education|skills|projects|certifications)[:\s]*$", re.IGNORECASE | re.MULTILINE)
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

def nlp_chunk_text(text, max_tokens=1500, model="gpt-3.5-turbo"):
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
    return chunks

def filter_non_empty_entries(entries, key_fields=None, section_name=None):
    if not entries:
        return []
    filtered = []
    for entry in entries:
        if isinstance(entry, dict):
            if any(entry.get(k) for k in (key_fields or [])):
                filtered.append(entry)
        elif entry:
            filtered.append(entry)
    return filtered

def parse_cv_with_ai_chunk(text):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt_instructions = (
        "Extract all information related to each individual job role, combining any matching content from all sections such as 'Work Experience', 'Relevant Achievements', 'Projects', or others. "
        "Group everything by job title and company, ensuring that dates, responsibilities, achievements, technologies used, and descriptions are preserved in full detail. "
        "Output the result as a JSON array where each object contains: 'company', 'title', 'start_date', 'end_date', and 'description'.\n"
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
        except Exception as e:
            logger.error(f"AI parsing failed: {e}")
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
        return data
    except Exception as e:
        logger.error(f"AI parsing failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {e}")

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
        logger.info(f"[CV UPLOAD] Extracted text from file:\n{text}")
        tasks[task_id]["raw_text"] = text
        # --- AI Extraction ---
        # Save per-chunk raw AI output
        sections = split_cv_by_sections(text)
        chunk_outputs = []
        raw_ai_outputs = []
        with ThreadPoolExecutor() as executor:
            futures = []
            for header, section_text in sections:
                nlp_chunks = nlp_chunk_text(section_text, max_tokens=1500)
                for chunk in nlp_chunks:
                    futures.append(executor.submit(parse_cv_with_ai_chunk, chunk))
            for future in as_completed(futures):
                arc_data = future.result()
                chunk_outputs.append(arc_data)
                # Save raw AI output if available (from logger or arc_data)
                if hasattr(arc_data, 'raw_ai_output'):
                    raw_ai_outputs.append(arc_data.raw_ai_output)
        tasks[task_id]["ai_raw_chunks"] = raw_ai_outputs
        # --- Combined AI Output ---
        combined = {"work_experience": [], "education": [], "skills": [], "projects": [], "certifications": []}
        for chunk in chunk_outputs:
            for key in combined.keys():
                value = chunk.get(key)
                if value:
                    if isinstance(value, list):
                        combined[key].extend(value)
                    else:
                        combined[key].append(value)
        tasks[task_id]["ai_combined"] = combined.copy()
        # --- Filtering ---
        filtered = {}
        filtered["work_experience"] = filter_non_empty_entries(combined["work_experience"], ["company", "title", "description", "start_date", "end_date"], section_name="work_experience")
        filtered["education"] = filter_non_empty_entries(combined["education"], ["institution", "degree", "field", "start_date", "end_date"], section_name="education")
        filtered["skills"] = [s for s in combined["skills"] if s]
        filtered["projects"] = filter_non_empty_entries(combined["projects"], ["name", "description"], section_name="projects")
        filtered["certifications"] = filter_non_empty_entries(combined["certifications"], ["name", "issuer", "year"], section_name="certifications")
        for key in list(filtered.keys()):
            if not filtered[key]:
                filtered[key] = None
        tasks[task_id]["ai_filtered"] = filtered.copy()
        # --- Final ArcData ---
        new_arc_data = ArcData(**filtered)
        tasks[task_id]["arcdata"] = new_arc_data.dict()
    except Exception as e:
        logger.error(f"Error in /cv upload endpoint: {e}")
        tasks[task_id] = {"status": "failed", "user_id": user_id, "error": str(e)}
        raise
    # Deduplicate and merge with existing data from DB
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj:
        db_obj.arc_data = new_arc_data.dict()
    else:
        db_obj = UserArcData(user_id=user_id, arc_data=new_arc_data.dict())
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    tasks[task_id]["status"] = "completed"
    tasks[task_id]["extractedDataSummary"] = {"workExperienceCount": len(new_arc_data.work_experience or []), "skillsFound": len(new_arc_data.skills or [])}
    return {"taskId": task_id}

@router.post("/chunk")
async def test_parse_cv_with_ai_chunk_new(request: Request, user_id: str = Depends(get_current_user)):
    body = await request.json()
    text = body.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' in request body.")
    import json as pyjson
    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not set")
        client = openai.OpenAI(api_key=openai_api_key)
        prompt_instructions = (
            "Extract all information related to each individual job role, combining any matching content from all sections such as 'Work Experience', 'Relevant Achievements', 'Projects', or others. "
            "Group everything by job title and company, ensuring that dates, responsibilities, achievements, technologies used, and descriptions are preserved in full detail. "
            "Output the result as a JSON array where each object contains: 'company', 'title', 'start_date', 'end_date', and 'description'.\n"
            "CV Text:\n"
        )
        prompt = prompt_instructions + text
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1800,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        raw_content = response.choices[0].message.content
        try:
            parsed = pyjson.loads(raw_content)
        except Exception as e:
            parsed = {"error": str(e), "raw": raw_content}
        return {"parsed": parsed, "raw": raw_content}
    except Exception as e:
        return {"error": str(e)}

app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- Add debug and data endpoints ---

@router.get("/cv/download/{taskId}")
async def download_processed_cv(taskId: str, user_id: str = Depends(get_current_user)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    dummy_content = f"Processed CV data for task {taskId}"
    return FileResponse(io.BytesIO(dummy_content.encode()), media_type="text/plain", filename=f"processed_cv_{taskId}.txt")

@router.get("/cv/tasks")
async def list_cv_tasks(user_id: str = Depends(get_current_user)):
    user_tasks = [ {"taskId": tid, **{k:v for k,v in t.items() if k != "user_id"}} for tid, t in tasks.items() if t["user_id"] == user_id ]
    return {"tasks": user_tasks}

@router.delete("/cv/{taskId}")
async def delete_cv_task(taskId: str, user_id: str = Depends(get_current_user)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    del tasks[taskId]
    return {"success": True}

class KeywordsRequest(BaseModel):
    jobDescription: str

class KeywordsResponse(BaseModel):
    keywords: list[str]

@router.post("/ai/keywords", response_model=KeywordsResponse)
async def extract_keywords(req: KeywordsRequest, user_id: str = Depends(get_current_user)):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = f'''Extract up to 20 of the most important recruiter-focused keywords from the following job description.\nUse UK English spelling and conventions throughout (e.g., 'organisation' not 'organization', 'specialise' not 'specialize').\nReturn ONLY a JSON object with a single property 'keywords', which is an array of keywords, and no extra text, comments, or explanations.\n\nJob Description:\n{req.jobDescription[:4000]}'''
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

class GenerateRequest(BaseModel):
    jobAdvert: str
    arcData: Dict[str, Any]

class GenerateResponse(BaseModel):
    cv: str
    coverLetter: str

@router.post("/generate", response_model=GenerateResponse)
async def generate_materials(req: GenerateRequest, user_id: str = Depends(get_current_user)):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = f"""You are an expert CV and cover letter writer. Your task is to generate a professional, optimized CV and a tailored cover letter for an applicant based on their provided career history and a specific job posting.\n\n[START APPLICANT CAREER HISTORY]\n{str(req.arcData)}\n[END APPLICANT CAREER HISTORY]\n\n[START JOB POSTING]\n{req.jobAdvert}\n[END JOB POSTING]\n"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        import json
        data = json.loads(response.choices[0].message.content)
        return GenerateResponse(**data)
    except Exception as e:
        logger.error(f"AI CV/cover letter generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI CV/cover letter generation failed: {e}")

# --- Add remaining endpoints ---

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
        db_obj.arc_data = data.dict()
    else:
        db_obj = UserArcData(user_id=user_id, arc_data=data.dict())
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return data

@router.get("")
async def get_all_arc_data(user_id: str = Depends(get_current_user)):
    db = next(get_db())
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj:
        return db_obj.arc_data
    return {}

@router.post("/work_experience")
async def add_work_experience(entry: dict = Body(...), user_id: str = Depends(get_current_user)):
    db = next(get_db())
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj:
        arc_data = ArcData(**db_obj.arc_data)
        arc_data.work_experience = (arc_data.work_experience or []) + [entry]
        db_obj.arc_data = arc_data.dict()
    else:
        arc_data = ArcData(work_experience=[entry])
        db_obj = UserArcData(user_id=user_id, arc_data=arc_data.dict())
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return entry

@router.post("/education")
async def add_education(entry: dict = Body(...), user_id: str = Depends(get_current_user)):
    db = next(get_db())
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj:
        arc_data = ArcData(**db_obj.arc_data)
        arc_data.education = (arc_data.education or []) + [entry]
        db_obj.arc_data = arc_data.dict()
    else:
        arc_data = ArcData(education=[entry])
        db_obj = UserArcData(user_id=user_id, arc_data=arc_data.dict())
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return entry

@router.post("/training")
async def add_training(entry: dict = Body(...), user_id: str = Depends(get_current_user)):
    db = next(get_db())
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj:
        arc_data = ArcData(**db_obj.arc_data)
        arc_data.certifications = (arc_data.certifications or []) + [entry]
        db_obj.arc_data = arc_data.dict()
    else:
        arc_data = ArcData(certifications=[entry])
        db_obj = UserArcData(user_id=user_id, arc_data=arc_data.dict())
        db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return entry

@router.patch("/work_experience/{id}")
async def update_work_experience(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user)):
    db = next(get_db())
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj and db_obj.arc_data.get("work_experience"):
        for entry in db_obj.arc_data["work_experience"]:
            if entry.get("id") == id:
                entry.update(update)
        db.commit()
        db.refresh(db_obj)
        return update
    raise HTTPException(status_code=404, detail="Work experience not found")

@router.patch("/education/{id}")
async def update_education(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user)):
    db = next(get_db())
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj and db_obj.arc_data.get("education"):
        for entry in db_obj.arc_data["education"]:
            if entry.get("id") == id:
                entry.update(update)
        db.commit()
        db.refresh(db_obj)
        return update
    raise HTTPException(status_code=404, detail="Education not found")

@router.patch("/training/{id}")
async def update_training(id: str, update: dict = Body(...), user_id: str = Depends(get_current_user)):
    db = next(get_db())
    db_obj = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if db_obj and db_obj.arc_data.get("certifications"):
        for entry in db_obj.arc_data["certifications"]:
            if entry.get("id") == id:
                entry.update(update)
        db.commit()
        db.refresh(db_obj)
        return update
    raise HTTPException(status_code=404, detail="Training not found") 