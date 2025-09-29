from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from db.database import get_db
from db.models import Certification, UserArcData
from db.repository import BaseRepository
from schemas.certification import CertificationCreate, CertificationUpdate, CertificationOut

router = APIRouter()

def get_certification_repository(db: Session = Depends(get_db)) -> BaseRepository:
    return BaseRepository(Certification, db)

@router.post("/users/{user_id}/certifications", response_model=CertificationOut)
def create_certification(
    user_id: str,
    data: CertificationCreate,
    repo: BaseRepository = Depends(get_certification_repository),
    db: Session = Depends(get_db)
):
    user = db.query(UserArcData).filter_by(user_id=user_id).first()
    if not user:
        user = UserArcData(user_id=user_id, arc_data={})
        db.add(user)
        db.commit()
        db.refresh(user)
    cert_data = data.dict()
    cert_data["user_id"] = user_id
    return repo.create(cert_data)

@router.get("/users/{user_id}/certifications", response_model=List[CertificationOut])
def list_certifications(
    user_id: str,
    repo: BaseRepository = Depends(get_certification_repository)
):
    return repo.get_by_user_id(user_id)

@router.get("/certifications/{id}", response_model=CertificationOut)
def get_certification(
    id: UUID,
    repo: BaseRepository = Depends(get_certification_repository)
):
    cert = repo.get(id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    return cert

@router.delete("/certifications/{id}")
def delete_certification(
    id: UUID,
    repo: BaseRepository = Depends(get_certification_repository)
):
    if not repo.delete(id):
        raise HTTPException(status_code=404, detail="Certification not found")
    return {"success": True}

@router.put("/certifications/{id}", response_model=CertificationOut)
def update_certification(
    id: UUID,
    data: CertificationUpdate,
    repo: BaseRepository = Depends(get_certification_repository)
):
    cert = repo.get(id)
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")
    update_data = data.dict(exclude_unset=True)
    return repo.update(cert, update_data)
