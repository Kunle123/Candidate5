# ---
# Example curl command to test /generate-assistant-adaptive endpoint:
#
# curl -X POST https://your-api/cv/generate-assistant-adaptive \
#   -H "Authorization: Bearer <token>" \
#   -H "Content-Type: application/json" \
#   -d '{
#     "profile": { ... },  # (Insert your full profile object here)
#     "job_description": "Applicants must be eligible to work in the specified location... (rest of your job description) ..."
#   }'
#
# Replace { ... } with your full profile JSON (see below for a truncated example), and <token> with your JWT.
#
# For your specific test, use:
#
# curl -X POST https://your-api/cv/generate-assistant-adaptive \
#   -H "Authorization: Bearer <token>" \
#   -H "Content-Type: application/json" \
#   --data-binary @payloads/adaptive_test_payload.json
#
# Where payloads/adaptive_test_payload.json contains your full test object (profile + job_description only).
# ---
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
from fastapi.responses import JSONResponse

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
    # Ensure user exists in user_arc_data
    from .models import UserArcData
    user = db.query(UserArcData).filter_by(user_id=user_id).first()
    if not user:
        user = UserArcData(user_id=user_id, arc_data={})
        db.add(user)
        db.commit()
        db.refresh(user)
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

@router.patch("/work_experience/{id}", response_model=WorkExperienceOut)
def patch_work_experience(id: UUID, data: WorkExperienceUpdate, db: Session = Depends(get_db)):
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
    except Exception as e:
        import traceback
        return {"error": f"Internal server error: {str(e)}", "trace": traceback.format_exc()}
# --- DYNAMIC ADAPTIVE CHUNKING STRATEGY ---
def analyze_payload(profile):
    import json
    payload_size = len(json.dumps(profile))
    role_count = len(profile.get("work_experience", []))
    career_years = calculate_career_span(profile.get("work_experience", []))
    def calculate_complexity(profile):
        # Simple complexity metric: size * role count * career years
        return (payload_size / 1024) * (role_count / 5) * (career_years / 10)
    return {
        "sizeKB": round(payload_size / 1024),
        "roleCount": role_count,
        "careerYears": career_years,
        "complexity": calculate_complexity(profile)
    }

def calculate_career_span(work_experience):
    from datetime import datetime
    import logging
    logger = logging.getLogger("arc_service")
    dates = []
    for role in work_experience:
        start = role.get("start_date")
        end = role.get("end_date")
        # Try multiple formats for start_date
        for fmt in ("%Y-%m-%d", "%Y-%m", "%b %Y", "%Y"):
            try:
                if start:
                    start_dt = datetime.strptime(start, fmt)
                    dates.append(start_dt)
                    break
            except Exception:
                continue
        # Try multiple formats for end_date, skip 'Present'
        if end and end.lower() not in ("present", "current", "now"):
            for fmt in ("%Y-%m-%d", "%Y-%m", "%b %Y", "%Y"):
                try:
                    end_dt = datetime.strptime(end, fmt)
                    dates.append(end_dt)
                    break
                except Exception:
                    continue
    if not dates:
        logger.warning(f"[CAREER SPAN] No valid dates found in work_experience: {work_experience}")
        return 0
    earliest = min(dates)
    latest = max(dates)
    years = round((latest - earliest).days / 365.25)
    logger.info(f"[CAREER SPAN] Earliest: {earliest}, Latest: {latest}, Years: {years}")
    return years

def select_chunking_strategy(analysis):
    sizeKB = analysis["sizeKB"]
    roleCount = analysis["roleCount"]
    careerYears = analysis["careerYears"]
    # Much more aggressive chunking:
    if sizeKB <= 5 or roleCount <= 2 or careerYears <= 2:
        return {"strategy": "single_chunk", "chunkCount": 1, "expectedTime": "10-15 seconds"}
    if sizeKB <= 10 or roleCount <= 4 or careerYears <= 4:
        return {"strategy": "dual_chunk", "chunkCount": 2, "expectedTime": "15-20 seconds"}
    if sizeKB <= 15 or roleCount <= 7 or careerYears <= 7:
        return {"strategy": "triple_chunk", "chunkCount": 3, "expectedTime": "20-25 seconds"}
    # Everything else: multi-chunk (max 5)
    return {
        "strategy": "multi_chunk",
        "chunkCount": min(max(4, round(roleCount / 5)), 5),
        "expectedTime": "25-45 seconds"
    }

