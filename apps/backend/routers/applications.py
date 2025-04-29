from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import List
from uuid import uuid4
import jwt
import os
from datetime import datetime

router = APIRouter(prefix="/applications", tags=["Applications"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# In-memory store: {user_id: {application_id: application_dict}}
APPLICATIONS = {}

def get_user_id(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("user_id") or payload.get("id")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/", response_model=List[dict])
def list_applications(user_id: str = Depends(get_user_id)):
    return list(APPLICATIONS.get(user_id, {}).values())

@router.post("/", response_model=dict)
def create_application(data: dict, user_id: str = Depends(get_user_id)):
    application_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    application = {"id": application_id, **data, "date": now}
    APPLICATIONS.setdefault(user_id, {})[application_id] = application
    return application

@router.get("/{id}", response_model=dict)
def get_application(id: str, user_id: str = Depends(get_user_id)):
    application = APPLICATIONS.get(user_id, {}).get(id)
    if not application:
        raise HTTPException(status_code=404, detail="Not found")
    return application

@router.put("/{id}", response_model=dict)
def update_application(id: str, data: dict, user_id: str = Depends(get_user_id)):
    if id not in APPLICATIONS.get(user_id, {}):
        raise HTTPException(status_code=404, detail="Not found")
    APPLICATIONS[user_id][id].update(data)
    return APPLICATIONS[user_id][id]

@router.delete("/{id}")
def delete_application(id: str, user_id: str = Depends(get_user_id)):
    if id in APPLICATIONS.get(user_id, {}):
        del APPLICATIONS[user_id][id]
        return {"success": True}
    raise HTTPException(status_code=404, detail="Not found") 