import uuid
from sqlalchemy import Column, String, DateTime, JSON, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from .db import Base
import enum

class TaskStatusEnum(str, enum.Enum):
    pending = "pending"
    metadata_extracted = "metadata_extracted"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    failed = "failed"

class UserArcData(Base):
    __tablename__ = "user_arc_data"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True, nullable=False, index=True)
    arc_data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CVTask(Base):
    __tablename__ = "cv_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_arc_data.user_id"), nullable=False, index=True)
    status = Column(Enum(TaskStatusEnum), nullable=False, default=TaskStatusEnum.pending)
    extracted_data_summary = Column(JSON, nullable=True)
    error = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# CVProfile model is now deprecated and will be removed
# class CVProfile(Base):
#     __tablename__ = "cv_profiles"
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     user_id = Column(String, nullable=False, index=True)
#     name = Column(String, nullable=False)
#     email = Column(String, nullable=True)
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class WorkExperience(Base):
    __tablename__ = "work_experience"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_arc_data.user_id"), nullable=False, index=True)
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    start_date = Column(String, nullable=False)
    end_date = Column(String, nullable=False)
    description = Column(JSONB, nullable=True)  # Now stores array of strings
    skills = Column(JSONB, nullable=True)       # New: array of strings per role
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Education(Base):
    __tablename__ = "education"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_arc_data.user_id"), nullable=False, index=True)
    institution = Column(String, nullable=False)
    degree = Column(String, nullable=False)
    field = Column(String, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    description = Column(JSONB, nullable=True)  # Now stores array of strings
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Skill(Base):
    __tablename__ = "skills"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_arc_data.user_id"), nullable=False, index=True)
    skill = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_arc_data.user_id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(JSONB, nullable=True)  # Now stores array of strings
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Certification(Base):
    __tablename__ = "certifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_arc_data.user_id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    issuer = Column(String, nullable=True)
    year = Column(String, nullable=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Training(Base):
    __tablename__ = "training"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_arc_data.user_id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    institution = Column(String, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class AIExtractionLog(Base):
    __tablename__ = "ai_extraction_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("cv_tasks.id"), nullable=False)
    entry_type = Column(String, nullable=False)  # e.g., 'work_experience', 'education', etc.
    entry_id = Column(UUID(as_uuid=True), nullable=True)  # FK to normalized table row, nullable until detail is written
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="pending")  # 'success', 'error', 'pending'
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 