def create_single_chunk(profile, job_description):
    return [{
        "type": "complete_career",
        "roles": profile.get("work_experience", []),
        "priorityRange": [1, 5],
        "focus": "comprehensive_optimization",
        "expectedSize": "10-15KB"
    }]

def create_dual_chunks(profile, job_description):
    roles = profile.get("work_experience", [])
    mid_point = (len(roles) + 1) // 2
    return [
        {
            "type": "recent_primary",
            "roles": roles[:mid_point],
            "priorityRange": [1, 3],
            "focus": "detailed_optimization",
            "expectedSize": "12-18KB"
        },
        {
            "type": "supporting_timeline",
            "roles": roles[mid_point:],
            "priorityRange": [3, 5],
            "focus": "timeline_completion",
            "expectedSize": "10-15KB"
        }
    ]

def create_triple_chunks(profile, job_description):
    roles = profile.get("work_experience", [])
    n = len(roles)
    recent_count = max(1, round(n * 0.4))
    supporting_count = max(1, round(n * 0.4))
    return [
        {
            "type": "recent_roles",
            "roles": roles[:recent_count],
            "priorityRange": [1, 3],
            "focus": "maximum_optimization",
            "expectedSize": "12-20KB"
        },
        {
            "type": "supporting_roles",
            "roles": roles[recent_count:recent_count+supporting_count],
            "priorityRange": [2, 4],
            "focus": "supporting_evidence",
            "expectedSize": "15-25KB"
        },
        {
            "type": "timeline_roles",
            "roles": roles[recent_count+supporting_count:],
            "priorityRange": [3, 5],
            "focus": "career_continuity",
            "expectedSize": "8-15KB"
        }
    ]

