from pydantic import BaseModel
from uuid import UUID

class SkillCreate(BaseModel):
    skill: str

class SkillOut(BaseModel):
    id: UUID
    skill: str

    class Config:
        from_attributes = True
