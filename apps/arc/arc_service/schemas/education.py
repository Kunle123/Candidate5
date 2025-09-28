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
