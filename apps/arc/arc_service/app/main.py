from fastapi import FastAPI, APIRouter, UploadFile, File, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import uuid4
from fastapi.responses import JSONResponse, FileResponse
import io

app = FastAPI(title="Career Ark (Arc) Service", description="API for Career Ark data extraction, deduplication, and application material generation.")
router = APIRouter(prefix="/api/arc")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# --- Models ---
class CVUploadResponse(BaseModel):
    taskId: str

class CVStatusResponse(BaseModel):
    status: str
    extractedDataSummary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ArcData(BaseModel):
    work_experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[Dict[str, Any]]] = None
    # Add more fields as needed

class GenerateRequest(BaseModel):
    jobAdvert: str
    arcData: Dict[str, Any]

class GenerateResponse(BaseModel):
    cv: str
    coverLetter: str

# --- In-memory stores for demo purposes ---
tasks = {}
user_arc_data = {}

# --- Deduplication & Merging Logic Stubs ---
def deduplicate_and_merge_work_experience(existing: list, new: list) -> list:
    """
    Deduplicate and merge work experience entries.
    Rules: Same company + similar role title + overlapping dates.
    TODO: Implement fuzzy/semantic matching and merging logic.
    """
    # Placeholder: naive append
    return (existing or []) + (new or [])

def deduplicate_and_merge_education(existing: list, new: list) -> list:
    """
    Deduplicate and merge education entries.
    Rules: Same institution + same degree + same field + overlapping dates.
    TODO: Implement fuzzy/semantic matching and merging logic.
    """
    return (existing or []) + (new or [])

def deduplicate_and_merge_skills(existing: list, new: list) -> list:
    """
    Deduplicate and merge skills by name/category.
    TODO: Implement case-insensitive and semantic deduplication.
    """
    return list(set((existing or []) + (new or [])))

def deduplicate_and_merge_projects(existing: list, new: list) -> list:
    """
    Deduplicate and merge projects by name/description/tech.
    TODO: Implement fuzzy/semantic matching and merging logic.
    """
    return (existing or []) + (new or [])

def deduplicate_and_merge_certifications(existing: list, new: list) -> list:
    """
    Deduplicate and merge certifications by credential ID or name/org.
    TODO: Implement matching and merging logic.
    """
    return (existing or []) + (new or [])

def deduplicate_and_merge_achievements(existing: list, new: list) -> list:
    """
    Deduplicate and merge achievements by semantic similarity within parent entity.
    TODO: Implement semantic deduplication.
    """
    return (existing or []) + (new or [])

# --- Helper: Merge ArcData ---
def merge_arc_data(existing: ArcData, new: ArcData) -> ArcData:
    return ArcData(
        work_experience=deduplicate_and_merge_work_experience(existing.work_experience, new.work_experience),
        education=deduplicate_and_merge_education(existing.education, new.education),
        skills=deduplicate_and_merge_skills(existing.skills, new.skills),
        projects=deduplicate_and_merge_projects(existing.projects, new.projects),
        certifications=deduplicate_and_merge_certifications(existing.certifications, new.certifications),
        # Add more fields as needed
    )

# --- Helper: Auth ---
def get_current_user(token: str = Depends(oauth2_scheme)):
    # Placeholder for real JWT validation
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # In real implementation, decode token and get user_id
    return "demo_user_id"

# --- Endpoint: Upload CV ---
@router.post("/cv", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    task_id = str(uuid4())
    tasks[task_id] = {"status": "pending", "user_id": user_id}
    # TODO: Extract structured ArcData from CV file
    # For now, simulate new ArcData
    new_arc_data = ArcData(
        work_experience=[{"company": "Acme Corp", "role": "Engineer", "dates": "2020-2022"}],
        skills=["Python", "Project Management"]
    )
    # Deduplicate and merge with existing data
    existing = user_arc_data.get(user_id, ArcData())
    merged = merge_arc_data(existing, new_arc_data)
    user_arc_data[user_id] = merged
    tasks[task_id] = {
        "status": "completed",
        "user_id": user_id,
        "extractedDataSummary": {"workExperienceCount": len(merged.work_experience or []), "skillsFound": len(merged.skills or [])}
    }
    return {"taskId": task_id}

# --- Endpoint: Poll CV Processing Status ---
@router.get("/cv/status/{taskId}", response_model=CVStatusResponse)
async def poll_cv_status(taskId: str, user_id: str = Depends(get_current_user)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": task["status"],
        "extractedDataSummary": task.get("extractedDataSummary"),
        "error": task.get("error")
    }

# --- Endpoint: Arc Data Management ---
@router.get("/data", response_model=ArcData)
async def get_arc_data(user_id: str = Depends(get_current_user)):
    return user_arc_data.get(user_id, ArcData())

@router.put("/data", response_model=ArcData)
@router.post("/data", response_model=ArcData)
async def update_arc_data(data: ArcData = Body(...), user_id: str = Depends(get_current_user)):
    # Deduplicate and merge with existing data
    existing = user_arc_data.get(user_id, ArcData())
    merged = merge_arc_data(existing, data)
    user_arc_data[user_id] = merged
    return merged

# --- Endpoint: Generate Application Materials ---
@router.post("/generate", response_model=GenerateResponse)
async def generate_materials(req: GenerateRequest, user_id: str = Depends(get_current_user)):
    # TODO: Implement generation logic
    return GenerateResponse(cv="Generated CV text or link", coverLetter="Generated cover letter text")

# --- Endpoint: Download Processed CV or Extracted Data ---
@router.get("/cv/download/{taskId}")
async def download_processed_cv(taskId: str, user_id: str = Depends(get_current_user)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    # TODO: Return actual processed file or data
    # For now, return a dummy text file
    dummy_content = f"Processed CV data for task {taskId}"
    return FileResponse(io.BytesIO(dummy_content.encode()), media_type="text/plain", filename=f"processed_cv_{taskId}.txt")

# --- Endpoint: List User's Uploaded CVs/Tasks ---
@router.get("/cv/tasks")
async def list_cv_tasks(user_id: str = Depends(get_current_user)):
    user_tasks = [ {"taskId": tid, **{k:v for k,v in t.items() if k != "user_id"}} for tid, t in tasks.items() if t["user_id"] == user_id ]
    return {"tasks": user_tasks}

# --- Endpoint: Delete a CV or Task ---
@router.delete("/cv/{taskId}")
async def delete_cv_task(taskId: str, user_id: str = Depends(get_current_user)):
    task = tasks.get(taskId)
    if not task or task["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    del tasks[taskId]
    # TODO: Remove associated data from user_arc_data if needed
    return {"success": True}

# --- Health Check Endpoint ---
@router.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/health")
async def root_health():
    return {"status": "ok"}

# --- Error handler example ---
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

app.include_router(router) 