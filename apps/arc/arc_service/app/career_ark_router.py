# Dummy change to trigger CI/CD redeployment
from fastapi import APIRouter, HTTPException, Path, Body, Depends, UploadFile, File
from sqlalchemy.orm import Session
from .models import CVProfile, WorkExperience, Education, Skill, Project, Certification, Training, UserArcData, CVTask
from .db import get_db
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .auth import get_current_user
import logging
from uuid import UUID, uuid4
import os
from fastapi.responses import FileResponse
import io
from .arc_schemas import ArcData
from .cv_utils import extract_text_from_docx, extract_text_from_pdf, split_cv_by_sections, nlp_chunk_text

router = APIRouter()

# --- Pydantic Schemas ---
class ProfileCreate(BaseModel):
    user_id: str
    name: str
    email: Optional[str] = None
class ProfileUpdate(BaseModel):
    name: Optional[str]
    email: Optional[str]
class ProfileOut(BaseModel):
    id: UUID
    user_id: str
    name: str
    email: Optional[str]
    class Config:
        from_attributes = True

class WorkExperienceCreate(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str
    description: Optional[str] = None
    order_index: Optional[int] = None
class WorkExperienceUpdate(BaseModel):
    company: Optional[str]
    title: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]
class WorkExperienceOut(BaseModel):
    id: UUID
    company: str
    title: str
    start_date: str
    end_date: str
    description: Optional[str]
    order_index: int
    class Config:
        from_attributes = True

class EducationCreate(BaseModel):
    institution: str
    degree: str
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None
class EducationUpdate(BaseModel):
    institution: Optional[str]
    degree: Optional[str]
    field: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]
class EducationOut(BaseModel):
    id: UUID
    institution: str
    degree: str
    field: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]
    order_index: int
    class Config:
        from_attributes = True

class SkillCreate(BaseModel):
    skill: str
class SkillOut(BaseModel):
    id: UUID
    skill: str
    class Config:
        from_attributes = True

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    order_index: Optional[int] = None
class ProjectUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]
class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    order_index: int
    class Config:
        from_attributes = True

class CertificationCreate(BaseModel):
    name: str
    issuer: Optional[str] = None
    year: Optional[str] = None
    order_index: Optional[int] = None
class CertificationUpdate(BaseModel):
    name: Optional[str]
    issuer: Optional[str]
    year: Optional[str]
class CertificationOut(BaseModel):
    id: UUID
    name: str
    issuer: Optional[str]
    year: Optional[str]
    order_index: int
    class Config:
        from_attributes = True

class TrainingCreate(BaseModel):
    name: str
    institution: str
    start_date: str
    end_date: str
    description: Optional[str] = None
    order_index: Optional[int] = None
class TrainingUpdate(BaseModel):
    name: Optional[str]
    institution: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]

# --- Profile Endpoints ---
@router.post("/profiles", response_model=ProfileOut)
def create_profile(data: ProfileCreate, db: Session = Depends(get_db)):
    entry = CVProfile(user_id=data.user_id, name=data.name, email=data.email)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/profiles/me", response_model=ProfileOut)