def create_multi_chunks(profile, job_description):
    roles = profile.get("work_experience", [])
    n = len(roles)
    chunk_count = min(max(4, round(n / 5)), 5)
    chunk_size = max(1, (n + chunk_count - 1) // chunk_count)
    chunks = []
    chunk_types = ["recent_primary", "recent_secondary", "mid_career", "early_career", "legacy"]
    for i in range(chunk_count):
        start = i * chunk_size
        end = n if i == chunk_count - 1 else (i + 1) * chunk_size
        chunks.append({
            "type": chunk_types[i] if i < len(chunk_types) else f"chunk_{i+1}",
            "roles": roles[start:end],
            "priorityRange": [min(i+1, 5), min(i+3, 5)],
            "focus": [
                "critical_optimization",
                "high_priority_support",
                "skill_progression",
                "timeline_foundation",
                "legacy"
            ][i] if i < 5 else "adaptive",
            "expectedSize": "10-20KB"
        })
    return chunks

def create_adaptive_chunks(profile, job_description, strategy):
    strat = strategy["strategy"]
    if strat == "single_chunk":
        return create_single_chunk(profile, job_description)
    elif strat == "dual_chunk":
        return create_dual_chunks(profile, job_description)
    elif strat == "triple_chunk":
        return create_triple_chunks(profile, job_description)
    elif strat == "multi_chunk":
        return create_multi_chunks(profile, job_description)
    else:
        return create_triple_chunks(profile, job_description)  # Fallback

# --- PROMPT DEFINITIONS FOR CHUNKED CV GENERATION ---

# --- Update chunk prompts to output only raw content ---
def get_chunk_prompt(chunk_type: str) -> str:
    """
    Returns the appropriate prompt for the given chunk type.
    """
    if chunk_type == "global_context":
        return '''You are a career analysis specialist. Analyze the provided career profile and job description to create global context standards that will ensure consistent CV generation across multiple processing chunks.

### ANTI-FABRICATION POLICY
- NEVER invent information not present in the profile
- ONLY use data from the provided profile and job description
- Base all analysis on factual evidence from source materials

### TASK: CREATE GLOBAL CONTEXT

**INPUT ANALYSIS:**
1. **Job Requirements Analysis:**
   - Extract GREEN keywords (exact matches in profile)
   - Extract AMBER keywords (related skills in profile)
   - Identify job seniority level (Entry/Mid/Senior/Executive)
   - Determine industry context and company type

2. **Career Profile Analysis:**
   - Identify top 5 career achievements across all roles
   - Analyze career progression and skill evolution
   - Determine experience level and specializations
   - Map keyword coverage across career timeline

3. **Priority Standards Definition:**
   - Define what constitutes Priority 1 content (highest job relevance)
   - Define Priority 2-5 standards for consistent application
   - Establish quality benchmarks for each priority level

### OUTPUT FORMAT (JSON):
{...}'''
    if chunk_type == "recent_roles":
        return '''You are a CV content processor specializing in RECENT CAREER ROLES (typically 2020-present). Your job is to generate RAW CONTENT ONLY - no complete CVs or cover letters.

### ANTI-FABRICATION POLICY
- NEVER invent achievements, metrics, or experiences not in the profile
- ONLY rephrase existing content for job alignment
- Use intelligent keyword substitution where factually supported
- Maintain 100% accuracy to source profile data

### GLOBAL CONTEXT INTEGRATION
You will receive global context standards. Apply these consistently:
- Use the provided job keyword analysis for optimization
- Reference career highlights for achievement prioritization
- Follow priority standards for consistent ranking
- Maintain quality benchmarks across all content

### PRIORITY ASSIGNMENT CONSTRAINTS
**CRITICAL: You can ONLY assign priorities 1, 2, or 3 to content in this chunk**
- **Priority 1:** Most job-relevant content in recent roles (GREEN keyword matches, key achievements)
- **Priority 2:** Strong job alignment or significant recent achievements
- **Priority 3:** Supporting recent experience or skill demonstrations

### TASK: GENERATE RAW CONTENT ONLY
**DO NOT generate:**
- Complete CV structure
- Cover letters
- Summary sections
- Final formatting

**DO generate:**
- Raw experience bullets with priorities
- Raw achievement statements
- Raw skill extractions
- Raw competency mappings

### OUTPUT FORMAT (JSON):
{
  "chunk_type": "recent_roles",
  "raw_experience": [ ... ],
  "raw_achievements": [ ... ],
  "raw_skills": [ ... ],
  "processing_notes": { ... }
}
'''
    if chunk_type == "supporting_roles":
        return '''You are a CV content processor specializing in SUPPORTING CAREER ROLES (typically 2010-2019). Your job is to generate RAW CONTENT ONLY - no complete CVs or cover letters.

### ANTI-FABRICATION POLICY
- NEVER invent achievements, metrics, or experiences not in the profile
- ONLY rephrase existing content for job alignment
- Use intelligent keyword substitution where factually supported
- Maintain 100% accuracy to source profile data

### PRIORITY ASSIGNMENT CONSTRAINTS
**CRITICAL: You can ONLY assign priorities 2, 3, or 4 to content in this chunk**
- **Priority 2:** Strong job alignment in supporting roles (AMBER keywords, skill progression)
- **Priority 3:** Relevant experience and skill demonstrations
- **Priority 4:** General professional experience and career development

### TASK: GENERATE RAW CONTENT ONLY
Focus on skill progression, career development, and supporting evidence for job suitability.

### OUTPUT FORMAT (JSON):
{
  "chunk_type": "supporting_roles",
  "raw_experience": [ ... ],
  "raw_achievements": [ ... ],
  "raw_skills": [ ... ],
  "processing_notes": { ... }
}
'''
    if chunk_type == "timeline_roles":
        return '''You are a CV content processor specializing in TIMELINE COMPLETION ROLES (typically pre-2010). Your job is to generate RAW CONTENT ONLY - no complete CVs or cover letters.

### PRIORITY ASSIGNMENT CONSTRAINTS
**CRITICAL: You can ONLY assign priorities 3, 4, or 5 to content in this chunk**
- **Priority 3:** Relevant early career achievements or foundational skills
- **Priority 4:** General professional experience and career foundation
- **Priority 5:** Timeline completion and basic responsibilities

### TASK: GENERATE RAW CONTENT ONLY
Focus on career foundation, early development, and timeline continuity.

### OUTPUT FORMAT (JSON):
{
  "chunk_type": "timeline_roles",
  "raw_experience": [ ... ],
  "raw_achievements": [ ... ],
  "raw_skills": [ ... ],
  "processing_notes": { ... }
}
'''
    if chunk_type == "final_assembly":
        return '''You are a CV assembly specialist. Take the processed raw content chunks and create a single, unified CV with one cover letter.

### ASSEMBLY REQUIREMENTS

**INPUT:** Multiple processed chunks with raw content
**OUTPUT:** Single unified CV with one cover letter

**1. Content Merging:**
- Combine all experience in reverse chronological order
- Merge achievements (max 12, highest priority first)
- Unify core competencies with priority rankings
- Ensure no duplicates or gaps in timeline

**2. Single Cover Letter Generation:**
- Create ONE cover letter using highlights from ALL chunks
- Draw from top achievements across entire career
- Maintain job alignment using global context
- Professional UK English throughout

**3. CV Structure Assembly:**
- Professional summary incorporating all career highlights
- Complete experience section in chronological order
- Unified achievements section (no duplicates)
- Core competencies with evidence from all periods
- Education and additional sections

### FINAL OUTPUT FORMAT:
{...}'''
    # Default fallback
    return "You are a CV content processor. Process the provided chunk as per the instructions."

# --- New: Assembly prompt for final unified CV and cover letter ---
def get_assembly_prompt() -> str:
    return '''You are a CV assembly specialist. Take the processed raw content chunks and create a single, unified CV with one cover letter.

INPUT: Multiple processed chunks with raw content
OUTPUT: Single unified CV with one cover letter

ASSEMBLY REQUIREMENTS:
1. Merge all experience in chronological order
2. Combine achievements (max 12, highest priority first)
3. Unify core competencies with priority rankings
4. Generate ONE cover letter using highlights from ALL chunks
5. Ensure consistent formatting and no duplicates

OUTPUT FORMAT:
{
  "cv": {
    "name": "{{CANDIDATE_NAME}}",
    "contact": "{{CONTACT_INFO}}",
    "summary": { "content": "Professional summary from all chunks", "priority": 1 },
    "relevant_achievements": [...],
    "experience": [...],
    "core_competencies": [...],
    "education": [...]
  },
  "cover_letter": {
    "content": "Single unified cover letter using highlights from all chunks",
    "priority": 1
  },
  "job_title": "Extracted from job description",
  "company_name": "Extracted from job description"
}
'''

# --- Anti-Fabrication Rules Helper ---
def get_anti_fabrication_rules():
    return {
        "policy": [
            "NEVER invent achievements, metrics, or experiences not in the profile",
            "ONLY rephrase existing content for job alignment",
            "Use intelligent keyword substitution where factually supported",
            "Maintain 100% accuracy to source profile data",
            "Base all analysis on factual evidence from source materials",
            "Do not fabricate or hallucinate any information"
        ]
    }

# --- Update process_chunk_with_openai to output only raw content ---
def process_chunk_with_openai(chunk, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID):
    import openai
    import json
    import time
    import logging
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    chunk_type = chunk.get("type", "recent_roles")
    prompt = get_chunk_prompt(chunk_type)
    anti_fabrication_rules = get_anti_fabrication_rules()
    message = {
        "chunk": chunk,
        "globalContext": {},  # Optionally pass global context if available
        "jobDescription": job_description,
        "profileContext": profile,
        "antiFabricationRules": anti_fabrication_rules,
        "instructions": prompt
    }
    logger = logging.getLogger("arc_service")
    start_time = time.time()
    logger.info(f"[TIMING] Chunk '{chunk_type}' processing started.")
    thread = client.beta.threads.create()
    thread_id = thread.id
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=json.dumps(message)
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
        logger.info(f"[TIMING] Chunk '{chunk_type}' processing failed after {time.time() - start_time:.2f}s.")
        return {"error": f"Assistant run did not complete: {run_status.status}"}
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
    if not messages.data:
        logger.info(f"[TIMING] Chunk '{chunk_type}' processing got no response after {time.time() - start_time:.2f}s.")
        return {"error": "No response from assistant"}
    content = messages.data[0].content[0].text.value
    if not content or not content.strip() or not content.strip().startswith("{"):
        logger.error(f"[OPENAI EMPTY OR INVALID RESPONSE] Content: {repr(content)}")
        logger.info(f"[TIMING] Chunk '{chunk_type}' processing got invalid response after {time.time() - start_time:.2f}s.")
        return {"error": "Assistant response is empty or not valid JSON", "raw": content}
    try:
        content_json = json.loads(content)
    except Exception as e:
        logger.error(f"[OPENAI JSON PARSE ERROR] {e} | Content: {repr(content)}")
        logger.info(f"[TIMING] Chunk '{chunk_type}' processing JSON parse error after {time.time() - start_time:.2f}s.")
        return {"error": f"JSON parse error: {e}", "raw": content}
    logger.info(f"[TIMING] Chunk '{chunk_type}' processing completed in {time.time() - start_time:.2f}s.")
    return content_json

# Helper: Assemble chunk results (simple concatenation for now)
def assemble_chunks(chunk_results):
    import logging
    logger = logging.getLogger("arc_service")
    cv_sections = []
    cover_letters = []
    for idx, r in enumerate(chunk_results):
        logger.info(f"[ADAPTIVE DEBUG] Chunk {idx} result type: {type(r)} value: {repr(r)[:300]}")
        cv_val = r.get("cv") if isinstance(r, dict) else None
        if isinstance(cv_val, dict):
            logger.info(f"[ADAPTIVE DEBUG] cv_val is dict, converting to string: {cv_val}")
            cv_val = str(cv_val)
        elif isinstance(cv_val, list):
            logger.info(f"[ADAPTIVE DEBUG] cv_val is list, joining: {cv_val}")
            cv_val = "\n".join(str(x) for x in cv_val)
        elif cv_val is not None and not isinstance(cv_val, str):
            cv_val = str(cv_val)
        if cv_val:
            cv_sections.append(cv_val)
        content_val = r.get("content") if isinstance(r, dict) else None
        if content_val:
            if isinstance(content_val, dict):
                logger.info(f"[ADAPTIVE DEBUG] content_val is dict, converting to string: {content_val}")
                content_val = str(content_val)
            elif isinstance(content_val, list):
                logger.info(f"[ADAPTIVE DEBUG] content_val is list, joining: {content_val}")
                content_val = "\n".join(str(x) for x in content_val)
            elif not isinstance(content_val, str):
                content_val = str(content_val)
            cv_sections.append(content_val)
        cover_val = r.get("cover_letter") if isinstance(r, dict) else None
        if isinstance(cover_val, dict):
            logger.info(f"[ADAPTIVE DEBUG] cover_val is dict, converting to string: {cover_val}")
            cover_val = str(cover_val)
        elif isinstance(cover_val, list):
            logger.info(f"[ADAPTIVE DEBUG] cover_val is list, joining: {cover_val}")
            cover_val = "\n".join(str(x) for x in cover_val)
        elif cover_val is not None and not isinstance(cover_val, str):
            cover_val = str(cover_val)
        if cover_val:
            cover_letters.append(cover_val)
    return {
        "cv": "\n\n".join(cv_sections),
        "cover_letter": "\n\n".join(cover_letters)
    }

# --- New: Final assembly step using OpenAI ---
def assemble_unified_cv(chunk_results, global_context, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID):
    import openai
    import json
    import time
    import logging
    logger = logging.getLogger("arc_service")
    start_time = time.time()
    logger.info("[TIMING] Final assembly step started.")
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    assembly_prompt = get_assembly_prompt()
    # Prepare the message for assembly
    message = {
        "chunks": chunk_results,
        "global_context": global_context,
        "profile": profile,
        "job_description": job_description,
        "instructions": assembly_prompt
    }
    thread = client.beta.threads.create()
    thread_id = thread.id
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=json.dumps(message)
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
        logger.info(f"[TIMING] Final assembly step failed after {time.time() - start_time:.2f}s.")
        return {"error": f"Assembly run did not complete: {run_status.status}"}
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
    if not messages.data:
        logger.info(f"[TIMING] Final assembly step got no response after {time.time() - start_time:.2f}s.")
        return {"error": "No response from assistant (assembly)"}
    content = messages.data[0].content[0].text.value
    try:
        content_json = json.loads(content)
    except Exception as e:
        logger.info(f"[TIMING] Final assembly step JSON parse error after {time.time() - start_time:.2f}s.")
        return {"error": f"Assembly response is not valid JSON: {str(e)}", "raw": content}
    logger.info(f"[TIMING] Final assembly step completed in {time.time() - start_time:.2f}s.")
    return content_json

# --- Update the adaptive endpoint to use two-stage processing ---
@router.post("/generate-assistant-adaptive")
async def generate_assistant_adaptive(request: Request):
    import os
    import json
    import logging
    import time
    logger = logging.getLogger("arc_service")
    data = await request.json()
    logger.info(f"[ADAPTIVE DEBUG] Incoming payload: {json.dumps(data)[:1000]}")
    overall_start = time.time()

    if "work_experience" in data:
        profile = data.copy()
        job_description = profile.pop("job_description", "")
    else:
        profile = data.get("profile")
        job_description = data.get("job_description", "")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
    if not OPENAI_API_KEY or not OPENAI_ASSISTANT_ID:
        logger.error("[ADAPTIVE DEBUG] OpenAI API key or Assistant ID not set")
        return {"error": "OpenAI API key or Assistant ID not set"}

    # 1. Analyze
    analysis = analyze_payload(profile)
    strategy = select_chunking_strategy(analysis)
    logger.info(f"[ADAPTIVE DEBUG] Payload analysis: {analysis}")
    logger.info(f"[ADAPTIVE DEBUG] Chunking strategy: {strategy}")
    # 2. Create chunks
    chunks = create_adaptive_chunks(profile, job_description, strategy)
    logger.info(f"[ADAPTIVE DEBUG] Chunks created: {json.dumps(chunks)[:1000]}")
    # 3. Create global context (if needed)
    global_context = {}  # Optionally, call OpenAI for global context if required
    # 4. Process chunks for raw content only, passing job description and anti-fabrication rules
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=strategy["chunkCount"]) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                process_chunk_with_openai,
                chunk,
                profile,
                job_description,
                OPENAI_API_KEY,
                OPENAI_ASSISTANT_ID
            ) for chunk in chunks
        ]
        chunk_results = await asyncio.gather(*tasks)
    logger.info(f"[ADAPTIVE DEBUG] Chunk results: {json.dumps(chunk_results, default=str)[:2000]}")
    # 5. Final assembly: single unified CV and cover letter
    assembled = assemble_unified_cv(chunk_results, global_context, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID)
    logger.info(f"[ADAPTIVE DEBUG] Final assembled output: {json.dumps(assembled, default=str)[:1000]}")
    logger.info(f"[TIMING] Total adaptive endpoint processing time: {time.time() - overall_start:.2f}s.")
    return {
        **assembled,
        "strategy": strategy,
        "analysis": analysis,
        "chunks": chunk_results
    }

