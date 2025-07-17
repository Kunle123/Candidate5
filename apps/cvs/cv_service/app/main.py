from fastapi import FastAPI, HTTPException, Depends, status, Query, Body, Request, File, UploadFile, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
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
from io import BytesIO
import time
import base64

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
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175,https://c5-frontend-pied.vercel.app").split(",")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
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

@app.get("/api/cv")
async def get_cvs(
    auth: dict = Depends(verify_token), 
    db: Session = Depends(get_db_session),
    type: str = Query(None, description="Filter by type: 'cv' or 'cover_letter'")
):
    """Get all CVs for the current user, optionally filtered by type."""
    user_id = auth["user_id"]
    query = db.query(models.CV).filter(models.CV.user_id == user_id)
    if type:
        query = query.filter(models.CV.type == type)
    cvs = query.order_by(
        desc(models.CV.is_default),
        desc(models.CV.last_modified)
    ).all()
    result = [serialize_cv(cv) for cv in cvs]
    return result

@app.post("/api/cv/upload", status_code=status.HTTP_201_CREATED)
async def create_cv_from_file(
    file: UploadFile = File(...),
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db_session)
):
    """Create a new CV from an uploaded file (legacy endpoint)."""
    logger.info(f"Received file upload: {file.filename}, content type: {file.content_type}")
    user_id = auth["user_id"]
    with NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
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
    # ... rest of legacy logic ...
    # (unchanged)
    # ... existing code ...

@app.middleware("http")
async def log_slow_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    if duration > 2:  # seconds
        logger.warning(f"Slow request: {request.method} {request.url} took {duration:.2f}s")
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled Exception: {exc}\n"
        f"Request: {request.method} {request.url}\n"
        f"Client: {request.client.host if request.client else 'unknown'}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )

