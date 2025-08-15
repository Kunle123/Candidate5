from fastapi import FastAPI, APIRouter, Depends, HTTPException, Body, status, BackgroundTasks, Security, Header, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal, Union
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
from sqlalchemy.orm import Session
from .models import UserProfile as UserProfileORM, TopupCredits
from .db import get_db
from fastapi.security import OAuth2PasswordBearer
import jwt
import requests
from sqlalchemy import and_
from datetime import date

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="User Service", description="User profile, settings, jobs, applications, and feedback endpoints.")

# Add CORS middleware with updated origins
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175,https://c5-frontend-pied.vercel.app,https://c5-api-gateway-production.up.railway.app,https://candidate5.co.uk,https://www.candidate5.co.uk").split(",")
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
class UserProfileResponse(BaseModel):
    id: Union[str, UUID]
    email: EmailStr
    name: str
    address_line1: Optional[str] = None
    city_state_postal: Optional[str] = None
    linkedin: Optional[str] = None
    phone_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {
        "from_attributes": True
    }

class UpdateUserProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    address_line1: Optional[str] = None
    city_state_postal: Optional[str] = None
    linkedin: Optional[str] = None
    phone_number: Optional[str] = None

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
    phone_number: Optional[str] = None

class UserCreditsResponse(BaseModel):
    monthly_credits_remaining: int
    daily_credits_remaining: int
    topup_credits_remaining: int
    subscription_type: str

class UseCreditsRequest(BaseModel):
    amount: int = 1

class UpdateSubscriptionRequest(BaseModel):
    user_id: str
    subscription_type: str  # 'free', 'monthly', 'annual'

class TopupCreditsRequest(BaseModel):
    user_id: str

# --- Dummy in-memory stores for demo ---
users = {}
settings = {}
applications = {}
jobs = {}
feedbacks = []

ADMIN_USER_ID = "50a5cb6e-6129-4f19-84cc-7afd6eab4363"  # Replace with your actual admin user ID

ARC_SERVICE_URL = os.getenv("ARC_SERVICE_URL", "http://arc_service:8080/api/career-ark")
INTER_SERVICE_SECRET = os.getenv("INTER_SERVICE_SECRET", "")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("id")  # Use 'id' as in your JWT
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_admin_user(user_id: str = Depends(get_current_user)):
    if user_id != ADMIN_USER_ID:
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return user_id

