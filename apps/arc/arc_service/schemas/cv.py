from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID

class CVCreate(BaseModel):
    user_id: UUID
    name: Optional[str] = None
    contact: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    relevant_achievements: Optional[List[Dict[str, Any]]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    core_competencies: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    cover_letter: Optional[Dict[str, Any]] = None

class CVUpdate(BaseModel):
    name: Optional[str]
    contact: Optional[str]
    summary: Optional[Dict[str, Any]]
    relevant_achievements: Optional[List[Dict[str, Any]]]
    experience: Optional[List[Dict[str, Any]]]
    core_competencies: Optional[List[Dict[str, Any]]]
    education: Optional[List[Dict[str, Any]]]
    cover_letter: Optional[Dict[str, Any]]

class CVOut(BaseModel):
    id: UUID
    user_id: UUID
    name: Optional[str]
    contact: Optional[str]
    summary: Optional[Dict[str, Any]]
    relevant_achievements: Optional[List[Dict[str, Any]]]
    experience: Optional[List[Dict[str, Any]]]
    core_competencies: Optional[List[Dict[str, Any]]]
    education: Optional[List[Dict[str, Any]]]
    cover_letter: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True
