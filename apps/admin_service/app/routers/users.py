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
    # Log admin action
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="list_users",
        resource_type="user",
        details=f"Listed users (skip={skip}, limit={limit}, search={search})"
    )
    db.add(audit_log)
    db.commit()
    
    # Fetch users from user service
    async with httpx.AsyncClient() as client:
        params = {"skip": skip, "limit": limit}
        if search:
            params["search"] = search
        
        response = await client.get(
            f"{USER_SERVICE_URL}/api/admin/users",
            params=params,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch users")
        
        return response.json()

@router.get("/{user_id}", response_model=UserDetail)
async def get_user_detail(
    user_id: UUID,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific user"""
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
    
    # Fetch user from user service
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{USER_SERVICE_URL}/api/admin/users/{user_id}",
            timeout=30.0
        )
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found")
        elif response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch user")
        
        return response.json()

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
    # Fetch current user data to get balance before
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{USER_SERVICE_URL}/api/admin/users/{user_id}",
            timeout=30.0
        )
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found")
        elif response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch user")
        
        user_data = response.json()
        balance_before = user_data.get("monthly_credits_remaining", 0) + user_data.get("topup_credits", 0)
    
    # Apply credit adjustment via user service
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{USER_SERVICE_URL}/api/admin/users/{user_id}/credits",
            json={"amount": adjustment.amount},
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to adjust credits")
        
        updated_user = response.json()
        balance_after = updated_user.get("monthly_credits_remaining", 0) + updated_user.get("topup_credits", 0)
    
    # Record transaction in admin database
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
    
    return {
        "success": True,
        "transaction": CreditTransactionOut.from_orm(transaction),
        "user": updated_user
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

