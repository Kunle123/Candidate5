from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.db.database import get_db
from app.db.models import WorkExperience
from app.db.repository import WorkExperienceRepository
from app.schemas.work_experience import WorkExperienceCreate, WorkExperienceUpdate, WorkExperienceOut

router = APIRouter()

def get_work_experience_repository(db: Session = Depends(get_db)) -> WorkExperienceRepository:
    return WorkExperienceRepository(WorkExperience, db)

@router.post("/users/{user_id}/work_experience", response_model=WorkExperienceOut)
def create_work_experience(
    user_id: str,
    data: WorkExperienceCreate,
    repo: WorkExperienceRepository = Depends(get_work_experience_repository)
):
    existing = repo.get_ordered_by_user(user_id)
    next_index = len(existing)
    work_exp_data = data.dict()
    work_exp_data.update({
        "user_id": user_id,
        "order_index": data.order_index if data.order_index is not None else next_index
    })
    return repo.create(work_exp_data)

@router.get("/users/{user_id}/work_experience", response_model=List[WorkExperienceOut])
def list_work_experience(
    user_id: str,
    repo: WorkExperienceRepository = Depends(get_work_experience_repository)
):
    return repo.get_ordered_by_user(user_id)

@router.get("/work_experience/{id}", response_model=WorkExperienceOut)
def get_work_experience(
    id: UUID,
    repo: WorkExperienceRepository = Depends(get_work_experience_repository)
):
    work_exp = repo.get(id)
    if not work_exp:
        raise HTTPException(status_code=404, detail="Work experience not found")
    return work_exp

@router.put("/work_experience/{id}", response_model=WorkExperienceOut)
def update_work_experience(
    id: UUID,
    data: WorkExperienceUpdate,
    repo: WorkExperienceRepository = Depends(get_work_experience_repository)
):
    work_exp = repo.get(id)
    if not work_exp:
        raise HTTPException(status_code=404, detail="Work experience not found")
    update_data = data.dict(exclude_unset=True)
    return repo.update(work_exp, update_data)

@router.delete("/work_experience/{id}")
def delete_work_experience(
    id: UUID,
    repo: WorkExperienceRepository = Depends(get_work_experience_repository)
):
    if not repo.delete(id):
        raise HTTPException(status_code=404, detail="Work experience not found")
    return {"success": True}

@router.patch("/work_experience/{id}/reorder", response_model=WorkExperienceOut)
def reorder_work_experience(
    id: UUID,
    new_order_index: int = Body(...),
    repo: WorkExperienceRepository = Depends(get_work_experience_repository)
):
    result = repo.reorder(id, new_order_index)
    if not result:
        raise HTTPException(status_code=404, detail="Work experience not found")
    return result
