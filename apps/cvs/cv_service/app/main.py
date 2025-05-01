from fastapi import FastAPI, HTTPException, Depends, status, Query, Body, Request, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
import os
import uuid
import json
import jwt
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from fastapi.security import OAuth2PasswordBearer
import logging
import sys
from docx import Document
from tempfile import NamedTemporaryFile

# Import database and models
from .database import get_db_session, is_sqlite, engine, Base
from . import models

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("cv_service")

# Create FastAPI app
app = FastAPI(title="CandidateV CV Service")

# Environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:3000").split(",")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Pydantic models
class CVMetadata(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: bool = False
    version: int = 1
    last_modified: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True

class CVCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: bool = False
    template_id: str = "default"
    base_cv_id: Optional[str] = None  # If copying from existing CV

class CVUpdateMetadata(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None

class CVUpdateContent(BaseModel):
    template_id: Optional[str] = None
    style_options: Optional[Dict[str, Any]] = None
    personal_info: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    
    # We'll implement these relationships separately
    # experiences: Optional[List[Dict[str, Any]]] = None
    # education: Optional[List[Dict[str, Any]]] = None
    # skills: Optional[List[Dict[str, Any]]] = None
    # languages: Optional[List[Dict[str, Any]]] = None
    # projects: Optional[List[Dict[str, Any]]] = None
    # certifications: Optional[List[Dict[str, Any]]] = None
    # references: Optional[List[Dict[str, Any]]] = None
    
    custom_sections: Optional[Dict[str, Any]] = None

# Helper function to verify JWT tokens
async def verify_token(token: Optional[str] = Depends(oauth2_scheme)):
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Verify token locally
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Accept both 'user_id' and 'id' fields
        user_id = payload.get("user_id") or payload.get("id")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {"user_id": user_id}
    
    except (jwt.PyJWTError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Helper function to serialize database objects to JSON-compatible dictionaries
def serialize_cv(cv, include_relationships=True):
    """Convert a CV database object to a dictionary."""
    result = {
        "id": str(cv.id) if hasattr(cv.id, "hex") else cv.id,
        "user_id": str(cv.user_id) if hasattr(cv.user_id, "hex") else cv.user_id,
        "filename": cv.name,
        "metadata": {
            "name": cv.name,
            "description": cv.description,
            "is_default": cv.is_default,
            "version": cv.version,
            "last_modified": cv.last_modified.isoformat() if cv.last_modified else None
        },
        "content": {
            "template_id": cv.template_id,
            "style_options": json.loads(cv.style_options) if isinstance(cv.style_options, str) else cv.style_options or {},
            "personal_info": json.loads(cv.personal_info) if isinstance(cv.personal_info, str) else cv.personal_info or {},
            "summary": cv.summary,
            "custom_sections": json.loads(cv.custom_sections) if isinstance(cv.custom_sections, str) else cv.custom_sections or {},
        },
        "created_at": cv.created_at.isoformat() if cv.created_at else None,
        "updated_at": cv.updated_at.isoformat() if cv.updated_at else None
    }
    
    # Add relationships if database supports them and they should be included
    if include_relationships and not is_sqlite:
        # Experiences
        result["content"]["experiences"] = []
        for exp in getattr(cv, "experiences", []):
            result["content"]["experiences"].append({
                "id": str(exp.id) if hasattr(exp.id, "hex") else exp.id,
                "company": exp.company,
                "position": exp.position,
                "start_date": exp.start_date,
                "end_date": exp.end_date,
                "description": exp.description,
                "included": exp.included,
                "order": exp.order
            })
        
        # Education
        result["content"]["education"] = []
        for edu in getattr(cv, "education", []):
            result["content"]["education"].append({
                "id": str(edu.id) if hasattr(edu.id, "hex") else edu.id,
                "institution": edu.institution,
                "degree": edu.degree,
                "field_of_study": edu.field_of_study,
                "start_date": edu.start_date,
                "end_date": edu.end_date,
                "description": edu.description,
                "included": edu.included,
                "order": edu.order
            })
        
        # Add other relationships as needed (skills, languages, etc.)
    
    return result

# Routes
@app.get("/")
async def root():
    return {"message": "CandidateV CV Service"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint for deployment verification"""
    import platform
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database_type": "SQLite" if is_sqlite else "PostgreSQL",
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "cwd": os.getcwd()
        }
    }

@app.get("/health")
async def health_check_root():
    return {"status": "ok"}

@app.get("/api/cv")
async def get_cvs(
    auth: dict = Depends(verify_token), 
    db: Session = Depends(get_db_session)
):
    """Get all CVs for the current user."""
    user_id = auth["user_id"]
    
    # Query CVs for this user, ordered by last modified
    cvs = db.query(models.CV).filter(models.CV.user_id == user_id).order_by(
        desc(models.CV.is_default),  # Default CV first
        desc(models.CV.last_modified)  # Then by modification date
    ).all()
    
    # Convert to API response format
    result = [serialize_cv(cv) for cv in cvs]
    
    return result

@app.post("/api/cv", status_code=status.HTTP_201_CREATED)
async def create_cv(
    file: UploadFile = File(...),
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db_session)
):
    """Create a new CV from an uploaded file."""
    logger.info(f"Received file upload: {file.filename}, content type: {file.content_type}")
    user_id = auth["user_id"]

    # Save uploaded file to a temp file
    with NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Parse the .docx file
    try:
        doc = Document(tmp_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        extracted_text = "\n".join(full_text)
    except Exception as e:
        logger.error(f"Error parsing .docx: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse .docx file")
    finally:
        os.unlink(tmp_path)

    # Create new CV record
    cv_id = str(uuid.uuid4())
    now = datetime.utcnow()
    new_cv = models.CV(
        id=cv_id,
        user_id=user_id,
        name=file.filename,
        description="Imported from .docx",
        is_default=False,
        version=1,
        last_modified=now,
        created_at=now,
        updated_at=now,
        template_id="default",
        style_options={},
        personal_info={},
        summary=extracted_text,
        custom_sections={}
    )
    db.add(new_cv)
    db.commit()
    db.refresh(new_cv)

    logger.info(f"CV created with ID: {cv_id}")
    return serialize_cv(new_cv)

@app.get("/api/cv/{cv_id}")
async def get_cv(
    cv_id: str,
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db_session)
):
    """Get a specific CV."""
    user_id = auth["user_id"]
    logger.info(f"Attempting to get CV. ID: '{cv_id}', User ID: '{user_id}'")
    cv = None
    try:
        # Query CV
        cv = db.query(models.CV).filter(
            models.CV.id == cv_id,
            models.CV.user_id == user_id
        ).first()
        logger.info(f"Database query executed for CV ID: '{cv_id}'")
    except Exception as e:
        logger.error(f"Database query failed for CV ID: '{cv_id}'. Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error while fetching CV"
        )

    if not cv:
        logger.warning(f"CV not found or access denied for CV ID: '{cv_id}', User ID: '{user_id}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    logger.info(f"CV found for ID: '{cv_id}'. Serializing.")
    try:
        serialized_cv = serialize_cv(cv)
        logger.info(f"Serialization successful for CV ID: '{cv_id}'")
        return serialized_cv
    except Exception as e:
        logger.error(f"Serialization failed for CV ID: '{cv_id}'. Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing CV data"
        )

@app.put("/api/cv/{cv_id}/metadata")
async def update_cv_metadata(
    cv_id: str,
    metadata: CVUpdateMetadata,
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db_session)
):
    """Update CV metadata."""
    user_id = auth["user_id"]
    
    # Query CV
    cv = db.query(models.CV).filter(
        models.CV.id == cv_id,
        models.CV.user_id == user_id
    ).first()
    
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    # Update fields if provided
    if metadata.name is not None:
        cv.name = metadata.name
    
    if metadata.description is not None:
        cv.description = metadata.description
    
    if metadata.is_default is not None:
        # If this is the default CV, update other CVs
        if metadata.is_default:
            # Find all default CVs for this user and set them to non-default
            default_cvs = db.query(models.CV).filter(
                models.CV.user_id == user_id,
                models.CV.is_default == True,
                models.CV.id != cv_id
            ).all()
            
            for other_cv in default_cvs:
                other_cv.is_default = False
        
        cv.is_default = metadata.is_default
    
    # Update version and timestamps
    cv.version += 1
    cv.last_modified = datetime.utcnow()
    cv.updated_at = datetime.utcnow()
    
    # Save changes
    db.commit()
    db.refresh(cv)
    
    return serialize_cv(cv)

@app.put("/api/cv/{cv_id}/content")
async def update_cv_content(
    cv_id: str,
    content: CVUpdateContent,
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db_session)
):
    """Update CV content."""
    user_id = auth["user_id"]
    
    # Query CV
    cv = db.query(models.CV).filter(
        models.CV.id == cv_id,
        models.CV.user_id == user_id
    ).first()
    
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    # Update fields if provided
    if content.template_id is not None:
        cv.template_id = content.template_id
    
    if content.style_options is not None:
        cv.style_options = json.dumps(content.style_options) if is_sqlite else content.style_options
    
    if content.personal_info is not None:
        cv.personal_info = json.dumps(content.personal_info) if is_sqlite else content.personal_info
    
    if content.summary is not None:
        cv.summary = content.summary
    
    if content.custom_sections is not None:
        cv.custom_sections = json.dumps(content.custom_sections) if is_sqlite else content.custom_sections
    
    # Update version and timestamps
    cv.version += 1
    cv.last_modified = datetime.utcnow()
    cv.updated_at = datetime.utcnow()
    
    # Save changes
    db.commit()
    db.refresh(cv)
    
    return serialize_cv(cv)

@app.delete("/api/cv/{cv_id}")
async def delete_cv(
    cv_id: str,
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db_session)
):
    """Delete a CV."""
    user_id = auth["user_id"]
    
    # Query CV
    cv = db.query(models.CV).filter(
        models.CV.id == cv_id,
        models.CV.user_id == user_id
    ).first()
    
    if not cv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    # Delete CV
    db.delete(cv)
    db.commit()
    
    return {"message": "CV deleted successfully"}

# Exception handler for database errors
@app.exception_handler(Exception)
async def database_exception_handler(request: Request, exc: Exception):
    logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred"},
    )

# --- Database Table Creation --- 
# Ensure tables are created on startup
# NOTE: In production, using Alembic for migrations is recommended
@app.on_event("startup")
def startup_event():
    logger.info("Running startup event: Creating database tables if they don't exist...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        # Depending on the error, you might want to prevent startup
# --- End Database Table Creation --- 

# --- /cvs endpoints (spec-compliant) ---
@app.get("/cvs")
async def get_cvs_v2(auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    return await get_cvs(auth, db)

@app.post("/cvs", status_code=status.HTTP_201_CREATED)
async def create_cv_v2(file: UploadFile = File(...), auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    return await create_cv(file, auth, db)

@app.get("/cvs/{cv_id}")
async def get_cv_v2(cv_id: str, auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    return await get_cv(cv_id, auth, db)

@app.put("/cvs/{cv_id}")
async def update_cv_content_v2(cv_id: str, content: CVUpdateContent, auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    return await update_cv_content(cv_id, content, auth, db)

@app.delete("/cvs/{cv_id}")
async def delete_cv_v2(cv_id: str, auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    return await delete_cv(cv_id, auth, db)

@app.post("/cvs/{cv_id}/analyze")
async def analyze_cv(cv_id: str, jobDescription: dict = Body(...), auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    # Placeholder: return mock missing keywords
    # In a real implementation, analyze the CV content and compare to jobDescription
    return {"missingKeywords": ["Python", "Leadership", "Teamwork"]}

@app.get("/cvs/{cv_id}/download")
async def download_cv(cv_id: str, auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    # Placeholder: return a dummy file response
    from fastapi.responses import StreamingResponse
    import io
    user_id = auth["user_id"]
    cv = db.query(models.CV).filter(models.CV.id == cv_id, models.CV.user_id == user_id).first()
    if not cv:
        raise HTTPException(status_code=404, detail="CV not found")
    # For now, just return the JSON as a file
    file_content = json.dumps(serialize_cv(cv), indent=2)
    return StreamingResponse(io.BytesIO(file_content.encode()), media_type="application/json", headers={"Content-Disposition": f"attachment; filename=cv_{cv_id}.json"})