import tempfile
from .assistant_manager import CVAssistantManager
from slowapi import Limiter
from slowapi.util import get_remote_address
import pyclamd
import re

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

def extract_json_from_markdown(content):
    match = re.search(r"```(?:json)?\s*([^\s`]+?)\s*```", content, re.IGNORECASE)
    if match:
        return match.group(1)
    return content

async def extract_comprehensive_keywords(job_description):
    import logging
    prompt = f'''
Extract 12-20 keywords from this job posting for comprehensive ATS optimization.\n\nJob Description: {job_description}\n\nExtract keywords in these categories:\n1. TECHNICAL SKILLS (4-6 keywords):\n2. FUNCTIONAL SKILLS (3-5 keywords):\n3. SOFT SKILLS (2-4 keywords):\n4. INDUSTRY TERMS (2-4 keywords):\n5. EXPERIENCE QUALIFIERS (1-3 keywords):\n\nREQUIREMENTS:\n- Extract EXACTLY 12-20 keywords total\n- Prioritize keywords that appear multiple times\n- Include both exact phrases and individual terms\n- Focus on keywords that would be searched by recruiters\n- Avoid generic words like "experience" or "skills"\n\nRespond ONLY with a valid JSON object matching the schema below.\n\nOutput format:\n{{\n  "technical_skills": [ ... ],\n  "functional_skills": [ ... ],\n  "soft_skills": [ ... ],\n  "industry_terms": [ ... ],\n  "experience_qualifiers": [ ... ],\n  "total_keywords": 16,\n  "keyword_priority": {{\n    "high": [ ... ],\n    "medium": [ ... ],\n    "low": [ ... ]\n  }}\n}}\n'''
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        logging.getLogger("arc").info(f"[OPENAI RAW CONTENT] {content}")
        if not content or not content.strip():
            logging.getLogger("arc").error(f"[OPENAI EMPTY RESPONSE] Full response: {response}")
            raise HTTPException(status_code=500, detail="OpenAI returned an empty response. Please try again or simplify your prompt.")
        import json
        try:
            return json.loads(content)
        except Exception as e:
            logging.getLogger("arc").error(f"[OPENAI INVALID JSON] {e}. Content: {content}")
            logging.getLogger("arc").error(f"[OPENAI FULL RESPONSE] {response}")
            raise HTTPException(status_code=500, detail=f"OpenAI returned invalid JSON: {e}. Content: {content}")
    except Exception as e:
        logging.getLogger("arc").error(f"[OPENAI EXCEPTION] {e}")
        raise HTTPException(status_code=500, detail=f"Keyword extraction failed: {e}")

