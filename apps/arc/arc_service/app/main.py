from fastapi import FastAPI, APIRouter, UploadFile, File, Depends, HTTPException, status, Body, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import uuid4
from fastapi.responses import JSONResponse, FileResponse
import io
import os
import openai
import pdfplumber
from docx import Document
import logging
import re
from sqlalchemy.orm import Session
from .models import UserArcData
from .db import SessionLocal
import tiktoken
import jwt
from fastapi.middleware.cors import CORSMiddleware
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
import difflib
import json
import traceback
import spacy

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

# In-memory stores for demo
arc_data_store = {}
tasks = {}

class ArcData(BaseModel):
    work_experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None

class KeywordsRequest(BaseModel):
    jobDescription: str

class KeywordsResponse(BaseModel):
    keywords: List[str]

class CVUploadResponse(BaseModel):
    taskId: str

class CVStatusResponse(BaseModel):
    status: str
    extractedDataSummary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class GenerateRequest(BaseModel):
    jobAdvert: str
    arcData: Dict[str, Any]

class GenerateResponse(BaseModel):
    cv: str
    coverLetter: str

@router.post("/chunk-test")
async def chunk_test(request: Request):
    body = await request.json()
    text = body.get("text")
    return {"message": "chunk-test endpoint works!", "received_text": text}

@router.post("/ai/keywords", response_model=KeywordsResponse)
async def extract_keywords(req: KeywordsRequest, user_id: str = Depends(oauth2_scheme)):
    # Dummy implementation for demo
    return KeywordsResponse(keywords=["python", "fastapi", "openai"])

@router.get("/data", response_model=ArcData)
async def get_arc_data(user_id: str = Depends(oauth2_scheme)):
    return arc_data_store.get(user_id, ArcData())

@router.put("/data", response_model=ArcData)
@router.post("/data", response_model=ArcData)
async def update_arc_data(data: ArcData = Body(...), user_id: str = Depends(oauth2_scheme)):
    arc_data_store[user_id] = data
    return data

@router.post("/cv", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), user_id: str = Depends(oauth2_scheme)):
    task_id = str(uuid4())
    tasks[task_id] = {"status": "completed", "user_id": user_id, "extractedDataSummary": {"workExperienceCount": 0, "skillsFound": 0}}
    return {"taskId": task_id}

@router.get("/cv/status/{taskId}", response_model=CVStatusResponse)
async def poll_cv_status(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": task["status"],
        "extractedDataSummary": task.get("extractedDataSummary"),
        "error": task.get("error")
    }

@router.get("/cv/tasks")
async def list_cv_tasks(user_id: str = Depends(oauth2_scheme)):
    user_tasks = [ {"taskId": tid, **{k:v for k,v in t.items() if k != "user_id"}} for tid, t in tasks.items() if t["user_id"] == user_id ]
    return {"tasks": user_tasks}

@router.delete("/cv/{taskId}")
async def delete_cv_task(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    del tasks[taskId]
    return {"success": True}

@router.get("/cv/download/{taskId}")
async def download_processed_cv(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    dummy_content = f"Processed CV data for task {taskId}"
    return FileResponse(io.BytesIO(dummy_content.encode()), media_type="text/plain", filename=f"processed_cv_{taskId}.txt")

@router.post("/chunk")
async def test_parse_cv_with_ai_chunk_new(request: Request, user_id: str = Depends(oauth2_scheme)):
    body = await request.json()
    text = body.get("text")
    # Dummy chunk parse logic
    return {"chunked": True, "text": text}

@router.post("/generate", response_model=GenerateResponse)
async def generate_materials(req: GenerateRequest, user_id: str = Depends(oauth2_scheme)):
    # Dummy implementation for demo
    return GenerateResponse(cv="Generated CV for: " + req.jobAdvert, coverLetter="Generated Cover Letter for: " + req.jobAdvert)

# --- Batch 2: Advanced CV Task Debug Endpoints ---

@router.get("/cv/text/{taskId}")
async def get_raw_text(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"raw_text": task.get("raw_text", "No raw text available")}

@router.get("/cv/ai-raw/{taskId}")
async def get_ai_raw(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ai_raw": task.get("ai_raw_chunks", [])}

@router.get("/cv/ai-combined/{taskId}")
async def get_ai_combined(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ai_combined": task.get("ai_combined", {})}

@router.get("/cv/ai-filtered/{taskId}")
async def get_ai_filtered(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ai_filtered": task.get("ai_filtered", {})}

@router.get("/cv/arcdata/{taskId}")
async def get_arcdata(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"arcdata": task.get("arcdata", {})}

@router.get("/cv/logs/{taskId}")
async def get_logs(taskId: str, user_id: str = Depends(oauth2_scheme)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"logs": task.get("logs", "No logs available")}

# --- Batch 3: Admin/Sectioned Data and Patch Endpoints ---

@router.get("")
async def get_all_arc_data(user_id: str = Depends(oauth2_scheme)):
    # Dummy: return all arc data for the user
    return arc_data_store.get(user_id, ArcData())

@router.post("/work_experience")
async def add_work_experience(entry: dict = Body(...), user_id: str = Depends(oauth2_scheme)):
    # Dummy: append to work_experience
    data = arc_data_store.setdefault(user_id, ArcData())
    if data.work_experience is None:
        data.work_experience = []
    data.work_experience.append(entry)
    return data

@router.post("/education")
async def add_education(entry: dict = Body(...), user_id: str = Depends(oauth2_scheme)):
    data = arc_data_store.setdefault(user_id, ArcData())
    if data.education is None:
        data.education = []
    data.education.append(entry)
    return data

@router.post("/training")
async def add_training(entry: dict = Body(...), user_id: str = Depends(oauth2_scheme)):
    data = arc_data_store.setdefault(user_id, ArcData())
    if data.certifications is None:
        data.certifications = []
    data.certifications.append(entry)
    return data

@router.patch("/work_experience/{id}")
async def update_work_experience(id: str, update: dict = Body(...), user_id: str = Depends(oauth2_scheme)):
    data = arc_data_store.setdefault(user_id, ArcData())
    if data.work_experience:
        for entry in data.work_experience:
            if entry.get("id") == id:
                entry.update(update)
    return data

@router.patch("/education/{id}")
async def update_education(id: str, update: dict = Body(...), user_id: str = Depends(oauth2_scheme)):
    data = arc_data_store.setdefault(user_id, ArcData())
    if data.education:
        for entry in data.education:
            if entry.get("id") == id:
                entry.update(update)
    return data

@router.patch("/training/{id}")
async def update_training(id: str, update: dict = Body(...), user_id: str = Depends(oauth2_scheme)):
    data = arc_data_store.setdefault(user_id, ArcData())
    if data.certifications:
        for entry in data.certifications:
            if entry.get("id") == id:
                entry.update(update)
    return data

app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"} 