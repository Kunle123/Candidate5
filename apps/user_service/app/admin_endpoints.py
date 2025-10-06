"""
Admin endpoints for user management
These endpoints are called by the Admin Service
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from datetime import datetime, timedelta
from .db import get_db
from .models import UserProfile, TopupCredits
from pydantic import BaseModel
from uuid import UUID

router = APIRouter(prefix="/api/admin", tags=["admin"])

class UserListItem(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    monthly_credits_remaining: int
    topup_credits: int
    subscription_type: str
    created_at: datetime
    last_monthly_reset: Optional[datetime]
    
    class Config:
        from_attributes = True

class UserDetailOut(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    address_line1: Optional[str]
    city_state_postal: Optional[str]
    linkedin: Optional[str]
    phone_number: Optional[str]
    monthly_credits_remaining: int
    daily_credits_remaining: int
    topup_credits: int
    subscription_type: str
    created_at: datetime
    updated_at: datetime
    last_daily_reset: Optional[datetime]
    last_monthly_reset: Optional[datetime]
    next_credit_reset: Optional[datetime]
    
    class Config:
        from_attributes = True

class CreditAdjustmentRequest(BaseModel):
    amount: int  # Positive to add, negative to deduct

class StatsOut(BaseModel):
    total_users: int
    active_users_7d: int
    active_users_30d: int
    new_signups_7d: int
    new_signups_30d: int

@router.get("/users", response_model=List[UserListItem])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """List all users with pagination and search"""
    query = db.query(UserProfile)
    
    # Apply search filter
    if search:
        query = query.filter(
            or_(
                UserProfile.email.ilike(f"%{search}%"),
                UserProfile.name.ilike(f"%{search}%")
            )
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    # Get topup credits for each user
    result = []
    for user in users:
        topup = db.query(TopupCredits).filter(
            TopupCredits.user_id == user.id
        ).first()
        
        user_dict = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "monthly_credits_remaining": user.monthly_credits_remaining,
            "topup_credits": topup.topup_credits_remaining if topup else 0,
            "subscription_type": user.subscription_type,
            "created_at": user.created_at,
            "last_monthly_reset": user.last_monthly_reset
        }
        result.append(UserListItem(**user_dict))
    
    return result

@router.get("/users/{user_id}", response_model=UserDetailOut)
def get_user_detail(user_id: UUID, db: Session = Depends(get_db)):
    """Get detailed information about a specific user"""
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get topup credits
    topup = db.query(TopupCredits).filter(
        TopupCredits.user_id == user_id
    ).first()
    
    user_dict = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "address_line1": user.address_line1,
        "city_state_postal": user.city_state_postal,
        "linkedin": user.linkedin,
        "phone_number": user.phone_number,
        "monthly_credits_remaining": user.monthly_credits_remaining,
        "daily_credits_remaining": user.daily_credits_remaining,
        "topup_credits": topup.topup_credits_remaining if topup else 0,
        "subscription_type": user.subscription_type,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_daily_reset": user.last_daily_reset,
        "last_monthly_reset": user.last_monthly_reset,
        "next_credit_reset": user.next_credit_reset
    }
    
    return UserDetailOut(**user_dict)

@router.post("/users/{user_id}/credits")
def adjust_user_credits(
    user_id: UUID,
    adjustment: CreditAdjustmentRequest,
    db: Session = Depends(get_db)
):
    """Adjust user credits (add or deduct from topup_credits)"""
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create topup credits record
    topup = db.query(TopupCredits).filter(
        TopupCredits.user_id == user_id
    ).first()
    
    if not topup:
        topup = TopupCredits(
            user_id=user_id,
            topup_credits_remaining=0
        )
        db.add(topup)
    
    # Apply adjustment
    new_balance = topup.topup_credits_remaining + adjustment.amount
    
    # Prevent negative balance
    if new_balance < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient credits. Current balance: {topup.topup_credits_remaining}, Requested deduction: {abs(adjustment.amount)}"
        )
    
    topup.topup_credits_remaining = new_balance
    db.commit()
    
    # Return updated user data
    user_dict = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "monthly_credits_remaining": user.monthly_credits_remaining,
        "topup_credits": topup.topup_credits_remaining,
        "subscription_type": user.subscription_type
    }
    
    return user_dict

@router.get("/stats", response_model=StatsOut)
def get_user_stats(db: Session = Depends(get_db)):
    """Get user statistics for analytics"""
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    
    total_users = db.query(UserProfile).count()
    
    # Note: We don't have last_login in UserProfile, so we'll use created_at as a proxy
    # In a real implementation, you'd track last_login
    new_signups_7d = db.query(UserProfile).filter(
        UserProfile.created_at >= seven_days_ago
    ).count()
    
    new_signups_30d = db.query(UserProfile).filter(
        UserProfile.created_at >= thirty_days_ago
    ).count()
    
    return StatsOut(
        total_users=total_users,
        active_users_7d=new_signups_7d,  # Placeholder
        active_users_30d=new_signups_30d,  # Placeholder
        new_signups_7d=new_signups_7d,
        new_signups_30d=new_signups_30d
    )

