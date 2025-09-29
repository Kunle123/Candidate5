from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class ProfileCreate(BaseModel):
    user_id: UUID
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    linkedin: Optional[str] = None
    summary: Optional[str] = None

class ProfileUpdate(BaseModel):
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    linkedin: Optional[str]
    summary: Optional[str]

class ProfileOut(BaseModel):
    user_id: UUID
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    linkedin: Optional[str]
    summary: Optional[str]

    class Config:
        from_attributes = True
