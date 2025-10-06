from sqlalchemy import Column, String, DateTime, Integer, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

class Admin(Base):
    """Admin user model"""
    __tablename__ = 'admins'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)  # bcrypt hashed password
    role = Column(String, nullable=False, default='admin')  # 'super_admin', 'admin', 'support'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
class CreditTransaction(Base):
    """Credit adjustment history for audit trail"""
    __tablename__ = 'credit_transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    admin_id = Column(UUID(as_uuid=True), nullable=False)  # Admin who made the change
    amount = Column(Integer, nullable=False)  # Positive for add, negative for deduct
    reason = Column(String, nullable=False)  # 'Refund', 'Promo', 'Support', 'Correction', etc.
    notes = Column(Text, nullable=True)  # Optional admin notes
    balance_before = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
class AdminAuditLog(Base):
    """Audit log for all admin actions"""
    __tablename__ = 'admin_audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    action = Column(String, nullable=False)  # 'view_user', 'adjust_credits', 'delete_cv', etc.
    resource_type = Column(String, nullable=False)  # 'user', 'cv', 'application', etc.
    resource_id = Column(String, nullable=True)  # ID of the affected resource
    details = Column(Text, nullable=True)  # JSON string with additional details
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

