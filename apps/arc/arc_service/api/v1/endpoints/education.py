from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from db.database import get_db
from db.models import Education
from db.repository import EducationRepository
from schemas.education import EducationCreate, EducationUpdate, EducationOut
from app.db.models import UserArcData
from app.db.repository import BaseRepository

router = APIRouter()

def get_education_repository(db: Session = Depends(get_db)) -> EducationRepository:
    return EducationRepository(Education, db)

@router.post("/users/{user_id}/education", response_model=EducationOut)
def create_education(
    user_id: str,
    data: EducationCreate,
    repo: EducationRepository = Depends(get_education_repository),
    db: Session = Depends(get_db)
):
    # Ensure user exists in user_arc_data
    user = db.query(UserArcData).filter_by(user_id=user_id).first()
    if not user:
        user = UserArcData(user_id=user_id, arc_data={})
        db.add(user)
        db.commit()
        db.refresh(user)
    existing = db.query(Education).filter_by(user_id=user_id).all()
    next_index = len(existing)
    edu_data = data.dict()
    edu_data.update({
        "user_id": user_id,
        "order_index": data.order_index if data.order_index is not None else next_index
    })
    return repo.create(edu_data)

@router.get("/users/{user_id}/education", response_model=List[EducationOut])
def list_education(
    user_id: str,
    repo: EducationRepository = Depends(get_education_repository)
):
    return repo.db.query(Education).filter_by(user_id=user_id).order_by(Education.order_index).all()

@router.get("/education/{id}", response_model=EducationOut)
def get_education(
    id: UUID,
    repo: EducationRepository = Depends(get_education_repository)
):
    edu = repo.get(id)
    if not edu:
        raise HTTPException(status_code=404, detail="Education record not found")
    return edu

@router.put("/education/{id}", response_model=EducationOut)
def update_education(
    id: UUID,
    data: EducationUpdate,
    repo: EducationRepository = Depends(get_education_repository)
):
    edu = repo.get(id)
    if not edu:
        raise HTTPException(status_code=404, detail="Education record not found")
    update_data = data.dict(exclude_unset=True)
    return repo.update(edu, update_data)

@router.delete("/education/{id}")
def delete_education(
    id: UUID,
    repo: EducationRepository = Depends(get_education_repository)
):
    if not repo.delete(id):
        raise HTTPException(status_code=404, detail="Education record not found")
    return {"success": True}

@router.patch("/education/{id}/reorder", response_model=EducationOut)
def reorder_education(
    id: UUID,
    new_order_index: int = Body(...),
    repo: EducationRepository = Depends(get_education_repository)
):
    result = repo.reorder(id, new_order_index)
    if not result:
        raise HTTPException(status_code=404, detail="Education record not found")
    return result
