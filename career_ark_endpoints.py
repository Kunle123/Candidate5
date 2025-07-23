from fastapi import APIRouter, HTTPException, Path, Body, Depends
from sqlalchemy.orm import Session
from .career_ark_models import Skill, CVProfile
from .db import get_db
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

# --- Pydantic Schemas ---
class SkillCreate(BaseModel):
    skill: str

class SkillOut(BaseModel):
    id: int
    skill: str
    class Config:
        orm_mode = True

class ProfileCreate(BaseModel):
    user_id: str
    name: str
    email: Optional[str] = None

class ProfileUpdate(BaseModel):
    name: Optional[str]
    email: Optional[str]

class ProfileOut(BaseModel):
    id: int
    user_id: str
    name: str
    email: Optional[str]
    class Config:
        orm_mode = True

# --- Skills Endpoints ---
@router.post("/profiles/{profile_id}/skills", response_model=SkillOut)
def add_skill(profile_id: int, data: SkillCreate, db: Session = Depends(get_db)):
    entry = Skill(user_id=profile_id, skill=data.skill)
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
    return db.query(Skill).filter_by(user_id=profile_id).all()

@router.delete("/skills/{id}")
def delete_skill(id: int, db: Session = Depends(get_db)):
    entry = db.query(Skill).get(id)
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(entry)
    db.commit()
    return {"success": True}

# --- Profile Endpoints ---
@router.post("/profiles", response_model=ProfileOut)
def create_profile(data: ProfileCreate, db: Session = Depends(get_db)):
    entry = CVProfile(user_id=data.user_id, name=data.name, email=data.email)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.get("/profiles/{user_id}", response_model=ProfileOut)
def get_profile(user_id: str, db: Session = Depends(get_db)):
    entry = db.query(CVProfile).filter_by(user_id=user_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Not found")
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