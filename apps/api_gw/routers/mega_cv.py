from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import List
from uuid import uuid4
import jwt
import os
from datetime import datetime

router = APIRouter(prefix="/mega-cv", tags=["Mega CV"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# In-memory store: {user_id: {mega_cv_id: mega_cv_dict}}
MEGA_CVS = {}
PREVIOUS_CVS = {}

def get_user_id(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("user_id") or payload.get("id")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/previous-cvs", response_model=List[dict])
def list_previous_cvs(user_id: str = Depends(get_user_id)):
    return list(PREVIOUS_CVS.get(user_id, {}).values())

@router.post("/", response_model=dict)
def create_mega_cv(data: dict, user_id: str = Depends(get_user_id)):
    mega_cv_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    mega_cv = {"id": mega_cv_id, **data, "created": now}
    MEGA_CVS.setdefault(user_id, {})[mega_cv_id] = mega_cv
    return mega_cv

@router.get("/{id}", response_model=dict)
def get_mega_cv(id: str, user_id: str = Depends(get_user_id)):
    mega_cv = MEGA_CVS.get(user_id, {}).get(id)
    if not mega_cv:
        raise HTTPException(status_code=404, detail="Not found")
    return mega_cv

@router.delete("/{id}")
def delete_mega_cv(id: str, user_id: str = Depends(get_user_id)):
    if id in MEGA_CVS.get(user_id, {}):
        del MEGA_CVS[user_id][id]
        return {"success": True}
    raise HTTPException(status_code=404, detail="Not found") 