from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from db.database import get_db
from db.models import Skill
from db.repository import BaseRepository
from schemas import SkillCreate, SkillOut
from app.db.models import UserArcData

router = APIRouter()

def get_skill_repository(db: Session = Depends(get_db)) -> BaseRepository:
    return BaseRepository(Skill, db)

@router.post("/users/{user_id}/skills", response_model=SkillOut)
def create_skill(
    user_id: str,
    data: SkillCreate,
    repo: BaseRepository = Depends(get_skill_repository),
    db: Session = Depends(get_db)
):
    # Ensure user exists in user_arc_data
    user = db.query(UserArcData).filter_by(user_id=user_id).first()
    if not user:
        user = UserArcData(user_id=user_id, arc_data={})
        db.add(user)
        db.commit()
        db.refresh(user)
    skill_data = data.dict()
    skill_data["user_id"] = user_id
    return repo.create(skill_data)

@router.get("/users/{user_id}/skills", response_model=List[SkillOut])
def list_skills(
    user_id: str,
    repo: BaseRepository = Depends(get_skill_repository)
):
    return repo.get_by_user_id(user_id)

@router.get("/skills/{id}", response_model=SkillOut)
def get_skill(
    id: UUID,
    repo: BaseRepository = Depends(get_skill_repository)
):
    skill = repo.get(id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill

@router.delete("/skills/{id}")
def delete_skill(
    id: UUID,
    repo: BaseRepository = Depends(get_skill_repository)
):
    if not repo.delete(id):
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"success": True}
