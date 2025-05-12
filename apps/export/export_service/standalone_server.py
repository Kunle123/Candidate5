from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import logging
import sys
from datetime import datetime
import time
import uuid
import asyncio
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("export_service")

# Create a simple FastAPI app
app = FastAPI(title="CandidateV Export Service")

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175,https://c5-frontend-pied.vercel.app").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    logger.info(f"Request started: {request.method} {request.url.path} (ID: {request_id})")
    
    try:
        response = await call_next(request)
        
        process_time = time.time() - start_time
        status_code = response.status_code
        logger.info(f"Request completed: {request.method} {request.url.path} "
                   f"(ID: {request_id}) - Status: {status_code} - Time: {process_time:.3f}s")
        
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request failed: {request.method} {request.url.path} "
                    f"(ID: {request_id}) - Error: {str(e)} - Time: {process_time:.3f}s")
        
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id}
        )

# Mock export data
EXPORT_FORMATS = ["pdf", "docx", "txt"]
EXPORT_JOBS = {
    "export-1": {
        "id": "export-1",
        "user_id": "user-1",
        "cv_id": "cv-1",
        "format": "pdf",
        "status": "completed",
        "download_url": "/api/export/download/export-1",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat()
    }
}

# Routes
@app.get("/")
async def root():
    return {"message": "CandidateV Export Service"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database_connection": "ok",
        "cv_service_connection": "ok"
    }

# Export endpoints
@app.get("/api/export/formats")
async def get_export_formats():
    """Get available export formats."""
    return {
        "formats": EXPORT_FORMATS
    }

@app.get("/api/export")
async def get_exports():
    """Get all export jobs for the current user."""
    # In a real app, this would use the current user's ID from the token
    user_id = "user-1"  # Mock user ID
    
    user_exports = [job for job in EXPORT_JOBS.values() if job.get("user_id") == user_id]
    return {
        "items": user_exports,
        "total": len(user_exports),
        "page": 1,
        "limit": 10
    }

@app.get("/api/export/{export_id}")
async def get_export(export_id: str):
    """Get a specific export job by ID."""
    # In a real app, this would use the current user's ID from the token
    user_id = "user-1"  # Mock user ID
    
    if export_id in EXPORT_JOBS and EXPORT_JOBS[export_id].get("user_id") == user_id:
        return EXPORT_JOBS[export_id]
    
    raise HTTPException(status_code=404, detail="Export job not found")

@app.post("/api/export")
async def create_export(export_data: Dict[str, Any]):
    """Create a new export job."""
    # In a real app, this would use the current user's ID from the token
    user_id = "user-1"  # Mock user ID
    
    # Validate request
    if "cv_id" not in export_data:
        raise HTTPException(status_code=400, detail="cv_id is required")
    
    format = export_data.get("format", "pdf").lower()
    if format not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported format. Supported formats: {', '.join(EXPORT_FORMATS)}")
    
    # Create new export job
    export_id = f"export-{uuid.uuid4()}"
    now = datetime.utcnow().isoformat()
    
    new_export = {
        "id": export_id,
        "user_id": user_id,
        "cv_id": export_data["cv_id"],
        "format": format,
        "template_options": export_data.get("template_options", {}),
        "status": "pending",
        "progress": 0,
        "created_at": now,
        "updated_at": now
    }
    
    # In a real app, we would start a background task here to process the export
    # For the mock, we'll just simulate a completed export after a delay
    EXPORT_JOBS[export_id] = new_export
    
    # Return the new export job
    return new_export

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8003"))
    logger.info(f"Starting Standalone Export Service on port {port}")
    # Use 127.0.0.1 instead of 0.0.0.0 to match the frontend's expectation
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info") 