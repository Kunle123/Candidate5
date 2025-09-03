# Dummy change to trigger redeployment
from fastapi import APIRouter, HTTPException, Path, Body, Depends, UploadFile, File, Request
from sqlalchemy.orm import Session
from .models import WorkExperience, Education, Skill, Project, Certification, Training, UserArcData, CVTask
from .db import get_db
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from .auth import get_current_user
import logging
from uuid import UUID, uuid4
import os
from fastapi.responses import FileResponse
import io
from .arc_schemas import ArcData
from .cv_utils import extract_text_from_docx, extract_text_from_pdf, split_cv_by_sections, nlp_chunk_text
from .ai_utils import parse_cv_with_ai_chunk, save_parsed_cv_to_db
from .schemas import ProfileCreate, ProfileUpdate, ProfileOut, WorkExperienceCreate, WorkExperienceUpdate, WorkExperienceOut, EducationCreate, EducationUpdate, EducationOut, SkillCreate, SkillOut, ProjectCreate, ProjectUpdate, ProjectOut, CertificationCreate, CertificationUpdate, CertificationOut, TrainingCreate, TrainingUpdate, Role
from openai import OpenAI
from fastapi.routing import APIRoute

# --- Add OpenAI Assistants API imports ---
import openai

# Utility function to fetch user profile from user service
import httpx

async def get_user_profile(user_id: str, token: str) -> dict:
    url = f"https://api-gw-production.up.railway.app/api/user/profile/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()

# Example usage (in an endpoint):
# profile = await get_user_profile(user_id, token)

router = APIRouter()

@router.get("/cv/status/{task_id}")
def get_cv_status(task_id: UUID, db: Session = Depends(get_db)):
    task = db.query(CVTask).filter_by(id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "taskId": str(task.id),
        "status": task.status,
        "error": task.error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }

# --- OpenAI config (if not already present) ---
logger = logging.getLogger(__name__)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set. AI features will not work correctly.")
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# --- Pydantic models ---
class KeywordRAG(BaseModel):
    keyword: str
    status: str  # "red", "amber", "green"

class KeywordsRequest(BaseModel):
    profile: dict
    job_description: str

class KeywordsResponse(BaseModel):
    keywords: List[str]
    match_percentage: int

class GenerateCVRequest(BaseModel):
    profile: dict
    job_description: str
    keywords: Optional[List[str]] = None

class GenerateCVResponse(BaseModel):
    cv: str
    cover_letter: str
    keywords: Optional[List[KeywordRAG]] = None

class UpdateCVRequest(BaseModel):
    profile: dict
    job_description: str
    additional_keypoints: List[str]
    previous_cv: str

class UpdateCVResponse(BaseModel):
    cv: str
    cover_letter: str

class AssistantActionRequest(BaseModel):
    action: str
    profile: Optional[Dict[str, Any]] = None
    job_description: Optional[str] = None
    keywords: Optional[List[str]] = None
    additional_keypoints: Optional[List[str]] = None
    previous_cv: Optional[str] = None
    thread_id: Optional[str] = None

# --- Profile Endpoints ---
# [REMOVED: All /profiles* endpoints and CVProfile usage as part of refactor]

