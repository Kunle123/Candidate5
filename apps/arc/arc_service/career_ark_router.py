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
    profile = db.query(UserArcData).filter(UserArcData.user_id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    # Ensure user_arc_data row exists for this user
    user_arc = db.query(UserArcData).filter(UserArcData.user_id == profile_id).first()
    if not user_arc:
        user_arc = UserArcData(user_id=profile_id, arc_data={})
        db.add(user_arc)
        db.commit()
        db.refresh(user_arc)
    task_id = str(uuid4())
    new_task = CVTask(id=task_id, user_id=profile_id, status="pending")
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