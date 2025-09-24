from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
import datetime
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    name = Column(String)
    address_line1 = Column(String, nullable=True)
    city_state_postal = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    # --- Credit and Subscription Fields ---
    monthly_credits_remaining = Column(Integer, nullable=False, default=3)  # Always a constant
    daily_credits_remaining = Column(Integer, nullable=False, default=0)    # Always a constant
    last_daily_reset = Column(DateTime, nullable=True)
    last_monthly_reset = Column(DateTime, nullable=True)
    subscription_type = Column(String, nullable=False, default='free')  # Always a constant
    next_credit_reset = Column(DateTime, nullable=True)  # New: per-user rolling reset
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow) 

class TopupCredits(Base):
    __tablename__ = 'topup_credits'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    topup_credits_remaining = Column(Integer, nullable=False, default=0)
    topup_credits_expiry = Column(DateTime, nullable=True)