def create_cv_profile_in_arc(user_id, name, email):
    url = f"{ARC_SERVICE_URL}/profiles"
    headers = {
        "Authorization": f"Bearer {INTER_SERVICE_SECRET}",
        "Content-Type": "application/json"
    }
    data = {
        "user_id": user_id,
        "name": name,
        "email": email
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to create CV profile in arc service: {e}")

def reset_user_credits(user: UserProfileORM, db: Session):
    now = datetime.utcnow()
    today = date.today()
    # Reset daily credits if new day
    if not user.last_daily_reset or user.last_daily_reset.date() != today:
        if user.subscription_type == 'monthly':
            user.daily_credits_remaining = 3
        elif user.subscription_type == 'annual':
            user.daily_credits_remaining = 5
        else:
            user.daily_credits_remaining = 0
        user.last_daily_reset = now
    # Reset monthly credits if new month
    if not user.last_monthly_reset or user.last_monthly_reset.month != now.month or user.last_monthly_reset.year != now.year:
        if user.subscription_type in ['monthly', 'annual']:
            user.monthly_credits_remaining = 50
        else:
            user.monthly_credits_remaining = 3
        user.last_monthly_reset = now
    # Remove expired top-up credits
    expired_topups = db.query(TopupCredits).filter(
        and_(TopupCredits.user_id == user.id, TopupCredits.topup_credits_expiry < now)
    ).all()
    for topup in expired_topups:
        db.delete(topup)
    db.commit()

# --- Profile Endpoints ---
@router.get("/user/list", response_model=List[UserProfileResponse])
def list_all_users(admin_user_id: str = Depends(get_admin_user), db: Session = Depends(get_db)):
    """List all users (admin only)."""
    try:
        users = db.query(UserProfileORM).all()
        logger.info(f"Successfully retrieved {len(users)} users")
        return users
    except Exception as e:
        logger.error(f"Error retrieving users: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while retrieving users")

@router.get("/user/profile", response_model=UserProfileResponse)
def get_user_profile(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
        if not user:
            logger.warning(f"User profile not found for user_id: {user_id}")
            raise HTTPException(status_code=404, detail="User profile not found")
        logger.info(f"Successfully retrieved profile for user_id: {user_id}")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while retrieving user profile")

@router.put("/user/profile", response_model=UserProfileResponse)
def put_user_profile(req: UpdateUserProfileRequest, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
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
        logger.info(f"Successfully put (fully updated) profile for user_id: {user_id}")
        return user
    except Exception as e:
        logger.error(f"Error putting user profile: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error while putting user profile")

@router.patch("/user/profile", response_model=UserProfileResponse)
def patch_user_profile(req: UpdateUserProfileRequest, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
        now = datetime.utcnow()
        if not user:
            raise HTTPException(status_code=404, detail="User profile not found")
        if req.name is not None:
            user.name = req.name
        if req.email is not None:
            user.email = req.email
        if req.address_line1 is not None:
            user.address_line1 = req.address_line1
        if req.city_state_postal is not None:
            user.city_state_postal = req.city_state_postal
        if req.linkedin is not None:
            user.linkedin = req.linkedin
        if req.phone_number is not None:
            user.phone_number = req.phone_number
        user.updated_at = now
        db.commit()
        db.refresh(user)
        logger.info(f"Successfully PATCHed profile for user_id: {user_id}")
        return user
    except Exception as e:
        logger.error(f"Error patching user profile: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error while patching user profile")

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

@router.post("/user/profile", response_model=UserProfileResponse)
def create_user_profile(
    req: CreateUserProfileRequest,
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    try:
        if authorization != f"Bearer {INTER_SERVICE_SECRET}":
            logger.warning("Invalid interservice secret provided")
            raise HTTPException(status_code=403, detail="Forbidden: Invalid interservice secret.")
        
        # Check if user already exists
        existing_user = db.query(UserProfileORM).filter(UserProfileORM.id == req.id).first()
        if existing_user:
            logger.warning(f"User already exists with id: {req.id}")
            raise HTTPException(status_code=409, detail="User already exists.")
        
        # Create new user
        now = datetime.utcnow()
        new_user = UserProfileORM(
            id=req.id,
            email=req.email,
            name=req.name,
            created_at=now,
            updated_at=now
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Inter-service call to create CV profile in arc service
        create_cv_profile_in_arc(new_user.id, new_user.name, new_user.email)
        
        logger.info(f"Successfully created profile for user_id: {req.id}")
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user profile: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error while creating user profile")

@router.get("/user/{user_id}", response_model=UserProfileResponse)
def get_user_profile_by_id(user_id: str, db: Session = Depends(get_db)):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
    if user:
        return user
    raise HTTPException(status_code=404, detail="User not found")

@router.get("/users/me", response_model=UserProfileResponse)
def get_my_profile(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
    if user:
        return user
    raise HTTPException(status_code=404, detail="User not found")

@router.get("/user/credits", response_model=UserCreditsResponse)
def get_user_credits(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    reset_user_credits(user, db)
    now = datetime.utcnow()
    topup_credits = db.query(TopupCredits).filter(
        TopupCredits.user_id == user_id,
        TopupCredits.topup_credits_expiry > now
    ).all()
    total_topup_credits = sum(t.topup_credits_remaining for t in topup_credits)
    return UserCreditsResponse(
        monthly_credits_remaining=user.monthly_credits_remaining,
        daily_credits_remaining=user.daily_credits_remaining,
        topup_credits_remaining=total_topup_credits,
        subscription_type=user.subscription_type
    )

@router.post("/user/credits/use", response_model=UserCreditsResponse)
def use_user_credits(
    req: UseCreditsRequest = Body(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    reset_user_credits(user, db)
    now = datetime.utcnow()
    amount = req.amount
    # 1. Use valid top-up credits first
    topups = db.query(TopupCredits).filter(
        TopupCredits.user_id == user_id,
        TopupCredits.topup_credits_expiry > now,
        TopupCredits.topup_credits_remaining > 0
    ).order_by(TopupCredits.topup_credits_expiry.asc()).all()
    for topup in topups:
        if amount <= 0:
            break
        use = min(topup.topup_credits_remaining, amount)
        topup.topup_credits_remaining -= use
        amount -= use
    # 2. Use daily credits
    if amount > 0 and user.daily_credits_remaining > 0:
        use = min(user.daily_credits_remaining, amount)
        user.daily_credits_remaining -= use
        amount -= use
    # 3. Use monthly credits
    if amount > 0 and user.monthly_credits_remaining > 0:
        use = min(user.monthly_credits_remaining, amount)
        user.monthly_credits_remaining -= use
        amount -= use
    if amount > 0:
        db.rollback()
        raise HTTPException(status_code=402, detail="Insufficient credits")
    db.commit()
    # Recalculate top-up credits
    topup_credits = db.query(TopupCredits).filter(
        TopupCredits.user_id == user_id,
        TopupCredits.topup_credits_expiry > now
    ).all()
    total_topup_credits = sum(t.topup_credits_remaining for t in topup_credits)
    return UserCreditsResponse(
        monthly_credits_remaining=user.monthly_credits_remaining,
        daily_credits_remaining=user.daily_credits_remaining,
        topup_credits_remaining=total_topup_credits,
        subscription_type=user.subscription_type
    )

@router.post("/user/credits/reset", response_model=UserCreditsResponse)
def admin_reset_user_credits(
    user_id: str = Body(...),
    admin_user_id: str = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    reset_user_credits(user, db)
    now = datetime.utcnow()
    topup_credits = db.query(TopupCredits).filter(
        TopupCredits.user_id == user_id,
        TopupCredits.topup_credits_expiry > now
    ).all()
    total_topup_credits = sum(t.topup_credits_remaining for t in topup_credits)
    return UserCreditsResponse(
        monthly_credits_remaining=user.monthly_credits_remaining,
        daily_credits_remaining=user.daily_credits_remaining,
        topup_credits_remaining=total_topup_credits,
        subscription_type=user.subscription_type
    )

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

@router.post("/user/subscription/update", status_code=200)
def update_user_subscription(req: UpdateSubscriptionRequest, db: Session = Depends(get_db)):
    user = db.query(UserProfileORM).filter(UserProfileORM.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.subscription_type = req.subscription_type
    # Reset credits as per plan
    now = datetime.utcnow()
    if req.subscription_type == 'monthly':
        user.monthly_credits_remaining = 50
        user.daily_credits_remaining = 3
    elif req.subscription_type == 'annual':
        user.monthly_credits_remaining = 50
        user.daily_credits_remaining = 5
    else:
        user.monthly_credits_remaining = 3
        user.daily_credits_remaining = 0
    user.last_monthly_reset = now
    user.last_daily_reset = now
    db.commit()
    return {"status": "success", "subscription_type": user.subscription_type}

@router.post("/user/topup/add", status_code=200)
def add_topup_credits(req: TopupCreditsRequest, db: Session = Depends(get_db)):
    from datetime import timedelta
    user = db.query(UserProfileORM).filter(UserProfileORM.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    now = datetime.utcnow()
    expiry = now + timedelta(days=30)
    from .models import TopupCredits
    topup = TopupCredits(
        user_id=user.id,
        topup_credits_remaining=50,
        topup_credits_expiry=expiry
    )
    db.add(topup)
    db.commit()
    return {"status": "success", "topup_credits_remaining": topup.topup_credits_remaining, "expiry": expiry.isoformat()}

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(router, prefix="/api") 