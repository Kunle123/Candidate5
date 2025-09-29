from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class TrainingCreate(BaseModel):
    name: str
    institution: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    order_index: Optional[int] = None

class TrainingUpdate(BaseModel):
    name: Optional[str]
    institution: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]

class TrainingOut(BaseModel):
    id: UUID
    name: str
    institution: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]
    order_index: int

    class Config:
        from_attributes = True
