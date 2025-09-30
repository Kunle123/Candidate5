# DUMMY COMMENT: Force git change for commit
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from db.database import get_db
from db.models import WorkExperience, Education, Skill, Project, Certification
from typing import Dict, Any
from datetime import datetime

router = APIRouter()

@router.get("/users/{user_id}/all_sections")
def get_all_sections(user_id: UUID, db: Session = Depends(get_db)) -> Dict[str, Any]:
    def parse_date(date_str):
        if not date_str:
            return 0
        if str(date_str).strip().lower() == "present":
            return float('inf')
        for fmt in ("%b %Y", "%Y"):
            try:
                return datetime.strptime(date_str, fmt).timestamp()
            except Exception:
                continue
        return 0
    work_experience = db.query(WorkExperience).filter_by(user_id=user_id).all()
    work_experience_sorted = sorted(
        work_experience,
        key=lambda x: parse_date(x.end_date),
        reverse=True
    )
    education = db.query(Education).filter_by(user_id=user_id).order_by(Education.order_index).all()
    skills = db.query(Skill).filter_by(user_id=user_id).order_by(Skill.id).all()
    projects = db.query(Project).filter_by(user_id=user_id).order_by(Project.order_index).all()
    certifications = db.query(Certification).filter_by(user_id=user_id).order_by(Certification.order_index).all()
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
