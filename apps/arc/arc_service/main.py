from fastapi import FastAPI, APIRouter, UploadFile, File, Depends, HTTPException, Request, Path, Body, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from uuid import uuid4, UUID
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
from .models import UserArcData, CVTask, TaskStatusEnum, CVProfile, WorkExperience, Education, Skill, Project, Certification
from .db import SessionLocal, Base, engine
import tiktoken
import re
import spacy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any
from .career_ark_router import router as career_ark_router
from .auth import get_current_user, oauth2_scheme
from .arc_schemas import ArcData, Role
from .cv_utils import extract_text_from_pdf, extract_text_from_docx, split_cv_by_sections, nlp_chunk_text
from .ai_utils import parse_cv_with_ai_chunk, flatten_work_experience, extract_cv_metadata_with_ai, extract_work_experience_description_with_ai

app = FastAPI(title="Career Ark (Arc) Service", description="API for Career Ark data extraction, deduplication, and application material generation.")

# --- Database Table Creation ---
@app.on_event("startup")
def startup_event():
    import logging
    logger = logging.getLogger("arc")
    logger.info("Running startup event: Creating database tables if they don't exist...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        # Depending on the error, you might want to prevent startup
# --- End Database Table Creation ---

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

app.include_router(career_ark_router, prefix="/api/career-ark", tags=["Career Ark"])

tasks = {}

# --- Models ---
class CVStatusResponse(BaseModel):
    status: str
    extractedDataSummary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

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

def parse_cv_with_ai_chunk(text):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt_instructions = (
        """You are a professional CV/resume parser specialized in extracting structured information from various CV formats. Your task is to extract key information from the provided CV and organize it into a standardized JSON format.\n\nFollow these specific guidelines:\n\n1. WORK EXPERIENCE EXTRACTION:\n   - Identify all work experiences throughout the document\n   - Group experiences by company and date range\n   - When the same role appears in multiple sections (summary and detailed sections):\n     * Combine all descriptions into one comprehensive entry\n     * Be flexible with job titles - if titles vary slightly but date ranges and company match, treat as the same role\n     * If a role has multiple titles at the same company during the same period, include all titles separated by \" / \"\n   - For roles with overlapping date ranges at different companies, create separate entries\n   - Format each point in the description to start on a new line\n   - Ensure all experiences are listed in reverse chronological order (most recent first)\n   - Standardize date formats to \"MMM YYYY\" (e.g., \"Jan 2021\") or \"Present\" for current roles\n   - Preserve full company names including divisions or departments (e.g., \"Test Supply Chain DHSC/UKHSA\" not just \"UKHSA\")\n   - Only include information explicitly stated in the CV, do not add inferred or generic descriptions\n\n2. EDUCATION EXTRACTION:\n   - Extract all education entries with institution, degree, field, dates, and descriptions\n   - Format consistently even if original CV has varying levels of detail\n   - If field is not explicitly stated but can be inferred from degree name, extract it\n\n3. SKILLS EXTRACTION:\n   - Extract ALL skills mentioned throughout the document, including those embedded in work experience descriptions\n   - Be thorough in identifying technical skills (e.g., Azure, Mulesoft, Power Apps, Power BI)\n   - Include methodologies (e.g., Agile, PRINCE2, Scrum)\n   - Include domain expertise (e.g., project management, integration, digital transformation)\n   - Include certifications as skills AND as separate certification entries\n   - Deduplicate skills that appear multiple times\n   - Aim to extract at least 15-20 skills if they are present in the document\n\n4. PROJECTS EXTRACTION:\n   - Extract all projects mentioned throughout the document\n   - Include project name and comprehensive description\n   - Distinguish between regular job responsibilities and distinct projects\n   - If project names are not explicitly stated, create descriptive names based on the content\n\n5. CERTIFICATIONS EXTRACTION:\n   - Extract all certifications with name, issuer, and year when available\n   - Include certifications even if they also appear in the skills section\n   - For certification issuers:\n     * PRINCE2 Practitioner is issued by AXELOS (formerly OGC)\n     * Certified Scrum Master is issued by Scrum Alliance\n     * If not explicitly stated, research standard issuers for common certifications\n   - For certification years:\n     * If explicitly stated, use the stated year\n     * If not stated, make a reasonable estimate based on career progression:\n       - For PRINCE2: Estimate 2017-2018 (before the Npower Digital role where project management was heavily featured)\n       - For Scrum Master: Estimate 2016-2017 (before the role at Npower Digital where Scrum Master duties were mentioned)\n     * NEVER use \"Unknown\" for certification years or issuers - always provide a reasonable estimate based on career timeline\n\nOutput the extracted information in the following JSON format:\n{\n  \"work_experience\": [\n    {\n      \"id\": \"string\",                // Generate a unique identifier\n      \"company\": \"string\",           // Full company name including divisions/departments\n      \"title\": \"string\",             // Job title(s), separated by \" / \" if multiple\n      \"start_date\": \"string\",        // Start date in format \"MMM YYYY\" or \"YYYY\"\n      \"end_date\": \"string\",          // End date in format \"MMM YYYY\", \"YYYY\", or \"Present\"\n      \"description\": \"string\"        // Comprehensive description with each point on a new line\n    }\n  ],\n  \"education\": [\n    {\n      \"id\": \"string\",                // Generate a unique identifier\n      \"institution\": \"string\",       // Educational institution\n      \"degree\": \"string\",            // Degree type\n      \"field\": \"string\",             // Field of study\n      \"start_date\": \"string\",        // Start date in format \"YYYY\" or \"MMM YYYY\"\n      \"end_date\": \"string\",          // End date in format \"YYYY\" or \"MMM YYYY\"\n      \"description\": \"string\"        // Any additional details about the education\n    }\n  ],\n  \"skills\": [\n    \"string\"                         // List of all skills including certifications\n  ],\n  \"projects\": [\n    {\n      \"id\": \"string\",                // Generate a unique identifier\n      \"name\": \"string\",              // Project name\n      \"description\": \"string\"        // Comprehensive project description\n    }\n  ],\n  \"certifications\": [\n    {\n      \"id\": \"string\",                // Generate a unique identifier\n      \"name\": \"string\",              // Certification name\n      \"issuer\": \"string\",            // Certification issuer (NEVER use \"Unknown\")\n      \"year\": \"string\"               // Year obtained (NEVER use \"Unknown\", provide estimate)\n    }\n  ]\n}\n\nEnsure your extraction is thorough and captures all relevant information from the CV, even if it appears in different sections or formats. The goal is to create a comprehensive career chronicle that can be used to generate future CVs.\n"""
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
        # --- JSON format verification ---
        expected_keys = ["work_experience", "education", "skills", "projects", "certifications"]
        for key in expected_keys:
            if key not in data:
                logger.error(f"[AI CHUNK] Missing key in response: {key}")
                raise HTTPException(status_code=500, detail=f"AI response missing required key: {key}")
        if not isinstance(data["work_experience"], list) or not isinstance(data["education"], list) or not isinstance(data["skills"], list) or not isinstance(data["projects"], list) or not isinstance(data["certifications"], list):
            logger.error("[AI CHUNK] One or more top-level fields are not lists as required.")
            raise HTTPException(status_code=500, detail="AI response fields are not lists as required.")
        for cert in data["certifications"]:
            if cert.get("issuer", "").strip().lower() == "unknown" or cert.get("year", "").strip().lower() == "unknown":
                logger.error(f"[AI CHUNK] Certification with 'Unknown' issuer/year: {cert}")
                raise HTTPException(status_code=500, detail="AI response contains 'Unknown' for certification issuer or year, which is not allowed.")
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

@app.post("/api/arc/cv", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    import uuid
    logger = logging.getLogger("arc")
    # 1. Extract text from file
    contents = await file.read()
    import io
    if file.filename.endswith(".pdf"):
        from .cv_utils import extract_text_from_pdf
        cv_text = extract_text_from_pdf(io.BytesIO(contents))
    elif file.filename.endswith(".docx"):
        from .cv_utils import extract_text_from_docx
        cv_text = extract_text_from_docx(io.BytesIO(contents))
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    # 2. First pass: extract metadata only
    try:
        metadata = extract_cv_metadata_with_ai(cv_text)
        logger.info(f"[CV UPLOAD] Extracted metadata: {metadata}")
    except Exception as e:
        logger.error(f"[CV UPLOAD] Metadata extraction failed: {e}")
        raise HTTPException(status_code=500, detail="Metadata extraction failed")
    # 3. Create or get CVProfile
    profile = db.query(CVProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile = CVProfile(id=uuid.uuid4(), user_id=user_id, name="Unnamed", email=None)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    # Ensure user_arc_data exists for this user (legacy support)
    user_arc_data = db.query(UserArcData).filter_by(user_id=user_id).first()
    if not user_arc_data:
        user_arc_data = UserArcData(user_id=user_id, arc_data={})
        db.add(user_arc_data)
        db.commit()
        db.refresh(user_arc_data)
    # 4. Insert metadata into normalized tables (normalized, not user_arc_data)
    # --- Deduplication and merging logic ---
    # Work Experience
    work_exp_ids = []
    existing_work_exps = {(wx.company, wx.title, wx.start_date, wx.end_date): wx for wx in db.query(WorkExperience).filter_by(cv_profile_id=profile.id).all()}
    for idx, wx in enumerate(metadata.get("work_experiences", [])):
        key = (
            wx.get("company", ""),
            wx.get("job_title", wx.get("title", "")),
            wx.get("start_date", ""),
            wx.get("end_date", "")
        )
        existing = existing_work_exps.get(key)
        if existing:
            new_desc = wx.get("description", "")
            old_desc = existing.description or ""
            if new_desc and new_desc.strip():
                old_lines = set([l.strip() for l in (old_desc.split("\n") if old_desc else []) if l.strip()])
                new_lines = [l.strip() for l in (new_desc.split("\n") if new_desc else []) if l.strip()]
                merged_lines = list(old_lines)
                for line in new_lines:
                    if line and line not in old_lines:
                        merged_lines.append(line)
                merged_desc = "\n".join(merged_lines)
                if merged_desc != old_desc:
                    existing.description = merged_desc
                    db.add(existing)
            # If new_desc is empty, do NOT overwrite or clear the old description
            work_exp_ids.append(existing.id)
        else:
            wx_id = uuid.uuid4()
            work_exp_ids.append(wx_id)
            db.add(WorkExperience(
                id=wx_id,
                cv_profile_id=profile.id,
                company=wx.get("company", ""),
                title=wx.get("job_title", wx.get("title", "")),
                start_date=wx.get("start_date", ""),
                end_date=wx.get("end_date", ""),
                description=None,  # To be filled in Pass 2
                order_index=idx
            ))
    # Education
    existing_educations = {(e.institution, e.degree, e.start_date, e.end_date): e for e in db.query(Education).filter_by(cv_profile_id=profile.id).all()}
    for idx, edu in enumerate(metadata.get("education", [])):
        key = (
            edu.get("institution", ""),
            edu.get("degree", ""),
            edu.get("start_date", None),
            edu.get("end_date", None)
        )
        existing = existing_educations.get(key)
        if existing:
            new_desc = edu.get("description", "")
            old_desc = existing.description or ""
            if new_desc and new_desc.strip():
                old_lines = set([l.strip() for l in (old_desc.split("\n") if old_desc else []) if l.strip()])
                new_lines = [l.strip() for l in (new_desc.split("\n") if new_desc else []) if l.strip()]
                merged_lines = list(old_lines)
                for line in new_lines:
                    if line and line not in old_lines:
                        merged_lines.append(line)
                merged_desc = "\n".join(merged_lines)
                if merged_desc != old_desc:
                    existing.description = merged_desc
                    db.add(existing)
            # If new_desc is empty, do NOT overwrite or clear the old description
        else:
            db.add(Education(
                id=uuid.uuid4(),
                cv_profile_id=profile.id,
                institution=edu.get("institution", ""),
                degree=edu.get("degree", ""),
                field=edu.get("field", None),
                start_date=edu.get("start_date", None),
                end_date=edu.get("end_date", None),
                description=edu.get("description", None),
                order_index=idx
            ))
    # Certifications
    existing_certs = {(c.name, c.issuer, c.year): c for c in db.query(Certification).filter_by(cv_profile_id=profile.id).all()}
    for idx, cert in enumerate(metadata.get("certifications", [])):
        key = (
            cert.get("name", ""),
            cert.get("issuer", None),
            cert.get("year", cert.get("date", None))
        )
        existing = existing_certs.get(key)
        if not existing:
            db.add(Certification(
                id=uuid.uuid4(),
                cv_profile_id=profile.id,
                name=cert.get("name", ""),
                issuer=cert.get("issuer", None),
                year=cert.get("year", cert.get("date", None)),
                order_index=idx
            ))
    # Skills (deduplicate by skill name)
    existing_skills = set(s.skill for s in db.query(Skill).filter_by(cv_profile_id=profile.id).all())
    for skill in metadata.get("skills", []):
        if skill not in existing_skills:
            db.add(Skill(
                id=uuid.uuid4(),
                cv_profile_id=profile.id,
                skill=skill
            ))
    # Projects (deduplicate by name)
    existing_projects = set((p.name, p.description) for p in db.query(Project).filter_by(cv_profile_id=profile.id).all())
    for idx, proj in enumerate(metadata.get("projects", [])):
        key = (proj.get("name", ""), proj.get("description", None))
        if key not in existing_projects:
            db.add(Project(
                id=uuid.uuid4(),
                cv_profile_id=profile.id,
                name=proj.get("name", ""),
                description=proj.get("description", None),
                order_index=idx
            ))
    db.commit()
    db.refresh(profile)
    # 5. Mark task as metadata_extracted
    db_task = CVTask(id=uuid.uuid4(), user_id=user_id, status="metadata_extracted", error=None)
    db.add(db_task)
    db.commit()
    # 6. Trigger Pass 2 in background
    def run_pass2_and_update_descriptions(cv_text, work_exp_ids, user_id, profile_id, task_id):
        from .ai_utils import extract_work_experience_description_with_ai
        from .models import AIExtractionLog, WorkExperience, CVTask, TaskStatusEnum
        from .db import SessionLocal
        import traceback
        session = SessionLocal()
        errors = []
        try:
            for wx_id in work_exp_ids:
                wx = session.query(WorkExperience).filter_by(id=wx_id, cv_profile_id=profile_id).first()
                if not wx:
                    continue
                wx_metadata = {
                    "job_title": wx.title,
                    "company": wx.company,
                    "start_date": wx.start_date,
                    "end_date": wx.end_date,
                    "location": None
                }
                try:
                    prompt = f"Extract description for: {wx_metadata}"
                    description = extract_work_experience_description_with_ai(cv_text, wx_metadata)
                    wx.description = description
                    session.add(AIExtractionLog(
                        task_id=task_id,
                        entry_type="work_experience",
                        entry_id=wx_id,
                        prompt=str(wx_metadata),
                        response=description,
                        status="success",
                        error_message=None
                    ))
                except Exception as e:
                    session.add(AIExtractionLog(
                        task_id=task_id,
                        entry_type="work_experience",
                        entry_id=wx_id,
                        prompt=str(wx_metadata),
                        response=None,
                        status="failed",
                        error_message=str(e) + "\n" + traceback.format_exc()
                    ))
                    errors.append(f"WorkExperience {wx_id}: {e}")
            # Update task status
            db_task = session.query(CVTask).filter_by(id=task_id).first()
            if errors:
                db_task.status = "completed_with_errors"
                db_task.error = " | ".join(errors)
            else:
                db_task.status = "completed"
                db_task.error = None
            session.commit()
        finally:
            session.close()
    if background_tasks is not None:
        background_tasks.add_task(run_pass2_and_update_descriptions, cv_text, work_exp_ids, user_id, profile.id, db_task.id)
    return CVUploadResponse(taskId=str(db_task.id))

@app.post("/api/career-ark/cv", response_model=CVUploadResponse)
async def upload_cv_career_ark(file: UploadFile = File(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    # Reuse the logic from /api/arc/cv
    return await upload_cv(file, user_id, db, background_tasks)

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
@app.post("/api/arc/chunk")
async def test_parse_cv_with_ai_chunk_new(request: Request, user_id: str = Depends(get_current_user)):
    body = await request.json()
    text = body.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' in request body.")
    # Minimal logic for demo; real logic can be restored as needed
    return {"parsed": {"text": text}, "raw": text}

# --- Endpoint: List User's Uploaded CVs/Tasks ---
@app.get("/api/arc/cv/tasks")
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
@app.delete("/api/arc/cv/{taskId}")
async def delete_cv_task(taskId: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    # Optionally, remove associated data from user_arc_data if needed
    return {"success": True}

# --- Endpoint: Download Processed CV ---
@app.get("/api/arc/cv/download/{taskId}", response_model=CVStatusResponse)
async def download_processed_cv(taskId: UUID = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if not db_user_arc or not db_user_arc.arc_data:
        raise HTTPException(status_code=404, detail="No extracted data found for user")
    import json
    data_bytes = json.dumps(db_user_arc.arc_data, indent=2).encode()
    return FileResponse(io.BytesIO(data_bytes), media_type="application/json", filename=f"extracted_cv_{taskId}.json")

@app.get("/api/arc/cv/text/{taskId}")
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

@app.get("/api/arc/cv/ai-raw/{taskId}")
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

@app.get("/api/arc/cv/ai-combined/{taskId}")
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

@app.get("/api/arc/cv/ai-filtered/{taskId}")
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

@app.get("/api/arc/data")
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

@app.put("/api/arc/data")
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

@app.post("/api/arc/work_experience")
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

@app.patch("/api/arc/work_experience/{id}")
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

@app.post("/api/arc/education")
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

@app.patch("/api/arc/education/{id}")
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

@app.post("/api/arc/training")
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

@app.patch("/api/arc/training/{id}")
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

@app.delete("/api/arc/work_experience/{id}")
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

@app.get("/api/arc/logs")
async def get_logs(user_id: str = Depends(get_current_user)):
    try:
        # In a real implementation, you would fetch logs from a logging service or file
        # For now, we'll return a placeholder message
        return {"message": "Logs are not yet implemented. This endpoint will return logs for debugging purposes."}
    except Exception as e:
        logger.error(f"Unexpected error in get_logs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/arc/ping")
async def ping():
    return {"message": "pong"}

@app.get("/api/arc/cv/task-status/{taskId}", response_model=CVStatusResponse)
async def get_task_status(taskId: UUID = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(f"[DEBUG] /cv/task-status called with taskId={taskId}, user_id={user_id}")
    # TEMP: Remove user_id filter for debugging
    db_task = db.query(CVTask).filter(CVTask.id == taskId).first()
    logger.info(f"[DEBUG] DB query result for taskId={taskId}: {db_task}")
    if not db_task:
        logger.warning(f"[DEBUG] Task not found for taskId={taskId}")
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": db_task.status,
        "extractedDataSummary": db_task.extracted_data_summary,
        "error": db_task.error
    }

@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"} 