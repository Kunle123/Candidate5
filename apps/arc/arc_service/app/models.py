import uuid
from sqlalchemy import Column, String, DateTime, JSON, Enum, ForeignKey
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