import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from datetime import datetime
import jwt

from app.export_manager import ExportManager

# Set up logging
logger = logging.getLogger("export_service.routes")

# Environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")

# Create router
router = APIRouter()

# Pydantic models
class ExportRequest(BaseModel):
    cv_id: str
    format: str = "pdf"
    template_options: Optional[Dict[str, Any]] = None

class ExportResponse(BaseModel):
    id: str
    status: str
    cv_id: str
    format: str
    download_url: Optional[str] = None
    created_at: datetime

class ExportStatusResponse(BaseModel):
    id: str
    status: str
    cv_id: str
    format: str
    download_url: Optional[str] = None
    progress: Optional[float] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

class ExportListResponse(BaseModel):
    exports: List[ExportStatusResponse]
    count: int

# Helper function to verify JWT token
async def verify_token(authorization: str = None):
    """
    Verify the JWT token and extract user ID
    
    Args:
        authorization: The Authorization header value
        
    Returns:
        The user ID from the token
        
    Raises:
        HTTPException: If the token is invalid or missing
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Split the Authorization header
        scheme, token = authorization.split()
        
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Decode and verify the token
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Extract user ID
        user_id = payload.get("sub") or payload.get("user_id")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {"user_id": user_id, "token": token}
    
    except (jwt.PyJWTError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Routes
@router.post("/api/export", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_export(
    export_req: ExportRequest,
    background_tasks: BackgroundTasks,
    auth = Depends(verify_token)
):
    """
    Create a new export job
    
    This will start a background task to generate the export file.
    """
    user_id = auth["user_id"]
    token = auth["token"]
    
    # Validate format
    if export_req.format.lower() not in ["pdf", "docx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Supported formats: pdf, docx"
        )
    
    # Create export job
    job = await ExportManager.create_export_job(
        cv_id=export_req.cv_id,
        format=export_req.format,
        user_id=user_id,
        template_options=export_req.template_options
    )
    
    # Start background task to process the job
    background_tasks.add_task(
        ExportManager.process_export_job,
        export_id=job["id"],
        token=token
    )
    
    # Return job details
    return {
        "id": job["id"],
        "status": job["status"],
        "cv_id": job["cv_id"],
        "format": job["format"],
        "created_at": job["created_at"],
        "download_url": job["download_url"]
    }

@router.get("/api/export/{export_id}", response_model=ExportStatusResponse)
async def get_export_status(
    export_id: str,
    auth = Depends(verify_token)
):
    """Get the status of an export job"""
    user_id = auth["user_id"]
    
    # Get job
    job = await ExportManager.get_export_job(export_id, user_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job with ID {export_id} not found"
        )
    
    return job

@router.get("/api/export", response_model=ExportListResponse)
async def list_exports(
    status: Optional[str] = Query(None, description="Filter by status (pending, processing, completed, failed)"),
    format: Optional[str] = Query(None, description="Filter by format (pdf, docx)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Skip the first N jobs"),
    auth = Depends(verify_token)
):
    """
    List export jobs for the current user
    
    Optional filters can be applied to narrow down the results.
    """
    user_id = auth["user_id"]
    
    # Get user's export jobs
    jobs = await ExportManager.get_user_export_jobs(user_id)
    
    # Apply filters
    if status:
        jobs = [job for job in jobs if job["status"].lower() == status.lower()]
    
    if format:
        jobs = [job for job in jobs if job["format"].lower() == format.lower()]
    
    # Get total count before pagination
    total_count = len(jobs)
    
    # Apply pagination
    jobs = jobs[offset:offset+limit]
    
    return {
        "exports": jobs,
        "count": total_count
    }

@router.get("/api/export/download/{export_id}")
async def download_export(
    export_id: str,
    auth = Depends(verify_token)
):
    """
    Download an export file
    
    The file will be served as an attachment with the appropriate Content-Type.
    """
    user_id = auth["user_id"]
    
    # Get job
    job = await ExportManager.get_export_job(export_id, user_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job with ID {export_id} not found"
        )
    
    # Check if job is completed
    if job["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Export job is not completed. Current status: {job['status']}"
        )
    
    # Check if file exists
    filepath = job.get("filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found"
        )
    
    # Determine content type based on format
    content_type = "application/pdf" if job["format"] == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    # Generate filename
    filename = f"cv_{job['cv_id']}_{datetime.utcnow().strftime('%Y%m%d')}.{job['format']}"
    
    # Return file
    return FileResponse(
        path=filepath,
        media_type=content_type,
        filename=filename
    )

@router.delete("/api/export/{export_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export(
    export_id: str,
    auth = Depends(verify_token)
):
    """Delete an export job and its associated file"""
    user_id = auth["user_id"]
    
    # Delete job
    deleted = await ExportManager.delete_export_job(export_id, user_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job with ID {export_id} not found"
        ) 