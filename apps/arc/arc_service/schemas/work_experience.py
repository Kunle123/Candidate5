from pydantic import BaseModel
from typing import Optional, List, Union
from uuid import UUID

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