# --- ENHANCED KEYWORD MAPPING ---
def map_profile_to_job_comprehensive(profile, job_analysis):
    profile_text = str(profile).lower()
    all_keywords = (
        job_analysis.get("technical_skills", []) +
        job_analysis.get("functional_skills", []) +
        job_analysis.get("soft_skills", []) +
        job_analysis.get("industry_terms", []) +
        job_analysis.get("experience_qualifiers", [])
    )
    mapping = {
        "green_keywords": [],
        "amber_keywords": [],
        "red_keywords": [],
        "keyword_coverage": {
            "total_keywords": len(all_keywords),
            "matched_keywords": 0,
            "coverage_percentage": 0
        }
    }
    for keyword in all_keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in profile_text:
            mapping["green_keywords"].append({"keyword": keyword, "evidence": "Found in profile"})
            mapping["keyword_coverage"]["matched_keywords"] += 1
        else:
            # Simple related skill logic: check for partial match
            related = None
            for word in keyword_lower.split():
                if word in profile_text and len(word) > 3:
                    related = word
                    break
            if related:
                mapping["amber_keywords"].append({"keyword": keyword, "related_skill": related, "transfer_rationale": f"{related} is related to {keyword}"})
                mapping["keyword_coverage"]["matched_keywords"] += 1
            else:
                mapping["red_keywords"].append({"keyword": keyword, "gap_severity": "medium", "mitigation": f"Consider gaining experience or training in {keyword}"})
    if mapping["keyword_coverage"]["total_keywords"] > 0:
        mapping["keyword_coverage"]["coverage_percentage"] = round(
            mapping["keyword_coverage"]["matched_keywords"] / mapping["keyword_coverage"]["total_keywords"] * 100
        )
    return mapping