# --- Work Experience Endpoints ---
@router.post("/users/{user_id}/work_experience", response_model=WorkExperienceOut)
def add_work_experience(user_id: str, data: WorkExperienceCreate, db: Session = Depends(get_db)):
    max_index = db.query(WorkExperience).filter_by(user_id=user_id).order_by(WorkExperience.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = WorkExperience(
        user_id=user_id,
        company=data.company,
        title=data.title,
        start_date=data.start_date,
        end_date=data.end_date,
        description=data.description,
        order_index=order_index
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/users/{user_id}/work_experience", response_model=List[WorkExperienceOut])
def list_work_experience(user_id: str, db: Session = Depends(get_db)):
    entries = db.query(WorkExperience).filter_by(user_id=user_id).order_by(WorkExperience.order_index).all()
    # Ensure id is always a string
    return [
        {**entry.__dict__, "id": str(entry.id)} if not isinstance(entry.id, str) else entry for entry in entries
    ]

@router.get("/work_experience/{id}", response_model=WorkExperienceOut)
def get_work_experience(id: UUID, db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    return entry

@router.put("/work_experience/{id}", response_model=WorkExperienceOut)
def update_work_experience(id: UUID, data: WorkExperienceUpdate, db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    update_data = data.dict(exclude_unset=True)
    desc = update_data.get("description")
    if desc is not None:
        if isinstance(desc, str):
            desc = [line.strip() for line in desc.splitlines() if line.strip()]
        entry.description = desc
        update_data.pop("description")
    for field, value in update_data.items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/work_experience/{id}")
def delete_work_experience(id: UUID, db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = entry.user_id
    order_index = entry.order_index
    db.delete(entry)
    db.commit()
    # Reindex remaining entries
    entries = db.query(WorkExperience).filter(
        WorkExperience.user_id == user_id,
        WorkExperience.order_index > order_index
    ).order_by(WorkExperience.order_index).all()
    for e in entries:
        e.order_index -= 1
    db.commit()
    return {"success": True}

@router.patch("/work_experience/{id}/reorder", response_model=WorkExperienceOut)
def reorder_work_experience(id: UUID, new_order_index: int = Body(...), db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = entry.user_id
    old_index = entry.order_index
    if new_order_index == old_index:
        return entry
    # Shift other entries
    if new_order_index > old_index:
        affected = db.query(WorkExperience).filter(
            WorkExperience.user_id == user_id,
            WorkExperience.order_index > old_index,
            WorkExperience.order_index <= new_order_index
        ).all()
        for e in affected:
            e.order_index -= 1
    else:
        affected = db.query(WorkExperience).filter(
            WorkExperience.user_id == user_id,
            WorkExperience.order_index < old_index,
            WorkExperience.order_index >= new_order_index
        ).all()
        for e in affected:
            e.order_index += 1
    entry.order_index = new_order_index
    db.commit()
    db.refresh(entry)
    return entry

@router.patch("/work_experience/{id}")
def partial_update_work_experience(id: UUID, update: WorkExperienceUpdate, db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    update_data = update.dict(exclude_unset=True)
    desc = update_data.get("description")
    if desc is not None:
        if isinstance(desc, str):
            desc = [line.strip() for line in desc.splitlines() if line.strip()]
        entry.description = desc
        update_data.pop("description")
    for field, value in update_data.items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

# --- Education Endpoints ---
@router.post("/users/{user_id}/education", response_model=EducationOut)
def add_education(user_id: str, data: EducationCreate, db: Session = Depends(get_db)):
    max_index = db.query(Education).filter_by(user_id=user_id).order_by(Education.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = Education(
        user_id=user_id,
        institution=data.institution,
        degree=data.degree,
        field=data.field,
        start_date=data.start_date,
        end_date=data.end_date,
        description=data.description,
        order_index=order_index
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/users/{user_id}/education", response_model=List[EducationOut])
def list_education(user_id: str, db: Session = Depends(get_db)):
    return db.query(Education).filter_by(user_id=user_id).order_by(Education.order_index).all()

@router.get("/education/{id}", response_model=EducationOut)
def get_education(id: int, db: Session = Depends(get_db)):
    entry = db.query(Education).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    return entry

@router.put("/education/{id}", response_model=EducationOut)
def update_education(id: int, data: EducationUpdate, db: Session = Depends(get_db)):
    entry = db.query(Education).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/education/{id}")
def delete_education(id: int, db: Session = Depends(get_db)):
    entry = db.query(Education).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    order_index = entry.order_index
    db.delete(entry)
    db.commit()
    # Reindex remaining entries
    entries = db.query(Education).filter(
        Education.user_id == entry.user_id,
        Education.order_index > order_index
    ).order_by(Education.order_index).all()
    for e in entries:
        e.order_index -= 1
    db.commit()
    return {"success": True}

@router.patch("/education/{id}/reorder", response_model=EducationOut)
def reorder_education(id: int, new_order_index: int = Body(...), db: Session = Depends(get_db)):
    entry = db.query(Education).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = entry.user_id
    old_index = entry.order_index
    if new_order_index == old_index:
        return entry
    # Shift other entries
    if new_order_index > old_index:
        affected = db.query(Education).filter(
            Education.user_id == user_id,
            Education.order_index > old_index,
            Education.order_index <= new_order_index
        ).all()
        for e in affected:
            e.order_index -= 1
    else:
        affected = db.query(Education).filter(
            Education.user_id == user_id,
            Education.order_index < old_index,
            Education.order_index >= new_order_index
        ).all()
        for e in affected:
            e.order_index += 1
    entry.order_index = new_order_index
    db.commit()
    db.refresh(entry)
    return entry

@router.patch("/education/{id}")
def partial_update_education(id: int, update: EducationUpdate, db: Session = Depends(get_db)):
    entry = db.query(Education).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

# --- Skills Endpoints ---
@router.post("/users/{user_id}/skills", response_model=SkillOut)
def add_skill(user_id: str, data: SkillCreate, db: Session = Depends(get_db)):
    entry = Skill(user_id=user_id, skill=data.skill)
    db.add(entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Skill already exists for this profile.")
    db.refresh(entry)
    return entry

@router.get("/users/{user_id}/skills", response_model=List[SkillOut])
def list_skills(user_id: str, db: Session = Depends(get_db)):
    return db.query(Skill).filter_by(user_id=user_id).all()

@router.delete("/skills/{id}")
def delete_skill(id: int, db: Session = Depends(get_db)):
    entry = db.query(Skill).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(entry)
    db.commit()
    return {"success": True}

@router.put("/skills/{id}")
def update_skill(id: int, data: SkillCreate, db: Session = Depends(get_db)):
    entry = db.query(Skill).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    entry.skill = data.skill
    db.commit()
    db.refresh(entry)
    return entry

@router.patch("/skills/{id}")
def partial_update_skill(id: int, update: SkillCreate, db: Session = Depends(get_db)):
    entry = db.query(Skill).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

# --- Projects Endpoints ---
@router.post("/users/{user_id}/projects", response_model=ProjectOut)
def add_project(user_id: str, data: ProjectCreate, db: Session = Depends(get_db)):
    max_index = db.query(Project).filter_by(user_id=user_id).order_by(Project.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = Project(
        user_id=user_id,
        name=data.name,
        description=data.description,
        order_index=order_index
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/users/{user_id}/projects", response_model=List[ProjectOut])
def list_projects(user_id: str, db: Session = Depends(get_db)):
    return db.query(Project).filter_by(user_id=user_id).order_by(Project.order_index).all()

@router.get("/projects/{id}", response_model=ProjectOut)
def get_project(id: int, db: Session = Depends(get_db)):
    entry = db.query(Project).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    return entry

@router.put("/projects/{id}", response_model=ProjectOut)
def update_project(id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    entry = db.query(Project).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/projects/{id}")
def delete_project(id: int, db: Session = Depends(get_db)):
    entry = db.query(Project).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    order_index = entry.order_index
    db.delete(entry)
    db.commit()
    # Reindex remaining entries
    entries = db.query(Project).filter(
        Project.user_id == entry.user_id,
        Project.order_index > order_index
    ).order_by(Project.order_index).all()
    for e in entries:
        e.order_index -= 1
    db.commit()
    return {"success": True}

@router.patch("/projects/{id}/reorder", response_model=ProjectOut)
def reorder_project(id: int, new_order_index: int = Body(...), db: Session = Depends(get_db)):
    entry = db.query(Project).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = entry.user_id
    old_index = entry.order_index
    if new_order_index == old_index:
        return entry
    # Shift other entries
    if new_order_index > old_index:
        affected = db.query(Project).filter(
            Project.user_id == user_id,
            Project.order_index > old_index,
            Project.order_index <= new_order_index
        ).all()
        for e in affected:
            e.order_index -= 1
    else:
        affected = db.query(Project).filter(
            Project.user_id == user_id,
            Project.order_index < old_index,
            Project.order_index >= new_order_index
        ).all()
        for e in affected:
            e.order_index += 1
    entry.order_index = new_order_index
    db.commit()
    db.refresh(entry)
    return entry

@router.patch("/projects/{id}")
def partial_update_project(id: int, update: ProjectUpdate, db: Session = Depends(get_db)):
    entry = db.query(Project).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

# --- Certifications Endpoints ---
@router.post("/users/{user_id}/certifications", response_model=CertificationOut)
def add_certification(user_id: str, data: CertificationCreate, db: Session = Depends(get_db)):
    max_index = db.query(Certification).filter_by(user_id=user_id).order_by(Certification.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = Certification(
        user_id=user_id,
        name=data.name,
        issuer=data.issuer,
        year=data.year,
        order_index=order_index
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/users/{user_id}/certifications", response_model=List[CertificationOut])
def list_certifications(user_id: str, db: Session = Depends(get_db)):
    return db.query(Certification).filter_by(user_id=user_id).order_by(Certification.order_index).all()

@router.get("/certifications/{id}", response_model=CertificationOut)
def get_certification(id: int, db: Session = Depends(get_db)):
    entry = db.query(Certification).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    return entry

@router.put("/certifications/{id}", response_model=CertificationOut)
def update_certification(id: int, data: CertificationUpdate, db: Session = Depends(get_db)):
    entry = db.query(Certification).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/certifications/{id}")
def delete_certification(id: int, db: Session = Depends(get_db)):
    entry = db.query(Certification).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    order_index = entry.order_index
    db.delete(entry)
    db.commit()
    # Reindex remaining entries
    entries = db.query(Certification).filter(
        Certification.user_id == entry.user_id,
        Certification.order_index > order_index
    ).order_by(Certification.order_index).all()
    for e in entries:
        e.order_index -= 1
    db.commit()
    return {"success": True}

@router.patch("/certifications/{id}/reorder", response_model=CertificationOut)
def reorder_certification(id: int, new_order_index: int = Body(...), db: Session = Depends(get_db)):
    entry = db.query(Certification).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    user_id = entry.user_id
    old_index = entry.order_index
    if new_order_index == old_index:
        return entry
    # Shift other entries
    if new_order_index > old_index:
        affected = db.query(Certification).filter(
            Certification.user_id == user_id,
            Certification.order_index > old_index,
            Certification.order_index <= new_order_index
        ).all()
        for e in affected:
            e.order_index -= 1
    else:
        affected = db.query(Certification).filter(
            Certification.user_id == user_id,
            Certification.order_index < old_index,
            Certification.order_index >= new_order_index
        ).all()
        for e in affected:
            e.order_index += 1
    entry.order_index = new_order_index
    db.commit()
    db.refresh(entry)
    return entry

@router.patch("/certifications/{id}")
def partial_update_certification(id: int, update: CertificationUpdate, db: Session = Depends(get_db)):
    entry = db.query(Certification).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/profiles/{profile_id}/all_sections")
def get_all_sections(profile_id: UUID, db: Session = Depends(get_db)):
    # Fetch all sections for the given profile_id
    def parse_date(date_str):
        if not date_str:
            return 0
        if date_str.strip().lower() == "present":
            return float('inf')
        for fmt in ("%b %Y", "%Y"):
            try:
                return datetime.strptime(date_str, fmt).timestamp()
            except Exception:
                continue
        return 0
    work_experience = db.query(WorkExperience).filter_by(user_id=profile_id).all()
    # Sort work_experience by end_date descending ("Present" most recent)
    work_experience_sorted = sorted(
        work_experience,
        key=lambda x: parse_date(x.end_date),
        reverse=True
    )
    education = db.query(Education).filter_by(user_id=profile_id).order_by(Education.order_index).all()
    skills = db.query(Skill).filter_by(user_id=profile_id).order_by(Skill.id).all()
    projects = db.query(Project).filter_by(user_id=profile_id).order_by(Project.order_index).all()
    certifications = db.query(Certification).filter_by(user_id=profile_id).order_by(Certification.order_index).all()
    return {
        "work_experience": [
            {
                "id": str(x.id),
                "company": x.company,
                "title": x.title,
                "start_date": x.start_date,
                "end_date": x.end_date,
                "description": x.description,
                "order_index": x.order_index
            } for x in work_experience_sorted
        ],
        "education": [
            {
                "id": str(x.id),
                "institution": x.institution,
                "degree": x.degree,
                "field": x.field,
                "start_date": x.start_date,
                "end_date": x.end_date,
                "description": x.description,
                "order_index": x.order_index
            } for x in education
        ],
        "skills": [
            {
                "id": str(x.id),
                "skill": x.skill
            } for x in skills
        ],
        "projects": [
            {
                "id": str(x.id),
                "name": x.name,
                "description": x.description,
                "order_index": x.order_index
            } for x in projects
        ],
        "certifications": [
            {
                "id": str(x.id),
                "name": x.name,
                "issuer": x.issuer,
                "year": x.year,
                "order_index": x.order_index
            } for x in certifications
        ]
    }

# --- Generate Assistant Endpoint ---
from fastapi import Request

@router.post("/generate-assistant")
async def generate_assistant(request: Request):
    """
    Generate a tailored CV and cover letter or extract keywords using OpenAI Assistant API, following strict output requirements.
    Accepts: {"action": "generate_cv"|"extract_keywords", "profile": {...}, "job_description": "...", "keywords": [...], "cv_length": "...", "thread_id": "..."}
    Returns: {"cv": "...", "cover_letter": "...", "job_title": "...", "company_name": "..."} or {"keywords": [...], "thread_id": "..."}
    """
    try:
        data = await request.json()
        action = data.get("action", "generate_cv")
        thread_id = data.get("thread_id")
        profile = data.get("profile")
        job_description = data.get("job_description")
        keywords = data.get("keywords")
        cv_length = data.get("cv_length")
        additional_keypoints = data.get("additional_keypoints")
        previous_cv = data.get("previous_cv")
        num_pages = data.get("numPages")
        language = data.get("language")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
        if not OPENAI_API_KEY:
            return {"error": "OpenAI API key not set"}
        if not OPENAI_ASSISTANT_ID:
            return {"error": "OpenAI Assistant ID not set"}
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        import time
        import json
        # --- Thread-aware keyword extraction ---
        if action == "extract_keywords" and thread_id:
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content="Extract the most important keywords from my profile and this job description for tailoring my application."
            )
            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=OPENAI_ASSISTANT_ID
            )
            for _ in range(180):
                run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
                if run_status.status in ("completed", "failed", "cancelled", "expired"):
                    break
                time.sleep(1)
            if run_status.status != "completed":
                return {"error": f"Assistant run did not complete: {run_status.status}"}
            messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
            if not messages.data:
                return {"error": "No response from assistant"}
            content = messages.data[0].content[0].text.value
            try:
                content_json = json.loads(content)
                keywords = content_json.get("keywords", [])
            except Exception as e:
                return {"error": f"Assistant response is not valid JSON: {str(e)}", "raw": content}
            return {"keywords": keywords, "thread_id": thread_id}
        # --- Thread-aware update_cv (apply keypoints and full CV structure) ---
        if action == "update_cv" and thread_id:
            # Compose the message content with full CV structure
            message_content = {
                "cv_keypoints": data.get("cv_keypoints"),
                "cover_letter_keypoints": data.get("cover_letter_keypoints"),
                "cv_length": data.get("cv_length"),
                "experience": data.get("experience"),
                "education": data.get("education"),
                "skills": data.get("skills"),
                "summary": data.get("summary"),
                "core_competencies": data.get("core_competencies"),
                "certifications": data.get("certifications"),
                "cover_letter": data.get("cover_letter"),
            }
            logger.info(f"[DEBUG] Adding full CV structure to thread {thread_id}: {json.dumps(message_content)[:500]} ... (truncated)")
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=json.dumps(message_content)
            )
            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=OPENAI_ASSISTANT_ID
            )
            for _ in range(180):
                run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
                if run_status.status in ("completed", "failed", "cancelled", "expired"):
                    break
                time.sleep(1)
            if run_status.status != "completed":
                return {"error": f"Assistant run did not complete: {run_status.status}"}
            messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
            if not messages.data:
                return {"error": "No response from assistant"}
            raw_content = messages.data[0].content[0].text.value
            logger.info(f"[DEBUG] Raw latest thread message: {raw_content[:500]} ... (truncated)")
            try:
                cv_data = json.loads(raw_content)
            except Exception as e:
                logger.error(f"[ERROR] Failed to parse latest thread message as JSON: {e}")
                return {"error": "Failed to parse thread message as JSON", "raw": raw_content}
            logger.info(f"[DEBUG] Parsed payload for /api/cv/generate-docx: {json.dumps(cv_data)[:500]} ... (truncated)")
            # Here you would POST cv_data to /api/cv/generate-docx (if this is the place)
            cv_data["thread_id"] = thread_id
            return cv_data
        # --- Thread-aware CV & cover letter generation ---
        # Always include profile and job_description in the payload, even for follow-up requests
        if action == "generate_cv":
            user_message = {
                "action": action,
                "profile": profile,
                "job_description": job_description
            }
            if keywords:
                user_message["keywords"] = keywords
            if cv_length:
                user_message["cv_length"] = cv_length
            if additional_keypoints:
                user_message["additional_keypoints"] = additional_keypoints
            if previous_cv:
                user_message["previous_cv"] = previous_cv
            if num_pages is not None:
                user_message["numPages"] = num_pages
            if language is not None:
                user_message["language"] = language
            import json
            logger.info(f"[OPENAI PAYLOAD] Sending to OpenAI: {json.dumps(user_message)}")
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=json.dumps(user_message)
            )
            run = client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=OPENAI_ASSISTANT_ID
            )
            for _ in range(180):
                run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
                if run_status.status in ("completed", "failed", "cancelled", "expired"):
                    break
                time.sleep(1)
            if run_status.status != "completed":
                return {"error": f"Assistant run did not complete: {run_status.status}"}
            messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
            if not messages.data:
                return {"error": "No response from assistant"}
            content = messages.data[0].content[0].text.value
            try:
                content_json = json.loads(content)
            except Exception as e:
                return {"error": f"Assistant response is not valid JSON: {str(e)}", "raw": content}
            content_json["thread_id"] = thread_id
            return content_json
        # --- Default: create thread and send full context ---
        user_message = {
            "action": action,
            "profile": profile,
            "job_description": job_description
        }
        if keywords:
            user_message["keywords"] = keywords
        if cv_length:
            user_message["cv_length"] = cv_length
        if additional_keypoints:
            user_message["additional_keypoints"] = additional_keypoints
        if previous_cv:
            user_message["previous_cv"] = previous_cv
        if num_pages is not None:
            user_message["numPages"] = num_pages
        if language is not None:
            user_message["language"] = language
        import json
        logger.info(f"[OPENAI PAYLOAD] Sending to OpenAI: {json.dumps(user_message)}")
        # If no thread_id, create a new thread (first request)
        if not thread_id:
            thread = client.beta.threads.create()
            thread_id = thread.id
        # Now always have a valid thread_id
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=json.dumps(user_message)  # Send as proper JSON
        )
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=OPENAI_ASSISTANT_ID
        )
        # For import assistant, use 300 seconds
        for _ in range(300):
            run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            if run_status.status in ("completed", "failed", "cancelled", "expired"):
                break
            time.sleep(1)
        if run_status.status != "completed":
            return {"error": f"Assistant run did not complete: {run_status.status}"}
        messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
        if not messages.data:
            return {"error": "No response from assistant"}
        content = messages.data[0].content[0].text.value
        try:
            content_json = json.loads(content)
        except Exception as e:
            return {"error": f"Assistant response is not valid JSON: {str(e)}", "raw": content}
        content_json["thread_id"] = thread_id
        return content_json
    except Exception as e:
        logger.error(f"[ERROR] Error in generate_assistant: {str(e)}")
        return {"error": f"Error generating CV: {str(e)}"}

import tempfile
from .assistant_manager import CVAssistantManager
from slowapi import Limiter
from slowapi.util import get_remote_address
import pyclamd

limiter = Limiter(key_func=get_remote_address)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain"
}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

def get_mime_type(filename):
    import mimetypes
    mime, _ = mimetypes.guess_type(filename)
    return mime

async def validate_upload(file: UploadFile):
    # Check MIME type
    mime_type = file.content_type or get_mime_type(file.filename)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")
    # Save to temp file for scanning
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    # --- Malware scan temporarily disabled for production ---
    # try:
    #     cd = pyclamd.ClamdUnixSocket()
    #     result = cd.scan_file(tmp_path)
    #     if result:
    #         raise HTTPException(status_code=400, detail="Malware detected in uploaded file")
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Malware scan failed: {e}")
    return contents, tmp_path

@router.post("/importassistant")
@limiter.limit("5/minute")
async def import_cv_assistant(
    request: Request,  # Required for SlowAPI
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import a CV file, extract its text, send it to the OpenAI Assistant for parsing, persist to DB, and return structured JSON.
    """
    # 1. Validate and scan upload
    contents, tmp_path = await validate_upload(file)
    # 2. Extract text from file (support PDF, DOCX, TXT)
    ext = file.filename.split('.')[-1].lower()
    if ext == "pdf":
        import pdfplumber
        with pdfplumber.open(tmp_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif ext in ("docx", "doc"):
        from docx import Document
        doc = Document(tmp_path)
        text = "\n".join([p.text for p in doc.paragraphs])
    elif ext == "txt":
        text = contents.decode("utf-8", errors="ignore")
    else:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF, DOCX, and TXT are supported.")
    os.unlink(tmp_path)
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the file.")
    # 3. Process with OpenAI Assistant
    try:
        from .assistant_manager import CVAssistantManager
        assistant = CVAssistantManager()
        parsed_data = assistant.process_cv(text)
        save_parsed_cv_to_db(parsed_data, user_id, db)
        return {"success": True, "data": parsed_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV processing failed: {e}")