from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models import Admin, AdminAuditLog
from ..schemas import AdminLogin, AdminCreate, AdminOut, AdminToken
from ..auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_admin,
    require_super_admin
)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])

@router.post("/login", response_model=AdminToken)
def admin_login(credentials: AdminLogin, request: Request, db: Session = Depends(get_db)):
    """Admin login endpoint"""
    # Find admin by email
    admin = db.query(Admin).filter(Admin.email == credentials.email).first()
    
    if not admin or not verify_password(credentials.password, admin.password_hash):
        # Log failed login attempt
        audit_log = AdminAuditLog(
            admin_id=admin.id if admin else None,
            action="login_failed",
            resource_type="admin",
            details=f"Failed login attempt for {credentials.email}",
            ip_address=request.client.host if request.client else None
        )
        db.add(audit_log)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is inactive"
        )
    
    # Update last login
    admin.last_login = datetime.utcnow()
    db.commit()
    
    # Create access token
    access_token = create_access_token(data={"admin_id": str(admin.id), "email": admin.email, "role": admin.role})
    
    # Log successful login
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="login_success",
        resource_type="admin",
        details=f"Successful login for {admin.email}",
        ip_address=request.client.host if request.client else None
    )
    db.add(audit_log)
    db.commit()
    
    return AdminToken(
        access_token=access_token,
        admin=AdminOut.from_orm(admin)
    )

@router.post("/create", response_model=AdminOut)
def create_admin(
    admin_data: AdminCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin)
):
    """Create a new admin (super admin only)"""
    # Check if email already exists
    existing = db.query(Admin).filter(Admin.email == admin_data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin with this email already exists"
        )
    
    # Create new admin
    new_admin = Admin(
        email=admin_data.email,
        name=admin_data.name,
        password_hash=get_password_hash(admin_data.password),
        role=admin_data.role
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    # Log admin creation
    audit_log = AdminAuditLog(
        admin_id=current_admin.id,
        action="create_admin",
        resource_type="admin",
        resource_id=str(new_admin.id),
        details=f"Created new admin: {new_admin.email} with role: {new_admin.role}"
    )
    db.add(audit_log)
    db.commit()
    
    return AdminOut.from_orm(new_admin)

@router.get("/me", response_model=AdminOut)
def get_current_admin_info(admin: Admin = Depends(get_current_admin)):
    """Get current admin info"""
    return AdminOut.from_orm(admin)

@router.post("/logout")
def admin_logout(admin: Admin = Depends(get_current_admin), db: Session = Depends(get_db)):
    """Admin logout (client should delete token, this just logs the action)"""
    audit_log = AdminAuditLog(
        admin_id=admin.id,
        action="logout",
        resource_type="admin",
        details=f"Admin {admin.email} logged out"
    )
    db.add(audit_log)
    db.commit()
    
    return {"message": "Logged out successfully"}

