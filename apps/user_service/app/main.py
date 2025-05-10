from fastapi import FastAPI, APIRouter, Depends, HTTPException, Body, status, BackgroundTasks, Security, Header
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from uuid import uuid4
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import os
from sqlalchemy.orm import Session
from .models import UserProfile as UserProfileORM
from .db import get_db

app = FastAPI(title="User Service", description="User profile, settings, jobs, applications, and feedback endpoints.")

# Add CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175,https://c5-frontend-pied.vercel.app").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

router = APIRouter()

# --- Models ---
class UserProfileSchema(BaseModel):
    id: str
    email: EmailStr
    name: str
    created_at: str
    updated_at: str
    model_config = {
        "from_attributes": True
    }

class UpdateUserProfileRequest(BaseModel):
    name: str
    email: EmailStr

class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

class UserSettings(BaseModel):
    notifications: dict = Field(default_factory=lambda: {"email": True, "sms": False})
    theme: Literal["light", "dark"] = "light"

class UpdateUserSettingsRequest(BaseModel):
    notifications: Optional[dict]
    theme: Optional[Literal["light", "dark"]]

class ApplicationHistoryItem(BaseModel):
    id: str
    jobTitle: str
    company: str
    appliedAt: str
    cvId: str
    coverLetterId: str

class ApplicationDetails(BaseModel):
    id: str
    jobTitle: str
    company: str
    appliedAt: str
    cv: dict
    coverLetter: dict

class JobItem(BaseModel):
    id: str
    title: str
    company: str
    description: str
    status: Literal["saved", "applied", "archived"]
    createdAt: str
    updatedAt: str

class CreateJobRequest(BaseModel):
    title: str
    company: str
    description: str

class UpdateJobRequest(BaseModel):
    title: Optional[str]
    company: Optional[str]
    description: Optional[str]
    status: Optional[Literal["saved", "applied", "archived"]]

class FeedbackRequest(BaseModel):
    message: str
    type: Literal["bug", "feature", "general"]
    email: Optional[EmailStr]

class CreateUserProfileRequest(BaseModel):
    id: str
    email: EmailStr
    name: str

# --- Dummy in-memory stores for demo ---
users = {}
settings = {}
applications = {}
jobs = {}
feedbacks = []

ADMIN_USER_ID = "50a5cb6e-6129-4f19-84cc-7afd6eab4363"  # Replace with your actual admin user ID

INTER_SERVICE_SECRET = os.getenv("INTER_SERVICE_SECRET", "")

def get_current_user():
    # Dummy user for demo
    return "demo_user_id"

def get_admin_user(user_id: str = Depends(get_current_user)):
    if user_id != ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return user_id

