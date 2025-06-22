from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey, DateTime, Table, LargeBinary
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
import os
from .database import Base

# Determine if using SQLite - moved before imports
is_sqlite = os.getenv("DATABASE_URL", "").startswith('sqlite:')

# Import PostgreSQL types only if needed
if not is_sqlite:
    from sqlalchemy.dialects.postgresql import JSONB, UUID
else:
    # Define placeholder for Type hints when using SQLite
    JSONB = None
    UUID = None

# Main CV table
class CV(Base):
    __tablename__ = "cvs"

    # Use different column types based on database
    if is_sqlite:
        # SQLite version (no UUID or JSONB support)
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        user_id = Column(String(36), nullable=False, index=True)
        # Store JSON as strings in SQLite
        style_options = Column(String, nullable=True)  
        personal_info = Column(String, nullable=True)
        custom_sections = Column(String, nullable=True)
        # Relationships will be handled differently
    else:
        # PostgreSQL version with proper types
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
        style_options = Column(JSONB, nullable=True)
        personal_info = Column(JSONB, nullable=True)
        custom_sections = Column(JSONB, nullable=True)
        # Define relationships for PostgreSQL
        experiences = relationship("Experience", back_populates="cv", cascade="all, delete-orphan")
        education = relationship("Education", back_populates="cv", cascade="all, delete-orphan")
        skills = relationship("Skill", back_populates="cv", cascade="all, delete-orphan")
        languages = relationship("Language", back_populates="cv", cascade="all, delete-orphan")
        projects = relationship("Project", back_populates="cv", cascade="all, delete-orphan")
        certifications = relationship("Certification", back_populates="cv", cascade="all, delete-orphan")
        references = relationship("Reference", back_populates="cv", cascade="all, delete-orphan")
        
    # Common columns
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False)
    version = Column(Integer, default=1)
    template_id = Column(String(50), nullable=False)
    summary = Column(Text, nullable=True)
    last_modified = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    docx_file = Column(LargeBinary, nullable=True)

# CV sections as separate tables for normalization and better querying
class Experience(Base):
    __tablename__ = "experiences"
    
    if is_sqlite:
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        cv_id = Column(String(36), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        cv_id = Column(UUID(as_uuid=True), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
        cv = relationship("CV", back_populates="experiences")
    
    company = Column(String(255), nullable=False)
    position = Column(String(255), nullable=False)
    start_date = Column(String(7), nullable=False)  # YYYY-MM format
    end_date = Column(String(7), nullable=True)  # YYYY-MM format or null for current
    description = Column(Text, nullable=True)
    included = Column(Boolean, default=True)
    order = Column(Integer, default=0)  # For custom ordering
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class Education(Base):
    __tablename__ = "education"
    
    if is_sqlite:
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        cv_id = Column(String(36), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        cv_id = Column(UUID(as_uuid=True), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
        cv = relationship("CV", back_populates="education")
    
    institution = Column(String(255), nullable=False)
    degree = Column(String(255), nullable=False)
    field_of_study = Column(String(255), nullable=False)
    start_date = Column(String(7), nullable=False)  # YYYY-MM format
    end_date = Column(String(7), nullable=True)  # YYYY-MM format or null for current
    description = Column(Text, nullable=True)
    included = Column(Boolean, default=True)
    order = Column(Integer, default=0)  # For custom ordering
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class Skill(Base):
    __tablename__ = "skills"
    
    if is_sqlite:
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        cv_id = Column(String(36), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        cv_id = Column(UUID(as_uuid=True), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
        cv = relationship("CV", back_populates="skills")
    
    name = Column(String(255), nullable=False)
    level = Column(Integer, nullable=True)  # 1-5 scale
    category = Column(String(100), nullable=True)
    years_of_experience = Column(Integer, nullable=True)
    included = Column(Boolean, default=True)
    order = Column(Integer, default=0)  # For custom ordering
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class Language(Base):
    __tablename__ = "languages"
    
    if is_sqlite:
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        cv_id = Column(String(36), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        cv_id = Column(UUID(as_uuid=True), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
        cv = relationship("CV", back_populates="languages")
    
    name = Column(String(255), nullable=False)
    proficiency = Column(String(50), nullable=False)  # Basic, Intermediate, Advanced, Fluent, Native
    included = Column(Boolean, default=True)
    order = Column(Integer, default=0)  # For custom ordering
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class Project(Base):
    __tablename__ = "projects"
    
    if is_sqlite:
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        cv_id = Column(String(36), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        cv_id = Column(UUID(as_uuid=True), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
        cv = relationship("CV", back_populates="projects")
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(255), nullable=True)
    start_date = Column(String(7), nullable=True)  # YYYY-MM format
    end_date = Column(String(7), nullable=True)  # YYYY-MM format
    included = Column(Boolean, default=True)
    order = Column(Integer, default=0)  # For custom ordering
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class Certification(Base):
    __tablename__ = "certifications"
    
    if is_sqlite:
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        cv_id = Column(String(36), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        cv_id = Column(UUID(as_uuid=True), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
        cv = relationship("CV", back_populates="certifications")
    
    name = Column(String(255), nullable=False)
    issuer = Column(String(255), nullable=False)
    date_issued = Column(String(7), nullable=False)  # YYYY-MM format
    date_expires = Column(String(7), nullable=True)  # YYYY-MM format
    credential_id = Column(String(255), nullable=True)
    url = Column(String(255), nullable=True)
    included = Column(Boolean, default=True)
    order = Column(Integer, default=0)  # For custom ordering
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

class Reference(Base):
    __tablename__ = "references"
    
    if is_sqlite:
        id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        cv_id = Column(String(36), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
    else:
        id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        cv_id = Column(UUID(as_uuid=True), ForeignKey("cvs.id", ondelete="CASCADE"), nullable=False)
        cv = relationship("CV", back_populates="references")
    
    name = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    position = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    included = Column(Boolean, default=True)
    order = Column(Integer, default=0)  # For custom ordering
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

# CV Templates
class Template(Base):
    __tablename__ = "templates"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    preview_image_url = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False)
    is_premium = Column(Boolean, default=False)
    
    if is_sqlite:
        style_options = Column(String, nullable=True)  # Store JSON as strings in SQLite
    else:
        style_options = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()) 