from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import httpx
import os
from ..database import get_db
from ..models import Admin, AdminAuditLog, CreditTransaction
from ..schemas import AnalyticsSummary
from ..auth import get_current_admin

router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])

# External service URLs
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
CV_SERVICE_URL = os.getenv("CV_SERVICE_URL")

@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get analytics summary dashboard"""
    # Log admin action
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="view_analytics",
        resource_type="analytics",
        details="Viewed analytics summary"
    )
    db.add(audit_log)
    db.commit()
    
    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    
    async with httpx.AsyncClient() as client:
        # Fetch user statistics
        user_stats_response = await client.get(
            f"{USER_SERVICE_URL}/api/admin/stats",
            timeout=30.0
        )
        user_stats = user_stats_response.json() if user_stats_response.status_code == 200 else {}
        
        # Fetch CV statistics
        cv_stats_response = await client.get(
            f"{CV_SERVICE_URL}/api/admin/stats",
            timeout=30.0
        )
        cv_stats = cv_stats_response.json() if cv_stats_response.status_code == 200 else {}
    
    # Get credit statistics from admin database
    total_credits_adjusted = db.query(CreditTransaction).count()
    total_credits_added = db.query(CreditTransaction).filter(
        CreditTransaction.amount > 0
    ).count()
    
    return AnalyticsSummary(
        total_users=user_stats.get("total_users", 0),
        active_users_7d=user_stats.get("active_users_7d", 0),
        active_users_30d=user_stats.get("active_users_30d", 0),
        new_signups_7d=user_stats.get("new_signups_7d", 0),
        new_signups_30d=user_stats.get("new_signups_30d", 0),
        total_cvs_generated=cv_stats.get("total_cvs", 0),
        cvs_generated_7d=cv_stats.get("cvs_7d", 0),
        cvs_generated_30d=cv_stats.get("cvs_30d", 0),
        total_applications=cv_stats.get("total_applications", 0),
        applications_7d=cv_stats.get("applications_7d", 0),
        applications_30d=cv_stats.get("applications_30d", 0),
        total_credits_purchased=total_credits_added,
        total_credits_consumed=cv_stats.get("credits_consumed", 0)
    )