# --- Profile Endpoints ---
@router.get("/user/list", response_model=List[UserProfileSchema])
def list_all_users(admin_user_id: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """List all users (admin only)."""
    return db.query(UserProfileORM).all()

@router.get("/user/profile", response_model=UserProfileSchema)
def get_user_profile(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
    if user:
        return user
    raise HTTPException(status_code=404, detail="User not found")

@router.patch("/user/profile", response_model=UserProfileSchema)
def patch_user_profile(req: UpdateUserProfileRequest, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
    now = datetime.utcnow()
    if user:
        user.name = req.name
        user.email = req.email
        user.updated_at = now
    else:
        user = UserProfileORM(
            id=user_id,
            name=req.name,
            email=req.email,
            created_at=now,
            updated_at=now
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/user/send-verification")
def send_verification_email(background_tasks: BackgroundTasks, user_id: str = Depends(get_current_user)):
    # Stub: Simulate sending email
    print(f"Verification email sent to user {user_id}")
    return {"success": True, "message": "Verification email sent."}

@router.post("/user/change-password")
def change_password(old_password: str, new_password: str, user_id: str = Depends(get_current_user)):
    # Stub: Simulate password change
    print(f"Password changed for user {user_id}")
    return {"success": True, "message": "Password changed."}

@router.post("/user/profile", response_model=UserProfileSchema)
def create_user_profile(
    req: CreateUserProfileRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    if authorization != f"Bearer {INTER_SERVICE_SECRET}":
        raise HTTPException(status_code=403, detail="Forbidden: Invalid interservice secret.")
    user = db.query(UserProfileORM).filter(UserProfileORM.id == req.id).first()
    if user:
        raise HTTPException(status_code=409, detail="User already exists.")
    now = datetime.utcnow()
    user = UserProfileORM(
        id=req.id,
        email=req.email,
        name=req.name,
        created_at=now,
        updated_at=now
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.get("/user/{user_id}", response_model=UserProfileSchema)
def get_user_profile_by_id(user_id: str, db: Session = Depends(get_db)):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
    if user:
        return user
    raise HTTPException(status_code=404, detail="User not found")

# --- Settings Endpoints ---
@router.get("/user/settings", response_model=UserSettings)
def get_user_settings(user_id: str = Depends(get_current_user)):
    return settings.get(user_id, UserSettings())

@router.put("/user/settings")
def update_user_settings(req: UpdateUserSettingsRequest, user_id: str = Depends(get_current_user)):
    s = settings.get(user_id, UserSettings())
    if req.notifications is not None:
        s.notifications = req.notifications
    if req.theme is not None:
        s.theme = req.theme
    settings[user_id] = s
    return {"success": True, "settings": s}

# --- Application History Endpoints ---
@router.get("/applications/history", response_model=List[ApplicationHistoryItem])
def list_application_history(user_id: str = Depends(get_current_user)):
    return list(applications.get(user_id, []))

@router.get("/applications/{app_id}", response_model=ApplicationDetails)
def get_application_details(app_id: str, user_id: str = Depends(get_current_user)):
    # Dummy: return a sample application
    now = datetime.utcnow().isoformat()
    return ApplicationDetails(
        id=app_id,
        jobTitle="Sample Job",
        company="Sample Company",
        appliedAt=now,
        cv={"id": "cv1", "content": "CV content"},
        coverLetter={"id": "cl1", "content": "Cover letter content"}
    )

# --- Job Management Endpoints ---
@router.get("/jobs", response_model=List[JobItem])
def list_jobs(user_id: str = Depends(get_current_user)):
    return list(jobs.get(user_id, []))

@router.post("/jobs")
def save_job(req: CreateJobRequest, user_id: str = Depends(get_current_user)):
    now = datetime.utcnow().isoformat()
    job = JobItem(id=str(uuid4()), title=req.title, company=req.company, description=req.description, status="saved", createdAt=now, updatedAt=now)
    jobs.setdefault(user_id, []).append(job)
    return {"success": True, "job": job}

@router.put("/jobs/{job_id}")
def update_job(job_id: str, req: UpdateJobRequest, user_id: str = Depends(get_current_user)):
    user_jobs = jobs.get(user_id, [])
    for job in user_jobs:
        if job.id == job_id:
            if req.title is not None:
                job.title = req.title
            if req.company is not None:
                job.company = req.company
            if req.description is not None:
                job.description = req.description
            if req.status is not None:
                job.status = req.status
            job.updatedAt = datetime.utcnow().isoformat()
            return {"success": True, "job": job}
    raise HTTPException(status_code=404, detail="Job not found")

@router.delete("/jobs/{job_id}")
def delete_job(job_id: str, user_id: str = Depends(get_current_user)):
    user_jobs = jobs.get(user_id, [])
    jobs[user_id] = [job for job in user_jobs if job.id != job_id]
    return {"success": True}

# --- Feedback Endpoint ---
@router.post("/feedback")
def submit_feedback(req: FeedbackRequest, user_id: Optional[str] = Depends(get_current_user)):
    feedbacks.append({"user_id": user_id, **req.dict()})
    return {"success": True}

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(router, prefix="/api") 