from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from datetime import datetime, timedelta
import httpx
import os
from uuid import UUID
from ..database import get_db
from ..models import Admin, CreditTransaction, AdminAuditLog
from ..schemas import UserListItem, UserDetail, CreditAdjustment, CreditTransactionOut
from ..auth import get_current_admin

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

# External service URLs
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
ARC_SERVICE_URL = os.getenv("ARC_SERVICE_URL")
CV_SERVICE_URL = os.getenv("CV_SERVICE_URL")

@router.get("/", response_model=List[UserListItem])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all users with pagination and search"""
    from ..models import UserProfile
    
    # Log admin action
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="list_users",
        resource_type="user",
        details=f"Listed users (skip={skip}, limit={limit}, search={search})"
    )
    db.add(audit_log)
    db.commit()
    
    # Query users directly from database
    query = db.query(UserProfile)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                UserProfile.email.ilike(search_pattern),
                UserProfile.name.ilike(search_pattern)
            )
        )
    
    users = query.offset(skip).limit(limit).all()
    
    return [
        UserListItem(
            id=user.id,
            email=user.email,
            name=user.name or "",
            monthly_credits_remaining=user.monthly_credits_remaining,
            daily_credits_remaining=user.daily_credits_remaining,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        for user in users
    ]

@router.get("/{user_id}", response_model=UserDetail)
async def get_user_detail(
    user_id: UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific user"""
    from ..models import UserProfile, TopupCredits
    
    # Log admin action
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="view_user",
        resource_type="user",
        resource_id=str(user_id),
        details=f"Viewed user details for {user_id}"
    )
    db.add(audit_log)
    db.commit()
    
    # Query user from database
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get topup credits if available
    topup = db.query(TopupCredits).filter(TopupCredits.user_id == user_id).first()
    topup_credits = topup.topup_credits_remaining if topup else 0
    topup_expiry = topup.topup_credits_expiry if topup else None
    
    return UserDetail(
        id=user.id,
        email=user.email,
        name=user.name or "",
        monthly_credits_remaining=user.monthly_credits_remaining,
        daily_credits_remaining=user.daily_credits_remaining,
        topup_credits=topup_credits,
        topup_credits_expiry=topup_expiry,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

@router.get("/{user_id}/profile")
async def get_user_career_arc(
    user_id: UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get user's complete career arc (profile data)"""
    # Log admin action
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="view_profile",
        resource_type="user",
        resource_id=str(user_id),
        details=f"Viewed career arc for user {user_id}"
    )
    db.add(audit_log)
    db.commit()
    
    # Fetch profile from ARC service
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ARC_SERVICE_URL}/api/v1/users/{user_id}/all_sections",
            timeout=30.0
        )
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="User profile not found")
        elif response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch profile")
        
        return response.json()

@router.post("/{user_id}/credits")
async def adjust_user_credits(
    user_id: UUID,
    adjustment: CreditAdjustment,
    request: Request,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Adjust user credits (add or deduct)"""
    from ..models import UserProfile, TopupCredits
    
    # Query user from database
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get topup credits
    topup = db.query(TopupCredits).filter(TopupCredits.user_id == user_id).first()
    if not topup:
        topup = TopupCredits(user_id=user_id, topup_credits_remaining=0)
        db.add(topup)
        db.flush()
    
    # Calculate balance before
    balance_before = user.monthly_credits_remaining + topup.topup_credits_remaining
    
    # Apply credit adjustment to topup credits
    topup.topup_credits_remaining += adjustment.amount
    
    # Don't allow negative credits
    if topup.topup_credits_remaining < 0:
        topup.topup_credits_remaining = 0
    
    # Set expiry for topup credits (90 days from now) if adding credits
    if adjustment.amount > 0:
        topup.topup_credits_expiry = datetime.now() + timedelta(days=90)
    
    # Calculate balance after
    balance_after = user.monthly_credits_remaining + topup.topup_credits_remaining
    
    # Update user timestamp
    user.updated_at = datetime.now()
    
    # Record transaction
    transaction = CreditTransaction(
        user_id=user_id,
        admin_id=admin.id,
        amount=adjustment.amount,
        reason=adjustment.reason,
        notes=adjustment.notes,
        balance_before=balance_before,
        balance_after=balance_after
    )
    db.add(transaction)
    
    # Log admin action
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="adjust_credits",
        resource_type="user",
        resource_id=str(user_id),
        details=f"Adjusted credits by {adjustment.amount} for user {user_id}. Reason: {adjustment.reason}",
        ip_address=request.client.host if request.client else None
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(transaction)
    db.refresh(user)
    db.refresh(topup)
    
    return {
        "success": True,
        "transaction": CreditTransactionOut.from_orm(transaction),
        "user": UserDetail(
            id=user.id,
            email=user.email,
            name=user.name or "",
            monthly_credits_remaining=user.monthly_credits_remaining,
            daily_credits_remaining=user.daily_credits_remaining,
            topup_credits=topup.topup_credits_remaining,
            topup_credits_expiry=topup.topup_credits_expiry,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
    }

@router.get("/{user_id}/credits/history", response_model=List[CreditTransactionOut])
def get_credit_history(
    user_id: UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get credit transaction history for a user"""
    # Log admin action
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="view_credit_history",
        resource_type="user",
        resource_id=str(user_id),
        details=f"Viewed credit history for user {user_id}"
    )
    db.add(audit_log)
    db.commit()
    
    # Fetch transactions
    transactions = db.query(CreditTransaction).filter(
        CreditTransaction.user_id == user_id
    ).order_by(CreditTransaction.created_at.desc()).limit(100).all()
    
    return [CreditTransactionOut.from_orm(t) for t in transactions]

@router.get("/{user_id}/activity")
async def get_user_activity(
    user_id: UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get user activity (CVs generated, applications submitted)"""
    # Log admin action
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="view_activity",
        resource_type="user",
        resource_id=str(user_id),
        details=f"Viewed activity for user {user_id}"
    )
    db.add(audit_log)
    db.commit()
    
    async with httpx.AsyncClient() as client:
        # Fetch CVs from CV service
        cv_response = await client.get(
            f"{CV_SERVICE_URL}/api/admin/users/{user_id}/cvs",
            timeout=30.0
        )
        cvs = cv_response.json() if cv_response.status_code == 200 else []
        
        # Fetch applications from CV service
        app_response = await client.get(
            f"{CV_SERVICE_URL}/api/admin/users/{user_id}/applications",
            timeout=30.0
        )
        applications = app_response.json() if app_response.status_code == 200 else []
    
    return {
        "user_id": str(user_id),
        "cvs_count": len(cvs),
        "cvs": cvs,
        "applications_count": len(applications),
        "applications": applications
    }

