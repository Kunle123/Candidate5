from fastapi import FastAPI, APIRouter, UploadFile, File, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from uuid import uuid4
from fastapi.responses import FileResponse
import io
import os
import openai
import pdfplumber
from docx import Document
import logging
import jwt
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Career Ark (Arc) Service", description="API for Career Ark data extraction, deduplication, and application material generation.")
router = APIRouter(prefix="/api/arc")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

logger = logging.getLogger("arc_service")
logging.basicConfig(level=logging.INFO)

JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175,https://c5-frontend-pied.vercel.app").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

tasks = {}

# --- Helper: Auth ---
def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id") or payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: no user_id")
        return user_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# --- Endpoint: Upload CV ---
class CVUploadResponse(BaseModel):
    taskId: str

@router.post("/cv", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    task_id = str(uuid4())
    tasks[task_id] = {"status": "pending", "user_id": user_id}
    # Minimal logic for demo; real logic can be restored as needed
    tasks[task_id]["status"] = "completed"
    tasks[task_id]["extractedDataSummary"] = {"workExperienceCount": 0, "skillsFound": 0}
    return {"taskId": task_id}

# --- Endpoint: Chunk ---
@router.post("/chunk")
async def test_parse_cv_with_ai_chunk_new(request: Request, user_id: str = Depends(get_current_user)):
    body = await request.json()
    text = body.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Missing 'text' in request body.")
    # Minimal logic for demo; real logic can be restored as needed
    return {"parsed": {"text": text}, "raw": text}

app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"} 