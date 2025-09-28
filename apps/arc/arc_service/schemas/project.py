from pydantic import BaseModel
from typing import Optional
from uuid import UUID

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
