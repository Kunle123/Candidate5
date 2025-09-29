from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from db.database import get_db
from db.models import Training, UserArcData
from db.repository import BaseRepository
from schemas.training import TrainingCreate, TrainingUpdate, TrainingOut

router = APIRouter()

def get_training_repository(db: Session = Depends(get_db)) -> BaseRepository:
    return BaseRepository(Training, db)

@router.post("/users/{user_id}/training", response_model=TrainingOut)
def create_training(
    user_id: str,
    data: TrainingCreate,
    repo: BaseRepository = Depends(get_training_repository),
    db: Session = Depends(get_db)
):
    user = db.query(UserArcData).filter_by(user_id=user_id).first()
    if not user:
        user = UserArcData(user_id=user_id, arc_data={})
        db.add(user)
        db.commit()
        db.refresh(user)
    training_data = data.dict()
    training_data["user_id"] = user_id
    return repo.create(training_data)

@router.get("/users/{user_id}/training", response_model=List[TrainingOut])
def list_training(
    user_id: str,
    repo: BaseRepository = Depends(get_training_repository)
):
    return repo.get_by_user_id(user_id)

@router.get("/training/{id}", response_model=TrainingOut)
def get_training(
    id: UUID,
    repo: BaseRepository = Depends(get_training_repository)
):
    training = repo.get(id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    return training

@router.delete("/training/{id}")
def delete_training(
    id: UUID,
    repo: BaseRepository = Depends(get_training_repository)
):
    if not repo.delete(id):
        raise HTTPException(status_code=404, detail="Training not found")
    return {"success": True}

@router.put("/training/{id}", response_model=TrainingOut)
def update_training(
    id: UUID,
    data: TrainingUpdate,
    repo: BaseRepository = Depends(get_training_repository)
):
    training = repo.get(id)
    if not training:
        raise HTTPException(status_code=404, detail="Training not found")
    update_data = data.dict(exclude_unset=True)
    return repo.update(training, update_data)
