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
from typing import List, Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("cv_service")

# Create a simple FastAPI app
app = FastAPI(title="CandidateV CV Service")

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

# Mock data for CV templates and CVs
MOCK_TEMPLATES = [
    {
        "id": "template-1",
        "name": "Professional Template",
        "description": "Clean and professional CV template",
        "thumbnail_url": "https://example.com/thumbnails/professional.jpg",
        "is_premium": False
    },
    {
        "id": "template-2",
        "name": "Creative Template",
        "description": "Unique and creative CV template for creative industries",
        "thumbnail_url": "https://example.com/thumbnails/creative.jpg",
        "is_premium": True
    },
    {
        "id": "template-3",
        "name": "Minimal Template",
        "description": "Simple and elegant CV template",
        "thumbnail_url": "https://example.com/thumbnails/minimal.jpg",
        "is_premium": False
    }
]

MOCK_CVS = {
    "user-1": [
        {
            "id": "cv-1",
            "user_id": "user-1",
            "title": "Software Developer CV",
            "template_id": "template-1",
            "content": {
                "personal_info": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "+1234567890",
                    "address": "New York, NY"
                },
                "summary": "Experienced software developer with 5+ years of experience...",
                "experience": [
                    {
                        "title": "Senior Developer",
                        "company": "Tech Corp",
                        "location": "New York, NY",
                        "start_date": "2020-01",
                        "end_date": "present",
                        "description": "Led development of..."
                    }
                ],
                "education": [
                    {
                        "degree": "Bachelor of Science in Computer Science",
                        "institution": "University of Technology",
                        "location": "Boston, MA",
                        "graduation_date": "2015"
                    }
                ],
                "skills": [
                    "JavaScript",
                    "Python",
                    "React",
                    "Node.js"
                ]
            },
            "last_modified": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }
    ]
}

# Routes
@app.get("/")
async def root():
    return {"message": "CandidateV CV Service"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database_connection": "ok",
        "user_service_connection": "ok"
    }

# CV Templates endpoints
@app.get("/api/cv/templates")
async def get_templates():
    """Get all available CV templates."""
    return {
        "items": MOCK_TEMPLATES,
        "total": len(MOCK_TEMPLATES),
        "page": 1,
        "limit": 10
    }

@app.get("/api/cv/templates/{template_id}")
async def get_template(template_id: str):
    """Get a specific CV template by ID."""
    for template in MOCK_TEMPLATES:
        if template["id"] == template_id:
            return template
    
    raise HTTPException(status_code=404, detail="Template not found")

# CV endpoints
@app.get("/api/cv")
async def get_cvs():
    """Get all CVs for the current user."""
    # In a real app, this would use the current user's ID from the token
    user_id = "user-1"  # Mock user ID
    
    user_cvs = MOCK_CVS.get(user_id, [])
    return {
        "items": user_cvs,
        "total": len(user_cvs),
        "page": 1,
        "limit": 10
    }

@app.get("/api/cv/{cv_id}")
async def get_cv(cv_id: str):
    """Get a specific CV by ID."""
    # In a real app, this would use the current user's ID from the token
    user_id = "user-1"  # Mock user ID
    
    user_cvs = MOCK_CVS.get(user_id, [])
    for cv in user_cvs:
        if cv["id"] == cv_id:
            return cv
    
    raise HTTPException(status_code=404, detail="CV not found")

@app.post("/api/cv")
async def create_cv(cv_data: Dict[str, Any]):
    """Create a new CV for the current user."""
    # In a real app, this would use the current user's ID from the token
    user_id = "user-1"  # Mock user ID
    
    new_cv = {
        "id": f"cv-{uuid.uuid4()}",
        "user_id": user_id,
        "title": cv_data.get("title", "New CV"),
        "template_id": cv_data.get("template_id", "template-1"),
        "content": cv_data.get("content", {}),
        "last_modified": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat()
    }
    
    if user_id not in MOCK_CVS:
        MOCK_CVS[user_id] = []
    
    MOCK_CVS[user_id].append(new_cv)
    
    return new_cv

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    logger.info(f"Starting Standalone CV Service on port {port}")
    # Use 127.0.0.1 instead of 0.0.0.0 to match the frontend's expectation
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info") 