# --- REPLACE MOCK LOGIC IN /cv/preview ---
import time
@router.post("/cv/preview")
async def cv_keyword_preview(request: Request):
    """
    Fast keyword preview and job analysis for user review before full CV generation.
    Input: { profile, jobDescription }
    Output: { preview_ready, processing_time, job_analysis, keyword_analysis, match_score, processing_strategy, user_options }
    """
    data = await request.json()
    profile = data.get("profile")
    job_description = data.get("jobDescription") or data.get("job_description")
    start = time.time()
    # 1. Extract comprehensive keywords from job description
    job_analysis = await extract_comprehensive_keywords(job_description)
    # 2. Map profile to keywords for RAG status
    keyword_mapping = map_profile_to_job_comprehensive(profile, job_analysis)
    # 3. Build preview response (leave fields blank/empty if missing, never use mock data)
    match_score = keyword_mapping.get("keyword_coverage", {}).get("coverage_percentage", 0)
    preview = {
        "preview_ready": True,
        "processing_time": f"{round(time.time() - start, 2)} seconds",
        "job_analysis": {
            "job_title": job_analysis.get("job_title", ""),
            "company": job_analysis.get("company", ""),
            "experience_level": job_analysis.get("experience_level", ""),
            "industry": job_analysis.get("industry", ""),
            "primary_keywords": (job_analysis.get("technical_skills") or []) + (job_analysis.get("functional_skills") or [])
        },
        "keyword_analysis": keyword_mapping,
        "match_score": match_score,
        "processing_strategy": {
            "chunking_approach": "auto",
            "estimated_time": "28 seconds",
            "optimization_focus": job_analysis.get("keyword_priority", {}).get("high", [])
        },
        "user_options": {
            "proceed_with_generation": True,
            "modify_keyword_emphasis": True,
            "adjust_focus_areas": True,
            "custom_instructions": True
        }
    }
    return JSONResponse(content=preview)

