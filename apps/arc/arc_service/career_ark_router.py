# Another dummy change to trigger CI/CD redeployment
# Dummy change to trigger CI/CD redeployment
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
from .ai_utils import parse_cv_with_ai_chunk
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

# --- OpenAI config (if not already present) ---
logger = logging.getLogger(__name__)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set. AI features will not work correctly.")
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# --- Pydantic models ---
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
    return db.query(WorkExperience).filter_by(user_id=user_id).order_by(WorkExperience.order_index).all()

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
    for field, value in data.dict(exclude_unset=True).items():
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
    for field, value in update.dict(exclude_unset=True).items():
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
    profile_id = entry.cv_profile_id
    order_index = entry.order_index
    db.delete(entry)
    db.commit()
    # Reindex remaining entries
    entries = db.query(Education).filter(
        Education.cv_profile_id == profile_id,
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
    profile_id = entry.cv_profile_id
    old_index = entry.order_index
    if new_order_index == old_index:
        return entry
    # Shift other entries
    if new_order_index > old_index:
        affected = db.query(Education).filter(
            Education.cv_profile_id == profile_id,
            Education.order_index > old_index,
            Education.order_index <= new_order_index
        ).all()
        for e in affected:
            e.order_index -= 1
    else:
        affected = db.query(Education).filter(
            Education.cv_profile_id == profile_id,
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
    profile_id = entry.cv_profile_id
    order_index = entry.order_index
    db.delete(entry)
    db.commit()
    # Reindex remaining entries
    entries = db.query(Project).filter(
        Project.cv_profile_id == profile_id,
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
    profile_id = entry.cv_profile_id
    old_index = entry.order_index
    if new_order_index == old_index:
        return entry
    # Shift other entries
    if new_order_index > old_index:
        affected = db.query(Project).filter(
            Project.cv_profile_id == profile_id,
            Project.order_index > old_index,
            Project.order_index <= new_order_index
        ).all()
        for e in affected:
            e.order_index -= 1
    else:
        affected = db.query(Project).filter(
            Project.cv_profile_id == profile_id,
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
    profile_id = entry.cv_profile_id
    order_index = entry.order_index
    db.delete(entry)
    db.commit()
    # Reindex remaining entries
    entries = db.query(Certification).filter(
        Certification.cv_profile_id == profile_id,
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
    profile_id = entry.cv_profile_id
    old_index = entry.order_index
    if new_order_index == old_index:
        return entry
    # Shift other entries
    if new_order_index > old_index:
        affected = db.query(Certification).filter(
            Certification.cv_profile_id == profile_id,
            Certification.order_index > old_index,
            Certification.order_index <= new_order_index
        ).all()
        for e in affected:
            e.order_index -= 1
    else:
        affected = db.query(Certification).filter(
            Certification.cv_profile_id == profile_id,
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

# --- Training Endpoints ---
@router.get("/users/{user_id}/training")
def list_training(user_id: str, db: Session = Depends(get_db)):
    return db.query(Training).filter_by(user_id=user_id).all()

@router.post("/users/{user_id}/training")
def add_training(user_id: str, data: TrainingCreate, db: Session = Depends(get_db)):
    max_index = db.query(Training).filter_by(user_id=user_id).order_by(Training.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = Training(
        user_id=user_id,
        name=data.name,
        institution=data.institution,
        start_date=data.start_date,
        end_date=data.end_date,
        description=data.description,
        order_index=order_index
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.put("/training/{id}")
def update_training(id: int, data: TrainingUpdate, db: Session = Depends(get_db)):
    entry = db.query(Training).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/training/{id}")
def delete_training(id: int, db: Session = Depends(get_db)):
    entry = db.query(Training).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(entry)
    db.commit()
    return {"success": True}

@router.patch("/training/{id}")
def partial_update_training(id: int, update: TrainingUpdate, db: Session = Depends(get_db)):
    entry = db.query(Training).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

# --- Per-Profile CV Upload Endpoint ---
@router.post("/profiles/{profile_id}/cv")
def upload_cv_for_profile(profile_id: UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    profile = db.query(CVProfile).filter(CVProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    # Ensure user_arc_data row exists for this user
    user_arc = db.query(UserArcData).filter(UserArcData.user_id == profile.user_id).first()
    if not user_arc:
        user_arc = UserArcData(user_id=profile.user_id, arc_data={})
        db.add(user_arc)
        db.commit()
        db.refresh(user_arc)
    task_id = str(uuid4())
    new_task = CVTask(id=task_id, user_id=profile.user_id, status="pending")
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    filename = file.filename.lower()
    try:
        # 1. Extract text from file
        if filename.endswith(".pdf"):
            text = extract_text_from_pdf(file)
        elif filename.endswith(".docx"):
            text = extract_text_from_docx(file)
        else:
            new_task.status = "failed"
            new_task.error = f"Unsupported file type: {filename}"
            db.commit()
            raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX are supported.")
        # 2. Split into sections
        sections = split_cv_by_sections(text)
        chunk_outputs = []
        ai_raw_chunks = []
        from concurrent.futures import ThreadPoolExecutor, as_completed
        total_chunks = 0
        with ThreadPoolExecutor() as executor:
            futures = []
            for section_idx, (header, section_text) in enumerate(sections):
                nlp_chunks = nlp_chunk_text(section_text, max_tokens=40000)
                for chunk in nlp_chunks:
                    futures.append(executor.submit(parse_cv_with_ai_chunk, chunk))
                total_chunks += len(nlp_chunks)
            for future in as_completed(futures):
                arc_data = future.result()
                arc_data_dict = arc_data.dict()
                arc_data_dict.pop("raw_ai_output", None)
                chunk_outputs.append(arc_data_dict)
                if hasattr(arc_data, 'raw_ai_output'):
                    ai_raw_chunks.append(getattr(arc_data, 'raw_ai_output'))
        # 3. Combine outputs
        combined = {"work_experience": [], "education": [], "skills": [], "projects": [], "certifications": []}
        for chunk in chunk_outputs:
            for key in combined.keys():
                value = chunk.get(key)
                if value:
                    if isinstance(value, list):
                        combined[key].extend(value)
                    else:
                        combined[key].append(value)
        # 4. Save results to user_arc_data
        new_arc_data = ArcData(**combined)
        arc_data_dict = new_arc_data.dict()
        arc_data_dict["raw_text"] = text
        arc_data_dict["ai_raw_chunks"] = ai_raw_chunks
        user_arc.arc_data = arc_data_dict
        db.commit()
        # 5. Update task status
        new_task.status = "completed"
        new_task.extracted_data_summary = {"workExperienceCount": len(new_arc_data.work_experience or []), "skillsFound": len(new_arc_data.skills or [])}
        db.commit()
    except Exception as e:
        new_task.status = "failed"
        new_task.error = str(e)
        db.commit()
        raise
    return {"taskId": task_id}

# --- Application Material Generation Endpoint ---
class GenerateRequest(BaseModel):
    jobAdvert: str
    arcData: dict
    cvOptions: Optional[dict] = None

@router.post("/generate")
def generate_application_materials(data: GenerateRequest):
    logger = logging.getLogger("arc")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = OpenAI(api_key=openai_api_key)

    # Log the actual user data being sent to OpenAI
    import json
    logger.info("[DEBUG] data.arcData sent to OpenAI: " + json.dumps(data.arcData, indent=2))
    logger.info("[DEBUG] data.jobAdvert sent to OpenAI: " + str(data.jobAdvert))

    # Extract cvOptions fields if present
    relevant_experience = None
    style = None
    tone = None
    if data.cvOptions:
        relevant_experience = data.cvOptions.get("relevantExperience")
        style = data.cvOptions.get("style")
        tone = data.cvOptions.get("tone")

    # Build the prompt
    prompt = (
        "You are an expert career assistant and professional resume writer, specializing in creating comprehensive, executive-level CVs for senior technology leaders. Your task is to generate a tailored CV and personalized cover letter that strategically positions the candidate's COMPLETE experience to match specific job requirements while staying strictly within the bounds of the source material.\n\n"
        "**CRITICAL DATA SOURCE SEPARATION RULE:**\n"
        "- **USER CV DATA:** This is the ONLY source for all CV content (work history, skills, achievements, education, etc.)\n"
        "- **JOB ADVERT:** This is ONLY used for tailoring and prioritization guidance - NEVER as content for the CV itself\n\n"
        "**DUAL PRIMARY DIRECTIVES:**\n"
        "1. **COMPLETENESS:** Include the candidate's ENTIRE career history from USER CV DATA - every single role must be represented\n"
        "2. **STRATEGIC TAILORING:** Reframe and emphasize existing experience to align with specific job requirements\n\n"
        "**ABSOLUTE PROHIBITIONS:**\n"
        "- NEVER include any content from the job advert in the CV\n"
        "- NEVER omit any employment periods or roles from USER CV DATA\n"
        "- NEVER invent experience, metrics, or achievements not in source material\n"
        "- NEVER claim competencies that cannot be evidenced in the work history\n\n"
        "**Instructions:**\n\n"
        "1. **Deep Job Requirements Analysis (FOR STRATEGIC TAILORING ONLY):**\n"
        "   - **Mandatory Requirements:** Identify 'essential,' 'mandatory,' or 'required' experience types\n"
        "   - **Industry Context:** Determine target industry and related sectors\n"
        "   - **Specific Experience Types:** Note unique requirements (client onboarding, M&A, global matrix, etc.)\n"
        "   - **Technical Requirements:** Identify specific platforms, methodologies, or tools\n"
        "   - **Seniority Indicators:** Understand scope, scale, and leadership expectations\n\n"
        "2. **Complete Career Inventory (USER CV DATA ANALYSIS):**\n"
        "   - **MANDATORY COMPLETENESS CHECK:** Catalog EVERY employment period from USER CV DATA\n"
        "   - **CHRONOLOGICAL VERIFICATION:** Ensure complete career timeline from earliest to most recent role\n"
        "   - **Experience Mapping:** Identify how each role can contribute to job requirements\n"
        "   - **Industry Alignment:** Find all roles that match or relate to target industry\n"
        "   - **Transferable Skills:** Discover experiences that can be repositioned for requirements\n"
        "   - **Technical Inventory:** Catalog all technologies, platforms, and methodologies mentioned\n\n"
        "3. **Strategic Experience Repositioning Framework:**\n\n"
        "   **A. Evidence-Based Competency Development:**\n"
        "   - **Only claim competencies that can be demonstrated in work history**\n"
        "   - **Map each claimed skill to specific roles and achievements**\n"
        "   - **Avoid generic competency lists without supporting evidence**\n\n"
        "   **B. Experience Reframing (Within Source Bounds):**\n"
        "   - 'Multi-supplier coordination' → 'Client integration and onboarding' (when managing external organizations)\n"
        "   - 'System consolidation projects' → 'Post-acquisition integration' (when involving organizational change)\n"
        "   - 'International team management' → 'Global matrix organization delivery' (when coordinating across locations)\n"
        "   - 'Stakeholder engagement' → 'Client relationship management' (when involving external parties)\n\n"
        "4. **Generate a Comprehensive, Strategically Tailored CV:**\n\n"
        "   **A. Structure and Length:**\n"
        "   - **Target Length:** 3-5 pages to accommodate COMPLETE career history\n"
        "   - **NO OMISSIONS:** Every single role from USER CV DATA must be included\n"
        "   - **Strategic Ordering:** Recent and job-relevant experience first, but ALL experience included\n\n"
        "   **B. Professional Summary (Strategic Positioning):**\n"
        "   - **Accurate Career Span:** Reflect total years of experience from USER CV DATA\n"
        "   - **Industry Breadth:** Mention ALL industries represented in career history\n"
        "   - **Requirement Alignment:** Subtly address mandatory requirements using actual experience\n"
        "   - **Technical Depth:** Include key technologies from across entire career\n\n"
        "   **C. Core Competencies (Evidence-Based):**\n"
        "   - **Demonstrated Skills Only:** Include only competencies evidenced in work history\n"
        "   - **Requirement Matching:** Prioritize skills that align with job requirements\n"
        "   - **Technical Platforms:** List technologies actually used in roles\n"
        "   - **Leadership Scope:** Include competencies demonstrated through actual experience\n\n"
        "   **D. Work Experience (Complete with Strategic Emphasis):**\n\n"
        "   **Inclusion Rules (NON-NEGOTIABLE):**\n"
        "   - **EVERY ROLE:** Must include every single employment period from USER CV DATA\n"
        "   - **COMPLETE TIMELINE:** From earliest role to most recent\n"
        "   - **NO CONDENSATION:** Do not merge or omit roles to save space\n"
        "   - **CHRONOLOGICAL ORDER:** Most recent first, but complete career represented\n\n"
        "   **Detail Standards by Strategic Relevance:**\n"
        "   - **Highly Relevant Roles:** 6-8 detailed bullet points with strategic reframing\n"
        "   - **Moderately Relevant Roles:** 4-6 bullet points with key achievements\n"
        "   - **Supporting Roles:** 3-4 bullet points showing progression and skills\n"
        "   - **Early Career Roles:** 2-3 bullet points highlighting foundational experience\n\n"
        "   **Strategic Reframing Guidelines:**\n"
        "   - **Context Setting:** Frame projects to highlight aspects relevant to target role\n"
        "   - **Language Alignment:** Use terminology that resonates with target industry\n"
        "   - **Scope Emphasis:** Highlight scale and complexity that matches job requirements\n"
        "   - **Industry Context:** Position work in context relevant to target sector\n\n"
        "   **E. Technical Detail Preservation:**\n"
        "   - **Maintain ALL specific technologies, platforms, and technical details from USER CV DATA**\n"
        "   - **Preserve quantifiable elements:** team sizes, project scales, timeframes from source\n"
        "   - **Include industry-specific technical implementations**\n"
        "   - **Show technical progression across career\n\n"
        "5. **Industry-Specific Tailoring Strategies:**\n\n"
        "   **Healthcare/Scientific/Publishing:**\n"
        "   - Emphasize regulatory compliance, research collaboration, data governance\n"
        "   - Highlight any healthcare, research, or academic experience\n"
        "   - Frame technology projects in terms of scientific/healthcare outcomes\n"
        "   - Position analytics and data integration experience prominently\n\n"
        "   **Financial Services:**\n"
        "   - Emphasize regulatory compliance, risk management, security\n"
        "   - Highlight payment systems, financial platforms, audit experience\n"
        "   - Frame projects in terms of financial impact and compliance\n\n"
        "   **Technology/Digital:**\n"
        "   - Emphasize platform scalability, user experience, digital transformation\n"
        "   - Highlight cloud technologies, integration platforms, agile methodologies\n"
        "   - Frame projects in terms of innovation and technical advancement\n\n"
        "6. **Quality Assurance for Complete Strategic Tailoring:**\n"
        "   Before finalizing, verify:\n"
        "   - [ ] Every employment period from USER CV DATA is included in the CV\n"
        "   - [ ] Career timeline is complete and accurate (full span represented)\n"
        "   - [ ] Every claimed competency is evidenced in the work history\n"
        "   - [ ] Mandatory job requirements are addressed through existing experience\n"
        "   - [ ] Industry context is appropriately emphasized without invention\n"
        "   - [ ] All technical details and platforms from source are preserved\n"
        "   - [ ] No content from job advert appears in the CV\n"
        "   - [ ] Professional summary accurately reflects complete career scope\n\n"
        "7. **Generate a Targeted Cover Letter:**\n"
        "   - **Requirement Mapping:** Connect candidate's actual experience to each mandatory requirement\n"
        "   - **Complete Career Context:** Reference the full breadth of experience\n"
        "   - **Industry Understanding:** Demonstrate knowledge using actual background\n"
        "   - **Evidence-Based Claims:** Only reference achievements and capabilities from USER CV DATA\n\n"
        "**CRITICAL SUCCESS FACTORS:**\n"
        "1. **Complete Representation:** Every role from source data appears in CV\n"
        "2. **Evidence-Based Tailoring:** All claims supported by actual work history\n"
        "3. **Strategic Positioning:** Existing experience reframed to meet job requirements\n"
        "4. **Industry Alignment:** Experience positioned in target industry context\n"
        "5. **Technical Credibility:** All technical details preserved and emphasized\n\n"
        "**FINAL VERIFICATION CHECKLIST:**\n"
        "- [ ] CV includes complete career history from USER CV DATA (no omissions)\n"
        "- [ ] Every competency claimed is demonstrated in work experience\n"
        "- [ ] Mandatory job requirements addressed through existing experience\n"
        "- [ ] Professional summary reflects full career span and industry breadth\n"
        "- [ ] Technical depth and specific implementations preserved\n"
        "- [ ] No invented content or exaggerated claims beyond source material\n\n"
        "**Return a JSON object with two fields: 'cv' and 'cover_letter'.**\n---\n"
        f"**USER CV DATA (JSON):**\n{json.dumps(data.arcData, indent=2)}\n\n"
        f"---\n**JOB ADVERT (FOR TAILORING REFERENCE ONLY - DO NOT INCLUDE CONTENT FROM THIS IN THE CV):**\n{data.jobAdvert}\n\n"
        "---\n**RESPONSE FORMAT:**\n{\n  \"cv\": \"...\",\n  \"cover_letter\": \"...\"\n}\n"
    )
    logger.info("[DEBUG] OpenAI prompt for /generate:\n" + prompt)
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        import json
        content = response.choices[0].message.content
        logger.info(f"[DEBUG] OpenAI response for /generate: {content[:500]}...")
        result = json.loads(content)
        return result
    except Exception as e:
        logger.error(f"[ERROR] OpenAI generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"OpenAI generation failed: {e}")

@router.post("/generate-assistant")
async def generate_assistant_action(data: AssistantActionRequest):
    import json
    logger = logging.getLogger("arc")
    action = data.action
    profile = data.profile
    job_description = data.job_description
    keywords = data.keywords
    additional_keypoints = data.additional_keypoints
    previous_cv = data.previous_cv
    thread_id = data.thread_id

    # --- OpenAI Assistants API setup ---
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)

    # --- Use a single assistant for all actions (create if not exists) ---
    ASSISTANT_NAME = "Career Ark Assistant"
    ASSISTANT_INSTRUCTIONS = "You are a career assistant for CV and cover letter generation, keyword extraction, and CV updating. Always return valid JSON as specified."
    ASSISTANT_TOOLS = []
    assistant_id = os.getenv("OPENAI_ASSISTANT_ID")
    if not assistant_id:
        assistant = client.beta.assistants.create(
            name=ASSISTANT_NAME,
            instructions=ASSISTANT_INSTRUCTIONS,
            tools=ASSISTANT_TOOLS,
            model="gpt-4o-2024-08-06"
        )
        assistant_id = assistant.id

    # --- Thread management ---
    if thread_id:
        thread = client.beta.threads.retrieve(thread_id)
    else:
        # On first call, require profile and job_description
        if not profile or not job_description:
            raise HTTPException(status_code=400, detail="'profile' and 'job_description' are required on the first call (when no thread_id is provided). Subsequent calls can omit them.")
        thread = client.beta.threads.create()
        thread_id = thread.id
        logger.info(f"[DEBUG] Created new OpenAI thread with thread_id: {thread_id}")

    # --- Compose the user message for the thread ---
    if action == "extract_keywords":
        user_message = (
            "ACTION: extract_keywords\n\n"
            f"PROFILE:\n{json.dumps(profile, indent=2) if profile else ''}\n\n"
            f"JOB DESCRIPTION:\n{job_description if job_description else ''}\n\n"
            "Return ONLY a valid JSON object in the format: {\"keywords\": [\"keyword1\", ...], \"match_percentage\": 87}\n"
        )
    elif action == "generate_cv":
        user_message = (
            "ACTION: generate_cv\n\n"
            f"PROFILE:\n{json.dumps(profile, indent=2) if profile else ''}\n\n"
            f"JOB DESCRIPTION:\n{job_description if job_description else ''}\n"
        )
        if keywords:
            user_message += f"\nKEYWORDS TO EMPHASIZE: {', '.join(keywords)}"
        user_message += "\nReturn ONLY a valid JSON object in the format: {\n  \"cv\": \"...\", \"cover_letter\": \"...\"\n}"
    elif action == "update_cv":
        user_message = (
            "ACTION: update_cv\n\n"
            f"PROFILE:\n{json.dumps(profile, indent=2) if profile else ''}\n\n"
            f"JOB DESCRIPTION:\n{job_description if job_description else ''}\n\n"
            f"PREVIOUS CV:\n{previous_cv}\n"
        )
        if additional_keypoints:
            user_message += f"\nADDITIONAL KEY POINTS TO INTEGRATE:\n{json.dumps(additional_keypoints, indent=2)}"
        user_message += "\nReturn ONLY a valid JSON object in the format: {\n  \"cv\": \"...updated...\", \"cover_letter\": \"...\"\n}"
    else:
        return {"error": "Unrecognized action. Must be one of: extract_keywords, generate_cv, update_cv"}

    # --- Add the message to the thread ---
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_message
    )

    # --- Run the assistant on the thread ---
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions=None
    )

    # --- Wait for the run to complete (polling) ---
    import time
    while True:
        run_status = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        if run_status.status in ["completed", "failed", "cancelled"]:
            break
        time.sleep(1)

    if run_status.status != "completed":
        logger.error(f"OpenAI Assistant run failed: {run_status.status}")
        raise HTTPException(status_code=500, detail=f"OpenAI Assistant run failed: {run_status.status}")

    # --- Get the latest assistant message ---
    messages = client.beta.threads.messages.list(thread_id=thread_id, order="desc", limit=1)
    if not messages.data:
        logger.error("No assistant message returned.")
        raise HTTPException(status_code=500, detail="No assistant message returned.")
    content = messages.data[0].content[0].text.value
    try:
        result = json.loads(content)
    except Exception as e:
        logger.error(f"Failed to parse assistant response as JSON: {e}\nRaw content: {content}")
        raise HTTPException(status_code=500, detail="Failed to parse assistant response as JSON.")

    # --- Always return the thread_id in the response ---
    result["thread_id"] = thread_id
    return result

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

@router.get("/cv/download/{taskId}")
async def download_processed_cv(taskId: UUID, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db_user_arc = db.query(UserArcData).filter(UserArcData.user_id == user_id).first()
    if not db_user_arc or not db_user_arc.arc_data:
        raise HTTPException(status_code=404, detail="No extracted data found for user")
    import json
    data_bytes = json.dumps(db_user_arc.arc_data, indent=2).encode()
    return FileResponse(io.BytesIO(data_bytes), media_type="application/json", filename=f"extracted_cv_{taskId}.json")

@router.get("/cv/status/{taskId}")
async def poll_cv_status(taskId: UUID = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = db.query(CVTask).filter(CVTask.id == taskId, CVTask.user_id == user_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": db_task.status,
        "extractedDataSummary": db_task.extracted_data_summary,
        "error": db_task.error
    }

@router.get("/cv/text/{taskId}")
async def get_raw_text(taskId: UUID = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def get_ai_raw(taskId: UUID = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def get_ai_combined(taskId: UUID = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def get_ai_filtered(taskId: UUID = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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
async def get_arcdata(taskId: UUID = Path(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
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

@router.get("/version")
def version():
    return {
        "version": "1.0.0",
        "git_commit": os.getenv("GIT_COMMIT", "unknown"),
        "deployed_at": os.getenv("DEPLOYED_AT", "unknown")
    }

@router.get("/debug/routes")
def list_routes():
    return [route.path for route in router.routes if isinstance(route, APIRoute)]

@router.post("/keywords", response_model=KeywordsResponse)
async def extract_keywords(request: KeywordsRequest):
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured.")
    try:
        N = 20
        system_prompt = '''
You are an expert ATS (Applicant Tracking System) keyword extraction specialist. Your task is to analyze the provided job description and extract EXACTLY 20 of the most critical keywords and phrases that recruiters and ATS systems prioritize when filtering and ranking resumes.

CRITICAL REQUIREMENT: You MUST return exactly 20 keywords - no more, no less.

EXTRACTION CRITERIA:
Select the top 20 keywords prioritizing them in this order:

1. HARD SKILLS & TECHNICAL REQUIREMENTS (Highest Priority)
   - Programming languages, software, tools, platforms
   - Technical certifications and credentials
   - Industry-specific technologies and methodologies
   - Measurable technical competencies
2. QUALIFICATIONS & EXPERIENCE REQUIREMENTS (High Priority)
   - Education requirements (degree types, fields of study)
   - Years of experience (specific numbers: "3+ years", "5-7 years")
   - Professional certifications and licenses
   - Industry experience requirements
3. JOB TITLES & ROLE-SPECIFIC TERMS (Medium-High Priority)
   - Exact job titles mentioned
   - Related role titles and seniority levels
   - Department or function names
   - Industry-specific role terminology
4. SOFT SKILLS & COMPETENCIES (Medium Priority - only if space allows)
   - Communication, leadership, teamwork abilities
   - Problem-solving and analytical thinking
   - Project management and organizational skills
   - Only include if explicitly mentioned as requirements

PRIORITIZATION RULES:
- Prioritize keywords that appear multiple times in the job description
- Give higher weight to terms in "Requirements" or "Qualifications" sections
- Include both exact phrases and individual component words when relevant
- Focus on "must-have" requirements over "nice-to-have" preferences
- If multiple similar terms exist, choose the most commonly used industry standard

KEYWORD FORMAT GUIDELINES:
- Include both acronyms and full terms when both appear (e.g., "SQL", "Structured Query Language")
- Preserve exact capitalization and formatting as written
- Include compound phrases as single keywords when they represent unified concepts
- Maintain industry-standard terminology and spelling

COUNT ENFORCEMENT:
- Count your keywords before finalizing
- If you have more than 20, remove the least critical ones
- If you have fewer than 20, add the next most important keywords from the job description
- Double-check that your final array contains exactly 20 elements

OUTPUT FORMAT:
Return ONLY a valid JSON object in the following format (no extra text, no explanations):
{"keywords": ["keyword1", "keyword2", ..., "keyword20"], "match_percentage": 87}

MATCH PERCENTAGE:
After extracting the keywords, compare them to the user's profile.
- Calculate a percentage match (0-100) based on how many of the 20 keywords are present in the user's profile (case-insensitive, partial matches allowed).
- Return this as "match_percentage" in the output JSON.
'''
        prompt = system_prompt + f"\n\nJOB DESCRIPTION:\n{request.job_description}\n\nUSER PROFILE:\n{request.profile}"
        logger.info(f"[DEBUG] OpenAI prompt for /keywords:\n{prompt}")
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.2,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            raw_response = completion.choices[0].message.content
            logger.info(f"[DEBUG] OpenAI response for /keywords: {raw_response[:500]}...")
            import json as pyjson
            result = pyjson.loads(raw_response)
            keywords = result.get("keywords", [])
            match_percentage = result.get("match_percentage", 0)
            return KeywordsResponse(keywords=keywords, match_percentage=match_percentage)
        except Exception as e:
            logger.error(f"[ERROR] OpenAI /keywords failed: {e}")
            raise HTTPException(status_code=500, detail=f"OpenAI /keywords failed: {e}")
    except Exception as e:
        logger.error(f"Error extracting keywords: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error extracting keywords: {str(e)}")

@router.post("/generate-cv", response_model=GenerateCVResponse)
async def generate_cv(request: GenerateCVRequest):
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured.")
    try:
        # Use the full system prompt from your docs/assistant_system_instructions.md
        system_prompt = """
[...PASTE FULL SYSTEM INSTRUCTIONS PROMPT HERE...]
USER CV DATA (JSON):\n{profile}\n\nJOB ADVERT (FOR STRATEGIC TAILORING REFERENCE ONLY - DO NOT INCLUDE CONTENT FROM THIS IN THE CV):\n{job_description}\n\nRESPONSE FORMAT:\n{{\n  \"cv\": \"...\",\n  \"cover_letter\": \"...\"\n}}\n"""
        prompt = system_prompt.format(profile=request.profile, job_description=request.job_description)
        if request.keywords:
            prompt += f"\nKEYWORDS TO EMPHASIZE: {', '.join(request.keywords)}\n"
        logger.info(f"[DEBUG] OpenAI prompt for /generate-cv:\n{prompt}")
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            raw_response = completion.choices[0].message.content
            logger.info(f"[DEBUG] OpenAI response for /generate-cv: {raw_response[:500]}...")
            import json as pyjson
            result = pyjson.loads(raw_response)
            return GenerateCVResponse(**result)
        except Exception as e:
            logger.error(f"[ERROR] OpenAI /generate-cv failed: {e}")
            raise HTTPException(status_code=500, detail=f"OpenAI /generate-cv failed: {e}")
    except Exception as e:
        logger.error(f"Error generating CV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating CV: {str(e)}")

@router.post("/update-cv", response_model=UpdateCVResponse)
async def update_cv(request: UpdateCVRequest):
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured.")
    try:
        system_prompt = """
[...PASTE FULL SYSTEM INSTRUCTIONS PROMPT HERE...]
USER CV DATA (JSON):\n{profile}\n\nJOB ADVERT (FOR STRATEGIC TAILORING REFERENCE ONLY - DO NOT INCLUDE CONTENT FROM THIS IN THE CV):\n{job_description}\n\nPREVIOUS CV:\n{previous_cv}\n\nADDITIONAL KEY POINTS TO INTEGRATE:\n{additional_keypoints}\n\nRESPONSE FORMAT:\n{{\n  \"cv\": \"...updated...\",\n  \"cover_letter\": \"...\"\n}}\n"""
        prompt = system_prompt.format(
            profile=request.profile,
            job_description=request.job_description,
            previous_cv=request.previous_cv,
            additional_keypoints="\n".join(request.additional_keypoints)
        )
        logger.info(f"[DEBUG] OpenAI prompt for /update-cv:\n{prompt}")
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            raw_response = completion.choices[0].message.content
            logger.info(f"[DEBUG] OpenAI response for /update-cv: {raw_response[:500]}...")
            import json as pyjson
            result = pyjson.loads(raw_response)
            return UpdateCVResponse(**result)
        except Exception as e:
            logger.error(f"[ERROR] OpenAI /update-cv failed: {e}")
            raise HTTPException(status_code=500, detail=f"OpenAI /update-cv failed: {e}")
    except Exception as e:
        logger.error(f"Error updating CV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating CV: {str(e)}") 