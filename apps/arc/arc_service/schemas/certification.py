from pydantic import BaseModel
from typing import Optional
from uuid import UUID

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
