from sqlalchemy import Column, String, DateTime
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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow) 