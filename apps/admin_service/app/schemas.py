from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# Admin schemas
class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class AdminCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "admin"  # 'super_admin', 'admin', 'support'

class AdminOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True

class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminOut

# User management schemas
class UserListItem(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    monthly_credits_remaining: int
    topup_credits: int
    subscription_type: str
    created_at: datetime
    last_monthly_reset: Optional[datetime]
    
class UserDetail(BaseModel):
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
    
# Credit transaction schemas
class CreditAdjustment(BaseModel):
    user_id: UUID
    amount: int  # Positive to add, negative to deduct
    reason: str  # 'Refund', 'Promo', 'Support', 'Correction', 'Violation'
    notes: Optional[str] = None

class CreditTransactionOut(BaseModel):
    id: int
    user_id: UUID
    admin_id: UUID
    amount: int
    reason: str
    notes: Optional[str]
    balance_before: int
    balance_after: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Analytics schemas
class AnalyticsSummary(BaseModel):
    total_users: int
    active_users_7d: int
    active_users_30d: int
    new_signups_7d: int
    new_signups_30d: int
    total_cvs_generated: int
    cvs_generated_7d: int
    cvs_generated_30d: int
    total_applications: int
    applications_7d: int
    applications_30d: int
    total_credits_purchased: int
    total_credits_consumed: int
    
# Audit log schemas
class AuditLogEntry(BaseModel):
    id: int
    admin_id: UUID
    admin_email: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    created_at: datetime

