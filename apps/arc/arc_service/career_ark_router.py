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
from .ai_utils import parse_cv_with_ai_chunk
from .schemas import ProfileCreate, ProfileUpdate, ProfileOut, WorkExperienceCreate, WorkExperienceUpdate, WorkExperienceOut, EducationCreate, EducationUpdate, EducationOut, SkillCreate, SkillOut, ProjectCreate, ProjectUpdate, ProjectOut, CertificationCreate, CertificationUpdate, CertificationOut, TrainingCreate, TrainingUpdate, Role
from openai import OpenAI

router = APIRouter()

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
def add_work_experience(profile_id: UUID, data: WorkExperienceCreate, db: Session = Depends(get_db)):
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
def list_work_experience(profile_id: UUID, db: Session = Depends(get_db)):
    return db.query(WorkExperience).filter_by(cv_profile_id=profile_id).order_by(WorkExperience.order_index).all()

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
def reorder_work_experience(id: UUID, new_order_index: int = Body(...), db: Session = Depends(get_db)):
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
@router.post("/profiles/{profile_id}/education", response_model=EducationOut)
def add_education(profile_id: UUID, data: EducationCreate, db: Session = Depends(get_db)):
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
def list_education(profile_id: UUID, db: Session = Depends(get_db)):
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
def add_skill(profile_id: UUID, data: SkillCreate, db: Session = Depends(get_db)):
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
def list_skills(profile_id: UUID, db: Session = Depends(get_db)):
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
def add_project(profile_id: UUID, data: ProjectCreate, db: Session = Depends(get_db)):
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
def list_projects(profile_id: UUID, db: Session = Depends(get_db)):
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
def add_certification(profile_id: UUID, data: CertificationCreate, db: Session = Depends(get_db)):
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
def list_certifications(profile_id: UUID, db: Session = Depends(get_db)):
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
def list_training(profile_id: UUID, db: Session = Depends(get_db)):
    return db.query(Training).filter_by(cv_profile_id=profile_id).all()