def get_my_profile(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    logger = logging.getLogger("arc")
    logger.setLevel(logging.DEBUG)
    logger.info(f"[DEBUG] /profiles/me endpoint hit for user_id={user_id}")
    try:
        entry = db.query(CVProfile).filter_by(user_id=user_id).first()
        logger.debug(f"[DEBUG] DB query result for user_id={user_id}: {entry}")
        if not entry:
            logger.warning(f"[DEBUG] No profile found for user_id={user_id}")
            raise HTTPException(status_code=404, detail="Profile not found for current user")
        logger.info(f"[DEBUG] Returning profile for user_id={user_id}: {entry}")
        return entry
    except Exception as e:
        logger.error(f"[DEBUG] Exception in /profiles/me for user_id={user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error in /profiles/me")

@router.get("/profiles/{user_id}", response_model=ProfileOut)
def get_profile(user_id: str, db: Session = Depends(get_db)):
    entry = db.query(CVProfile).filter_by(user_id=user_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Profile not found")
    return entry

@router.put("/profiles/{user_id}", response_model=ProfileOut)
def update_profile(user_id: str, data: ProfileUpdate, db: Session = Depends(get_db)):
    entry = db.query(CVProfile).filter_by(user_id=user_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/profiles/{user_id}")
def delete_profile(user_id: str, db: Session = Depends(get_db)):
    entry = db.query(CVProfile).filter_by(user_id=user_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(entry)
    db.commit()
    return {"success": True}

# --- Work Experience Endpoints ---
@router.post("/profiles/{profile_id}/work_experience", response_model=WorkExperienceOut)
def add_work_experience(profile_id: int, data: WorkExperienceCreate, db: Session = Depends(get_db)):
    max_index = db.query(WorkExperience).filter_by(cv_profile_id=profile_id).order_by(WorkExperience.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = WorkExperience(
        cv_profile_id=profile_id,
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

@router.get("/profiles/{profile_id}/work_experience", response_model=List[WorkExperienceOut])
def list_work_experience(profile_id: int, db: Session = Depends(get_db)):
    return db.query(WorkExperience).filter_by(cv_profile_id=profile_id).order_by(WorkExperience.order_index).all()

@router.get("/work_experience/{id}", response_model=WorkExperienceOut)
def get_work_experience(id: int, db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    return entry

@router.put("/work_experience/{id}", response_model=WorkExperienceOut)
def update_work_experience(id: int, data: WorkExperienceUpdate, db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/work_experience/{id}")
def delete_work_experience(id: int, db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    profile_id = entry.cv_profile_id
    order_index = entry.order_index
    db.delete(entry)
    db.commit()
    # Reindex remaining entries
    entries = db.query(WorkExperience).filter(
        WorkExperience.cv_profile_id == profile_id,
        WorkExperience.order_index > order_index
    ).order_by(WorkExperience.order_index).all()
    for e in entries:
        e.order_index -= 1
    db.commit()
    return {"success": True}

@router.patch("/work_experience/{id}/reorder", response_model=WorkExperienceOut)
def reorder_work_experience(id: int, new_order_index: int = Body(...), db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    profile_id = entry.cv_profile_id
    old_index = entry.order_index
    if new_order_index == old_index:
        return entry
    # Shift other entries
    if new_order_index > old_index:
        affected = db.query(WorkExperience).filter(
            WorkExperience.cv_profile_id == profile_id,
            WorkExperience.order_index > old_index,
            WorkExperience.order_index <= new_order_index
        ).all()
        for e in affected:
            e.order_index -= 1
    else:
        affected = db.query(WorkExperience).filter(
            WorkExperience.cv_profile_id == profile_id,
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
def partial_update_work_experience(id: int, update: WorkExperienceUpdate, db: Session = Depends(get_db)):
    entry = db.query(WorkExperience).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    for field, value in update.dict(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry

# --- Education Endpoints ---
@router.post("/profiles/{profile_id}/education", response_model=EducationOut)
def add_education(profile_id: int, data: EducationCreate, db: Session = Depends(get_db)):
    max_index = db.query(Education).filter_by(cv_profile_id=profile_id).order_by(Education.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = Education(
        cv_profile_id=profile_id,
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

@router.get("/profiles/{profile_id}/education", response_model=List[EducationOut])
def list_education(profile_id: int, db: Session = Depends(get_db)):
    return db.query(Education).filter_by(cv_profile_id=profile_id).order_by(Education.order_index).all()

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
@router.post("/profiles/{profile_id}/skills", response_model=SkillOut)
def add_skill(profile_id: int, data: SkillCreate, db: Session = Depends(get_db)):
    entry = Skill(cv_profile_id=profile_id, skill=data.skill)
    db.add(entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Skill already exists for this profile.")
    db.refresh(entry)
    return entry

@router.get("/profiles/{profile_id}/skills", response_model=List[SkillOut])
def list_skills(profile_id: int, db: Session = Depends(get_db)):
    return db.query(Skill).filter_by(cv_profile_id=profile_id).all()

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
@router.post("/profiles/{profile_id}/projects", response_model=ProjectOut)
def add_project(profile_id: int, data: ProjectCreate, db: Session = Depends(get_db)):
    max_index = db.query(Project).filter_by(cv_profile_id=profile_id).order_by(Project.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = Project(
        cv_profile_id=profile_id,
        name=data.name,
        description=data.description,
        order_index=order_index
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/profiles/{profile_id}/projects", response_model=List[ProjectOut])
def list_projects(profile_id: int, db: Session = Depends(get_db)):
    return db.query(Project).filter_by(cv_profile_id=profile_id).order_by(Project.order_index).all()

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
@router.post("/profiles/{profile_id}/certifications", response_model=CertificationOut)
def add_certification(profile_id: int, data: CertificationCreate, db: Session = Depends(get_db)):
    max_index = db.query(Certification).filter_by(cv_profile_id=profile_id).order_by(Certification.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = Certification(
        cv_profile_id=profile_id,
        name=data.name,
        issuer=data.issuer,
        year=data.year,
        order_index=order_index
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/profiles/{profile_id}/certifications", response_model=List[CertificationOut])
def list_certifications(profile_id: int, db: Session = Depends(get_db)):
    return db.query(Certification).filter_by(cv_profile_id=profile_id).order_by(Certification.order_index).all()

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
def get_all_sections(profile_id: str, db: Session = Depends(get_db)):
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
    work_experience = db.query(WorkExperience).filter_by(cv_profile_id=profile_id).all()
    # Sort work_experience by end_date descending ("Present" most recent)
    work_experience_sorted = sorted(
        work_experience,
        key=lambda x: parse_date(x.end_date),
        reverse=True
    )
    education = db.query(Education).filter_by(cv_profile_id=profile_id).order_by(Education.order_index).all()
    skills = db.query(Skill).filter_by(cv_profile_id=profile_id).order_by(Skill.id).all()
    projects = db.query(Project).filter_by(cv_profile_id=profile_id).order_by(Project.order_index).all()
    certifications = db.query(Certification).filter_by(cv_profile_id=profile_id).order_by(Certification.order_index).all()
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
@router.get("/profiles/{profile_id}/training")
def list_training(profile_id: int, db: Session = Depends(get_db)):
    return db.query(Training).filter_by(cv_profile_id=profile_id).all()

@router.post("/profiles/{profile_id}/training")
def add_training(profile_id: int, data: TrainingCreate, db: Session = Depends(get_db)):
    max_index = db.query(Training).filter_by(cv_profile_id=profile_id).order_by(Training.order_index.desc()).first()
    next_index = (max_index.order_index + 1) if max_index else 0
    order_index = data.order_index if data.order_index is not None else next_index
    entry = Training(
        cv_profile_id=profile_id,
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
                nlp_chunks = nlp_chunk_text(section_text, max_tokens=800)
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

@router.post("/generate")
def generate_application_materials(data: GenerateRequest):
    # Placeholder: implement actual generation logic
    return {
        "cv": "Generated CV content here...",
        "cover_letter": "Generated cover letter content here..."
    }

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