@app.post("/api/cv")
@app.post("/api/cv/")
async def generate_cv_docx(
    payload: dict = Body(...),
    auth: dict = Depends(verify_token),
    request: Request = None,
    db: Session = Depends(get_db_session)
):
    """
    Generate a CV DOCX from provided text and return as base64-encoded string in JSON.
    """
    import base64
    try:
        logger.info(f"Received {request.method} to {request.url} from {request.client.host if request.client else 'unknown'} (CV only)")
        logger.info("[DEBUG] generate_docx called: Enforcing strict, professional, consistent CV structure.")
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
        from docx.oxml.ns import qn
        doc = Document()
        # Set page size and margins (A4, 1" margins)
        section = doc.sections[0]
        section.page_height = Inches(11.69)
        section.page_width = Inches(8.27)
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        # Helper: Set font for all runs in a paragraph
        def set_font(paragraph, size, bold=False):
            for run in paragraph.runs:
                run.font.name = 'Arial'
                run._element.rPr.rFonts.set(qn('w:eastAsia'), 'Arial')
                run.font.size = Pt(size)
                run.bold = bold
            paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
        # Helper: Add section heading (Title Case, bold)
        def add_section_heading(text):
            para = doc.add_paragraph()
            run = para.add_run(text.title())
            set_font(para, 14, bold=True)
            para.paragraph_format.space_before = Pt(18)
            para.paragraph_format.space_after = Pt(12)
            return para
        # Helper: Add job block (dates, job title, company)
        def add_job_block(dates, title, company):
            para_dates = doc.add_paragraph(dates)
            set_font(para_dates, 11, bold=False)
            para_dates.paragraph_format.space_before = Pt(12)
            para_dates.paragraph_format.space_after = Pt(0)
            para_title = doc.add_paragraph(title)
            set_font(para_title, 12, bold=True)
            para_title.paragraph_format.space_after = Pt(0)
            para_company = doc.add_paragraph(company)
            set_font(para_company, 11, bold=False)
            para_company.paragraph_format.space_after = Pt(6)
        # Helper: Add bullet point (all regular weight, consistent, real bullet)
        def add_bullet(text, indent=0.25):
            para = doc.add_paragraph()
            para.style = doc.styles['List Bullet']
            para.paragraph_format.left_indent = Inches(indent)
            para.paragraph_format.first_line_indent = Inches(0)
            para.paragraph_format.space_after = Pt(3)
            para.paragraph_format.line_spacing = 1.15
            set_font(para, 11, bold=False)
            para.text = text
            return para
        # Helper: Add sub-bullet (further indented, regular weight)
        def add_sub_bullet(text):
            return add_bullet(text, indent=0.5)
        # Helper: Add contact info (centered, smaller)
        def add_contact_info(text):
            para = doc.add_paragraph(text)
            set_font(para, 10, bold=False)
            para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            para.paragraph_format.space_after = Pt(6)
            return para
        # Parse cv_text
        cv_text = payload.get("cv")
        if not cv_text:
            logger.warning("Missing 'cv' field in request body")
            raise HTTPException(status_code=400, detail="'cv' field is required in the request body.")
        lines = [l.strip() for l in cv_text.splitlines() if l.strip()]
        # Candidate name (first non-empty line)
        if lines:
            para = doc.add_paragraph(lines[0])
            set_font(para, 20, bold=True)
            para.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            para.paragraph_format.space_after = Pt(6)
            lines = lines[1:]
        # Contact info (next line if present)
        if lines and ("@" in lines[0] or any(c.isdigit() for c in lines[0])):
            add_contact_info(lines[0])
            lines = lines[1:]
        # Section parsing
        section_headers = [
            "Summary", "Professional Summary", "Core Competencies", "Experience", "Professional Experience", "Education", "Skills", "Certifications", "Projects", "References"
        ]
        i = 0
        while i < len(lines):
            line = lines[i]
            # Section heading
            if line.title() in section_headers:
                add_section_heading(line)
                i += 1
                continue
            # Dates + job title + company block (pattern: date, title, company)
            if i+2 < len(lines) and any(month in lines[i] for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
                add_job_block(lines[i], lines[i+1], lines[i+2])
                i += 3
                continue
            # Bullet point or sub-bullet
            if line.startswith("•") or line.startswith("-"):
                # Sub-bullet if indented (starts with two spaces or tab)
                if line.startswith("    ") or line.startswith("\t"):
                    add_sub_bullet(line.lstrip("•- \t"))
                else:
                    add_bullet(line[1:].strip())
                i += 1
                continue
            # Default: body text
            para = doc.add_paragraph(line)
            set_font(para, 11)
            para.paragraph_format.space_after = Pt(6)
            i += 1
        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        docx_bytes = buf.getvalue()
        # Persist to DB
        from .models import CV
        new_cv = CV(
            id=uuid.uuid4(),
            user_id=auth["user_id"],
            name="Generated CV",
            description="CV generated via API",
            is_default=False,
            version=1,
            template_id="default",
            summary=None,
            docx_file=docx_bytes,
            type="cv"
        )
        db.add(new_cv)
        db.commit()
        db.refresh(new_cv)
        logger.info(f"CV DOCX generated and persisted in DB for user_id={auth.get('user_id')}, cv_id={new_cv.id}")
        try:
            docx_b64 = base64.b64encode(docx_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Base64 encoding failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to encode DOCX as base64")
        return {
            "filename": f"cv_{new_cv.id}.docx",
            "filedata": docx_b64,
            "cv_id": str(new_cv.id)
        }
    except Exception as e:
        logger.error(f"Error generating CV DOCX: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate CV DOCX")

@app.post("/api/cover-letter")
@app.post("/api/cover-letter/")
async def generate_cover_letter_docx(
    payload: dict = Body(...),
    auth: dict = Depends(verify_token),
    request: Request = None,
    db: Session = Depends(get_db_session)
):
    """
    Generate a Cover Letter DOCX from provided text and return as base64-encoded string in JSON.
    """
    import base64
    try:
        logger.info(f"Received {request.method} to {request.url} from {request.client.host if request.client else 'unknown'} (Cover Letter only)")
        cover_letter = payload.get("cover_letter")
        if not cover_letter:
            logger.warning("Missing 'cover_letter' field in request body")
            raise HTTPException(status_code=400, detail="'cover_letter' field is required in the request body.")
        doc = Document()
        doc.add_heading("Cover Letter", 0)
        for line in cover_letter.splitlines():
            if line.strip() == "":
                doc.add_paragraph()
            else:
                doc.add_paragraph(line)
        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        docx_bytes = buf.getvalue()
        # Persist to DB (as a separate CV record for now)
        from .models import CV
        new_cv = CV(
            id=uuid.uuid4(),
            user_id=auth["user_id"],
            name="Generated Cover Letter",
            description="Cover letter generated via API",
            is_default=False,
            version=1,
            template_id="default",
            summary=None,
            docx_file=docx_bytes,
            type="cover_letter"
        )
        db.add(new_cv)
        db.commit()
        db.refresh(new_cv)
        logger.info(f"Cover Letter DOCX generated and persisted in DB for user_id={auth.get('user_id')}, cv_id={new_cv.id}")
        try:
            docx_b64 = base64.b64encode(docx_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Base64 encoding failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to encode DOCX as base64")
        return {
            "filename": f"cover_letter_{new_cv.id}.docx",
            "filedata": docx_b64,
            "cv_id": str(new_cv.id)
        }
    except Exception as e:
        logger.error(f"Error generating Cover Letter DOCX: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate Cover Letter DOCX")

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
    return await create_cv_from_file(file, auth, db) # Reusing the existing function

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

@app.get("/api/cv/{cv_id}/download")
async def download_persisted_docx(cv_id: str, auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    """
    Return the persisted DOCX as a base64-encoded string in JSON (proxy-friendly).
    """
    import base64
    from .models import CV
    user_id = auth["user_id"]
    cv = db.query(CV).filter(CV.id == cv_id, CV.user_id == user_id).first()
    if not cv or not cv.docx_file:
        raise HTTPException(status_code=404, detail="CV or DOCX file not found")
    try:
        docx_b64 = base64.b64encode(cv.docx_file).decode('utf-8')
    except Exception as e:
        logger.error(f"Base64 encoding failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to encode DOCX as base64")
    return {
        "filename": f"cv_{cv_id}.docx",
        "filedata": docx_b64,
        "cv_id": str(cv_id)
    }

@app.post("/api/applications")
async def create_application(
    payload: dict = Body(...),
    auth: dict = Depends(verify_token),
    db: Session = Depends(get_db_session)
):
    """
    Create an application (role) with CV and cover letter, store both DOCX files.
    """
    import base64
    from .models import Application
    user_id = auth["user_id"]
    role_title = payload.get("role_title")
    job_description = payload.get("job_description")
    cv_text = payload.get("cv_text")
    cover_letter_text = payload.get("cover_letter_text")
    if not (role_title and cv_text and cover_letter_text):
        raise HTTPException(status_code=400, detail="role_title, cv_text, and cover_letter_text are required.")
    # Generate CV DOCX
    from docx import Document
    from io import BytesIO
    cv_doc = Document()
    cv_doc.add_heading("Curriculum Vitae", 0)
    for line in cv_text.splitlines():
        if line.strip() == "":
            cv_doc.add_paragraph()
        else:
            cv_doc.add_paragraph(line)
    cv_buf = BytesIO()
    cv_doc.save(cv_buf)
    cv_buf.seek(0)
    cv_docx_bytes = cv_buf.getvalue()
    # Generate Cover Letter DOCX
    cl_doc = Document()
    cl_doc.add_heading("Cover Letter", 0)
    for line in cover_letter_text.splitlines():
        if line.strip() == "":
            cl_doc.add_paragraph()
        else:
            cl_doc.add_paragraph(line)
    cl_buf = BytesIO()
    cl_doc.save(cl_buf)
    cl_buf.seek(0)
    cl_docx_bytes = cl_buf.getvalue()
    # Store Application
    app = Application(
        user_id=user_id,
        role_title=role_title,
        job_description=job_description,
        cv_docx_file=cv_docx_bytes,
        cover_letter_docx_file=cl_docx_bytes,
        cv_text=cv_text,
        cover_letter_text=cover_letter_text
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return {
        "id": str(app.id),
        "role_title": app.role_title,
        "created_at": app.created_at.isoformat(),
    }

@app.get("/api/applications")
async def list_applications(auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    from .models import Application
    user_id = auth["user_id"]
    apps = db.query(Application).filter(Application.user_id == user_id).order_by(Application.created_at.desc()).all()
    return [
        {
            "id": str(app.id),
            "role_title": app.role_title,
            "created_at": app.created_at.isoformat(),
        } for app in apps
    ]

@app.get("/api/applications/{id}/cv")
async def download_application_cv(id: str = Path(...), auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    from .models import Application
    import base64
    user_id = auth["user_id"]
    app = db.query(Application).filter(Application.id == id, Application.user_id == user_id).first()
    if not app or not app.cv_docx_file:
        raise HTTPException(status_code=404, detail="Application or CV not found")
    docx_b64 = base64.b64encode(app.cv_docx_file).decode('utf-8')
    return {
        "filename": f"cv_{id}.docx",
        "filedata": docx_b64,
        "application_id": str(id)
    }

@app.get("/api/applications/{id}/cover-letter")
async def download_application_cover_letter(id: str = Path(...), auth: dict = Depends(verify_token), db: Session = Depends(get_db_session)):
    from .models import Application
    import base64
    user_id = auth["user_id"]
    app = db.query(Application).filter(Application.id == id, Application.user_id == user_id).first()
    if not app or not app.cover_letter_docx_file:
        raise HTTPException(status_code=404, detail="Application or cover letter not found")
    docx_b64 = base64.b64encode(app.cover_letter_docx_file).decode('utf-8')
    return {
        "filename": f"cover_letter_{id}.docx",
        "filedata": docx_b64,
        "application_id": str(id)
    }