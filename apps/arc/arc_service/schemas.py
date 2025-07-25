from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union
from uuid import UUID

# --- Profile Schemas ---
class ProfileCreate(BaseModel):
    user_id: str
    name: str
    email: Optional[str] = None

class ProfileUpdate(BaseModel):
    name: Optional[str]
    email: Optional[str]

class ProfileOut(BaseModel):
    id: UUID
    user_id: str
    name: str
    email: Optional[str]
    class Config:
        from_attributes = True

# --- Work Experience Schemas ---
class WorkExperienceCreate(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str
    description: Optional[Union[str, List[str]]] = None
    order_index: Optional[int] = None

class WorkExperienceUpdate(BaseModel):
    company: Optional[str]
    title: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[Union[str, List[str]]]

class WorkExperienceOut(BaseModel):
    id: UUID
    company: str
    title: str
    start_date: str
    end_date: str
    description: Optional[Union[str, List[str]]]
    order_index: int
    class Config:
        from_attributes = True

# --- Education Schemas ---
class EducationCreate(BaseModel):
    institution: str
    degree: str
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None

class EducationUpdate(BaseModel):
    institution: Optional[str]
    degree: Optional[str]
    field: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]

class EducationOut(BaseModel):
    id: UUID
    institution: str
    degree: str
    field: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]
    order_index: int
    class Config:
        from_attributes = True

# --- Skill Schemas ---
class SkillCreate(BaseModel):
    skill: str

class SkillOut(BaseModel):
    id: UUID
    skill: str
    class Config:
        from_attributes = True

# --- Project Schemas ---
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    order_index: Optional[int] = None

class ProjectUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str]

class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    order_index: int
    class Config:
        from_attributes = True

# --- Certification Schemas ---
class CertificationCreate(BaseModel):
    name: str
    issuer: Optional[str] = None
    year: Optional[str] = None
    order_index: Optional[int] = None

class CertificationUpdate(BaseModel):
    name: Optional[str]
    issuer: Optional[str]
    year: Optional[str]

class CertificationOut(BaseModel):
    id: UUID
    name: str
    issuer: Optional[str]
    year: Optional[str]
    order_index: int
    class Config:
        from_attributes = True

# --- Training Schemas ---
class TrainingCreate(BaseModel):
    name: str
    institution: str
    start_date: str
    end_date: str
    description: Optional[str] = None
    order_index: Optional[int] = None

class TrainingUpdate(BaseModel):
    name: Optional[str]
    institution: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]

# --- ArcData and Role Schemas (from arc_schemas.py) ---
class Role(BaseModel):
    company: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    successes: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    training: Optional[List[str]] = None

class ArcData(BaseModel):
    work_experience: Optional[List[Role]] = None
    education: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None 