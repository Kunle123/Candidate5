from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import List
from uuid import uuid4
import jwt
import os
from datetime import datetime

router = APIRouter(prefix="/cover-letters", tags=["Cover Letters"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# In-memory store: {user_id: {cover_letter_id: cover_letter_dict}}
COVER_LETTERS = {}

def get_user_id(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("user_id") or payload.get("id")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/", response_model=List[dict])
def list_cover_letters(user_id: str = Depends(get_user_id)):
    return list(COVER_LETTERS.get(user_id, {}).values())

@router.post("/", response_model=dict)
def create_cover_letter(data: dict, user_id: str = Depends(get_user_id)):
    cover_letter_id = str(uuid4())
    now = datetime.utcnow().isoformat()
    cover_letter = {"id": cover_letter_id, **data, "created": now, "status": "draft"}
    COVER_LETTERS.setdefault(user_id, {})[cover_letter_id] = cover_letter
    return cover_letter

@router.get("/{id}", response_model=dict)
def get_cover_letter(id: str, user_id: str = Depends(get_user_id)):
    cover_letter = COVER_LETTERS.get(user_id, {}).get(id)
    if not cover_letter:
        raise HTTPException(status_code=404, detail="Not found")
    return cover_letter

@router.put("/{id}", response_model=dict)
def update_cover_letter(id: str, data: dict, user_id: str = Depends(get_user_id)):
    if id not in COVER_LETTERS.get(user_id, {}):
        raise HTTPException(status_code=404, detail="Not found")
    COVER_LETTERS[user_id][id].update(data)
    return COVER_LETTERS[user_id][id]

@router.delete("/{id}")
def delete_cover_letter(id: str, user_id: str = Depends(get_user_id)):
    if id in COVER_LETTERS.get(user_id, {}):
        del COVER_LETTERS[user_id][id]
        return {"success": True}
    raise HTTPException(status_code=404, detail="Not found") 