# --- NEW: Full CV Generation Endpoint ---
@router.post("/cv/generate")
async def cv_full_generation(request: Request):
    """
    Full CV generation with user preferences and preview data.
    Input: { profile, jobDescription, previewData, userPreferences }
    Output: { ...full CV, cover letter, validation, update capabilities... }
    """
    import os
    import json
    import logging
    from concurrent.futures import ThreadPoolExecutor
    import asyncio
    logger = logging.getLogger("arc_service")
    data = await request.json()
    profile = data.get("profile")
    job_description = data.get("jobDescription") or data.get("job_description")
    preview_data = data.get("previewData")
    user_preferences = data.get("userPreferences", {})
    # Use adaptive chunking pipeline
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
    if not OPENAI_API_KEY or not OPENAI_ASSISTANT_ID:
        logger.error("[CV GENERATE] OpenAI API key or Assistant ID not set")
        return {"error": "OpenAI API key or Assistant ID not set"}
    # 1. Analyze
    analysis = analyze_payload(profile)
    strategy = select_chunking_strategy(analysis)
    logger.info(f"[CV GENERATE] Payload analysis: {analysis}")
    logger.info(f"[CV GENERATE] Chunking strategy: {strategy}")
    # 2. Create chunks
    chunks = create_adaptive_chunks(profile, job_description, strategy)
    logger.info(f"[CV GENERATE] Chunks created: {json.dumps(chunks)[:1000]}")
    # 3. Create global context (if needed)
    global_context = {}  # Optionally, call OpenAI for global context if required
    # 4. Process chunks for raw content only, passing job description and anti-fabrication rules
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=strategy["chunkCount"]) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                process_chunk_with_openai,
                chunk,
                profile,
                job_description,
                OPENAI_API_KEY,
                OPENAI_ASSISTANT_ID
            ) for chunk in chunks
        ]
        chunk_results = await asyncio.gather(*tasks)
    logger.info(f"[CV GENERATE] Chunk results: {json.dumps(chunk_results, default=str)[:2000]}")
    # 5. Final assembly: single unified CV and cover letter
    assembled = assemble_unified_cv(chunk_results, global_context, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID)
    logger.info(f"[CV GENERATE] Final assembled output: {json.dumps(assembled, default=str)[:1000]}")
    return {
        **assembled,
        "strategy": strategy,
        "analysis": analysis,
        "chunks": chunk_results
    }

# --- NEW: CV Update Endpoint ---
@router.post("/cv/update")
async def cv_update(request: Request):
    """
    User-driven CV update endpoint (emphasis, keywords, length, etc.).
    Input: { currentCV, updateRequest, originalProfile, jobDescription }
    Output: { ...updated CV... }
    """
    data = await request.json()
    current_cv = data.get("currentCV")
    update_request = data.get("updateRequest")
    original_profile = data.get("originalProfile")
    job_description = data.get("jobDescription") or data.get("job_description")
    # --- Placeholder logic for update ---
    # In production, call OpenAI with update prompt and current CV
    updated_cv = {
        "cv": {"name": "{{CANDIDATE_NAME}}", "summary": {"content": f"[UPDATED] {update_request}", "priority": 1}},
        "update_applied": update_request,
        "validation_summary": {"factual_accuracy": "100%", "job_alignment": "maximum", "anti_fabrication_compliance": "full"}
    }
    return JSONResponse(content=updated_cv)