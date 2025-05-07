from fastapi import FastAPI, APIRouter, Depends, HTTPException, Body, status, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from uuid import uuid4
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="User Service", description="User profile, settings, jobs, applications, and feedback endpoints.")

# Add CORS middleware
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175").split(",")
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
class UserProfile(BaseModel):
    id: str
    name: str
    email: EmailStr
    createdAt: str
    updatedAt: str

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

# --- Dummy in-memory stores for demo ---
users = {}
settings = {}
applications = {}
jobs = {}
feedbacks = []

def get_current_user():
    # Dummy user for demo
    return "demo_user_id"

# --- Profile Endpoints ---
@router.get("/user/profile", response_model=UserProfile)
def get_user_profile(user_id: str = Depends(get_current_user)):
    now = datetime.utcnow().isoformat()
    return users.get(user_id, UserProfile(id=user_id, name="Demo User", email="demo@example.com", createdAt=now, updatedAt=now))

@router.patch("/user/profile")
def patch_user_profile(req: UpdateUserProfileRequest, user_id: str = Depends(get_current_user)):
    now = datetime.utcnow().isoformat()
    profile = UserProfile(id=user_id, name=req.name, email=req.email, createdAt=now, updatedAt=now)
    users[user_id] = profile
    return {"success": True, "profile": profile}

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