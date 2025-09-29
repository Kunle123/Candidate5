from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from db.database import get_db
from db.models import Project, UserArcData
from db.repository import BaseRepository
from schemas.project import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter()

def get_project_repository(db: Session = Depends(get_db)) -> BaseRepository:
    return BaseRepository(Project, db)

@router.post("/users/{user_id}/projects", response_model=ProjectOut)
def create_project(
    user_id: str,
    data: ProjectCreate,
    repo: BaseRepository = Depends(get_project_repository),
    db: Session = Depends(get_db)
):
    user = db.query(UserArcData).filter_by(user_id=user_id).first()
    if not user:
        user = UserArcData(user_id=user_id, arc_data={})
        db.add(user)
        db.commit()
        db.refresh(user)
    project_data = data.dict()
    project_data["user_id"] = user_id
    return repo.create(project_data)

@router.get("/users/{user_id}/projects", response_model=List[ProjectOut])
def list_projects(
    user_id: str,
    repo: BaseRepository = Depends(get_project_repository)
):
    return repo.get_by_user_id(user_id)

@router.get("/projects/{id}", response_model=ProjectOut)
def get_project(
    id: UUID,
    repo: BaseRepository = Depends(get_project_repository)
):
    project = repo.get(id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.delete("/projects/{id}")
def delete_project(
    id: UUID,
    repo: BaseRepository = Depends(get_project_repository)
):
    if not repo.delete(id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"success": True}

@router.put("/projects/{id}", response_model=ProjectOut)
def update_project(
    id: UUID,
    data: ProjectUpdate,
    repo: BaseRepository = Depends(get_project_repository)
):
    project = repo.get(id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    update_data = data.dict(exclude_unset=True)
    return repo.update(project, update_data)
