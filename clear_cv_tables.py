from apps.arc.arc_service.db import SessionLocal
from apps.arc.arc_service.models import (
    WorkExperience, Education, Skill, Project, Certification, UserArcData, CVTask
)

def clear_cv_tables():
    db = SessionLocal()
    try:
        db.query(WorkExperience).delete()
        db.query(Education).delete()
        db.query(Skill).delete()
        db.query(Project).delete()
        db.query(Certification).delete()
        db.query(CVTask).delete()
        db.query(UserArcData).delete()
        db.commit()
        print("All CV-related tables cleared.")
    finally:
        db.close()

if __name__ == "__main__":
    clear_cv_tables()


