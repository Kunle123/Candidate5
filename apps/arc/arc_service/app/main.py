from fastapi import FastAPI, APIRouter, Request, Body, Depends, HTTPException, UploadFile, File
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import uuid4

app = FastAPI(title="Minimal Arc Service Debug")
router = APIRouter(prefix="/api/arc")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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

app.include_router(router)

@app.get("/health")
async def health():
    return {"status": "ok"} 