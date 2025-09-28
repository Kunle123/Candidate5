from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeclarativeMeta
from uuid import UUID
from db.models import WorkExperience, Education

ModelType = TypeVar("ModelType", bound=DeclarativeMeta)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db
    
    def get(self, id: UUID) -> Optional[ModelType]:
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_by_user_id(self, user_id: str) -> List[ModelType]:
        return self.db.query(self.model).filter(self.model.user_id == user_id).all()
    
    def create(self, obj_in: dict) -> ModelType:
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(self, db_obj: ModelType, obj_in: dict) -> ModelType:
        for field, value in obj_in.items():
            setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: UUID) -> bool:
        obj = self.get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False

class WorkExperienceRepository(BaseRepository):
    def get_ordered_by_user(self, user_id: str):
        # Convert to UUID if it's a string
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except Exception:
                pass  # fallback, let SQLAlchemy handle if not a valid UUID
        return self.db.query(self.model).filter(
            self.model.user_id == user_id
        ).order_by(self.model.order_index).all()
    
    def reorder(self, id: UUID, new_order_index: int):
        entry = self.get(id)
        if not entry:
            return None
        
        old_index = entry.order_index
        user_id = entry.user_id
        
        if new_order_index > old_index:
            affected = self.db.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.order_index > old_index,
                self.model.order_index <= new_order_index
            ).all()
            for e in affected:
                e.order_index -= 1
        else:
            affected = self.db.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.order_index < old_index,
                self.model.order_index >= new_order_index
            ).all()
            for e in affected:
                e.order_index += 1
        
        entry.order_index = new_order_index
        self.db.commit()
        self.db.refresh(entry)
        return entry

class EducationRepository(BaseRepository):
    def get_ordered_by_user(self, user_id: str):
        # Convert to UUID if it's a string
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except Exception:
                pass  # fallback, let SQLAlchemy handle if not a valid UUID
        return self.db.query(self.model).filter(
            self.model.user_id == user_id
        ).order_by(self.model.order_index).all()

    def reorder(self, id: UUID, new_order_index: int):
        entry = self.get(id)
        if not entry:
            return None
        old_index = entry.order_index
        user_id = entry.user_id
        if new_order_index > old_index:
            affected = self.db.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.order_index > old_index,
                self.model.order_index <= new_order_index
            ).all()
            for e in affected:
                e.order_index -= 1
        else:
            affected = self.db.query(self.model).filter(
                self.model.user_id == user_id,
                self.model.order_index < old_index,
                self.model.order_index >= new_order_index
            ).all()
            for e in affected:
                e.order_index += 1
        entry.order_index = new_order_index
        self.db.commit()
        self.db.refresh(entry)
        return entry
