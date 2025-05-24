import uuid
from sqlalchemy import Column, String, DateTime, JSON, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from .db import Base
import enum

class TaskStatusEnum(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"

class UserArcData(Base):
    __tablename__ = "user_arc_data"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, unique=True, nullable=False, index=True)
    arc_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CVTask(Base):
    __tablename__ = "cv_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, ForeignKey("user_arc_data.user_id"), nullable=False, index=True)
    status = Column(Enum(TaskStatusEnum), nullable=False, default=TaskStatusEnum.pending)
    extracted_data_summary = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CVProfile(Base):
    __tablename__ = "cv_profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class WorkExperience(Base):
    __tablename__ = "work_experience"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_profile_id = Column(UUID(as_uuid=True), ForeignKey("cv_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Education(Base):
    __tablename__ = "education"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_profile_id = Column(UUID(as_uuid=True), ForeignKey("cv_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    institution = Column(String, nullable=False)
    degree = Column(String, nullable=False)
    field = Column(String, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Skill(Base):
    __tablename__ = "skills"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_profile_id = Column(UUID(as_uuid=True), ForeignKey("cv_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    skill = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_profile_id = Column(UUID(as_uuid=True), ForeignKey("cv_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Certification(Base):
    __tablename__ = "certifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_profile_id = Column(UUID(as_uuid=True), ForeignKey("cv_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    issuer = Column(String, nullable=True)
    year = Column(String, nullable=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 