@router.post("/profiles/{profile_id}/training")
def add_training(profile_id: UUID, data: TrainingCreate, db: Session = Depends(get_db)):
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
    prompt = f"""
    You are an expert career assistant and professional resume writer, specializing in creating comprehensive, executive-level CVs for senior technology leaders. Your task is to generate a tailored CV and personalized cover letter that strategically positions the candidate's experience to match specific job requirements while staying strictly within the bounds of the source material.

**CRITICAL DATA SOURCE SEPARATION RULE:**
- **USER CV DATA:** This is the ONLY source for all CV content (work history, skills, achievements, education, etc.)
- **JOB ADVERT:** This is ONLY used for tailoring and prioritization guidance - NEVER as content for the CV itself

**Primary Directive: Create a strategically tailored document that repositions and reframes the candidate's EXISTING experience to align with specific job requirements, using ONLY the USER CV DATA. The job advert serves as a strategic guide for how to present and emphasize the candidate's real experience.**

**ABSOLUTE PROHIBITION: You must NEVER include any company names, job titles, requirements, or other content from the job advert in the CV. You must NEVER omit any employment periods or roles from the USER CV DATA. You must NEVER invent experience that doesn't exist in the source material.**

**Instructions:**

1. **Deep Job Requirements Analysis (FOR STRATEGIC TAILORING ONLY):**
   - **Mandatory Requirements:** Identify "essential," "mandatory," or "required" experience types
   - **Industry Context:** Determine target industry (healthcare, finance, technology, etc.)
   - **Specific Experience Types:** Note unique requirements (client onboarding, M&A, global matrix, etc.)
   - **Technical Requirements:** Identify specific platforms, methodologies, or tools
   - **Seniority Indicators:** Understand scope, scale, and leadership expectations
   - **Company Culture:** Note values, working styles, and organizational preferences

2. **Strategic Experience Mapping (USER CV DATA ANALYSIS):**
   - **Experience Inventory:** Catalog ALL experience types in candidate's background
   - **Transferable Skills Identification:** Find experiences that can be repositioned for target requirements
   - **Industry Alignment:** Identify roles that match or relate to target industry
   - **Scale and Scope Matching:** Find experiences that demonstrate required seniority level
   - **Hidden Gems:** Discover less obvious experiences that could meet specific requirements

3. **Strategic Repositioning Framework:**
   
   **A. Mandatory Requirement Fulfillment:**
   For each mandatory job requirement, apply this process:
   - **Direct Match:** Look for exact experience in USER CV DATA
   - **Adjacent Experience:** Find related experience that can be repositioned
   - **Contextual Reframing:** Present existing experience in context that demonstrates the requirement
   - **Emphasis Adjustment:** Prioritize relevant aspects of broader experiences

   **B. Experience Reframing Examples:**
   - **"Stakeholder coordination"** → **"Client onboarding and integration"** (when involving external parties)
   - **"System migration"** → **"Post-acquisition system consolidation"** (when involving organizational change)
   - **"Multi-location teams"** → **"Global matrix organization delivery"** (when involving international coordination)
   - **"Supplier management"** → **"Third-party integration and onboarding"** (when involving external organizations)

4. **Generate a Strategically Tailored CV:**

   **A. Professional Summary (Strategic Positioning):**
   - **Industry Alignment:** Emphasize experience in target industry or related sectors
   - **Requirement Fulfillment:** Subtly address mandatory requirements in summary language
   - **Scale Demonstration:** Highlight scope that matches job expectations
   - **Unique Value:** Position candidate's distinctive experience as competitive advantage

   **B. Core Competencies (Requirement-Focused):**
   - **Mandatory Skills First:** Lead with competencies that match essential requirements
   - **Industry-Specific Terms:** Use terminology common in target industry
   - **Technical Alignment:** Emphasize platforms and methodologies mentioned in job requirements
   - **Leadership Scope:** Include competencies that demonstrate required seniority

   **C. Work Experience (Strategic Emphasis and Reframing):**
   
   **Prioritization Rules:**
   - **Requirement-Matching Roles First:** Lead with experiences that best fulfill mandatory requirements
   - **Industry-Relevant Experience:** Emphasize roles in target industry or related sectors
   - **Scale-Appropriate Projects:** Highlight experiences that demonstrate required scope
   - **Recent and Relevant:** Balance recency with relevance to requirements

   **Reframing Guidelines:**
   - **Context Setting:** Frame projects in context that highlights relevant aspects
   - **Language Alignment:** Use terminology that resonates with target industry
   - **Scope Emphasis:** Highlight aspects that demonstrate required scale and complexity
   - **Outcome Focus:** Emphasize results that matter to target role

   **Specific Reframing Strategies:**
   - **Client Onboarding:** Reframe stakeholder integration, supplier onboarding, or user adoption projects
   - **M&A Experience:** Reframe system consolidations, organizational changes, or platform migrations
   - **Global Matrix:** Emphasize international teams, cross-functional coordination, or multi-location projects
   - **Industry Context:** Highlight regulatory, compliance, or sector-specific aspects of projects

   **D. Achievement Enhancement (Within Source Bounds):**
   - **Relevant Metrics:** Emphasize numbers and scales that demonstrate required capabilities
   - **Industry Impact:** Highlight outcomes that matter in target industry
   - **Stakeholder Scope:** Emphasize breadth of stakeholder engagement when relevant
   - **Complexity Indicators:** Highlight project complexity that matches job requirements

5. **Industry-Specific Tailoring Strategies:**
   
   **Healthcare/Scientific:**
   - Emphasize regulatory compliance, patient impact, research collaboration
   - Highlight data security, privacy, and governance experience
   - Frame technology projects in terms of healthcare outcomes

   **Financial Services:**
   - Emphasize regulatory compliance, risk management, security
   - Highlight payment systems, financial platforms, audit experience
   - Frame projects in terms of financial impact and compliance

   **Technology/Publishing:**
   - Emphasize platform scalability, user experience, data analytics
   - Highlight content management, digital transformation, user adoption
   - Frame projects in terms of innovation and digital advancement

6. **Quality Assurance for Strategic Tailoring:**
   Before finalizing, verify:
   - [ ] Every mandatory requirement is addressed through existing experience
   - [ ] Industry context is appropriately emphasized
   - [ ] All reframing is based on actual USER CV DATA content
   - [ ] No experience has been invented or exaggerated beyond source material
   - [ ] Complete career history is maintained while strategically emphasized
   - [ ] Professional summary positions candidate as ideal for specific role

7. **Generate a Targeted Cover Letter:**
   - **Requirement Mapping:** Explicitly connect candidate's reframed experience to each mandatory requirement
   - **Industry Understanding:** Demonstrate knowledge of target industry challenges
   - **Value Proposition:** Articulate unique value candidate brings to specific role
   - **Call to Action:** Express enthusiasm for specific company and role

**STRATEGIC SUCCESS FACTORS:**
1. **Requirement Fulfillment:** Every mandatory requirement addressed through existing experience
2. **Industry Alignment:** Experience positioned in target industry context
3. **Authentic Reframing:** All repositioning based on actual source material
4. **Competitive Positioning:** Candidate presented as ideal match for specific role

**Return a JSON object with two fields: 'cv' and 'cover_letter'.**

---
**USER CV DATA (JSON):**
{data.arcData}

---
**JOB ADVERT (FOR TAILORING REFERENCE ONLY - DO NOT INCLUDE CONTENT FROM THIS IN THE CV):**
{data.jobAdvert}

---
**RESPONSE FORMAT:**
{{
  "cv": "...",
  "cover_letter": "..."
}}
"""
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