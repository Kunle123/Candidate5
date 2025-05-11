from fastapi import FastAPI, HTTPException, Depends, status, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import os
import uuid
import jwt
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse

# Create FastAPI app
app = FastAPI(title="CandidateV CV Service")

# Try to import optional dependencies, gracefully handle missing ones
try:
    import jwt
except ImportError:
    print("WARNING: PyJWT not installed, authentication features will be limited")
    jwt = None

# Configure CORS
try:
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
except ImportError:
    print("WARNING: CORS middleware not available")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# Models
class CVMetadata(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: bool = False
    version: int = 1
    last_modified: datetime = Field(default_factory=datetime.utcnow)

class CVTemplate(BaseModel):
    id: str
    name: str
    preview_image_url: Optional[str] = None
    description: Optional[str] = None
    category: str
    style_options: Dict[str, Any] = {}

class CVEducation(BaseModel):
    id: str
    institution: str
    degree: str
    field_of_study: str
    start_date: str  # YYYY-MM format
    end_date: Optional[str] = None  # YYYY-MM format or null for current
    description: Optional[str] = None
    included: bool = True  # Whether to include in CV

class CVExperience(BaseModel):
    id: str
    company: str
    position: str
    start_date: str  # YYYY-MM format
    end_date: Optional[str] = None  # YYYY-MM format or null for current
    description: Optional[str] = None
    included: bool = True  # Whether to include in CV

class CVSkill(BaseModel):
    id: str
    name: str
    level: Optional[int] = None  # 1-5, with 5 being the highest
    category: Optional[str] = None
    years_of_experience: Optional[int] = None
    included: bool = True  # Whether to include in CV

class CVLanguage(BaseModel):
    id: str
    name: str
    proficiency: str  # "Basic", "Intermediate", "Advanced", "Fluent", "Native"
    included: bool = True  # Whether to include in CV

class CVProject(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    url: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM format
    end_date: Optional[str] = None  # YYYY-MM format
    included: bool = True  # Whether to include in CV

class CVCertification(BaseModel):
    id: str
    name: str
    issuer: str
    date_issued: str  # YYYY-MM format
    date_expires: Optional[str] = None  # YYYY-MM format
    credential_id: Optional[str] = None
    url: Optional[str] = None
    included: bool = True  # Whether to include in CV

class CVReference(BaseModel):
    id: str
    name: str
    company: Optional[str] = None
    position: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    included: bool = True  # Whether to include in CV

class CVContent(BaseModel):
    template_id: str
    style_options: Dict[str, Any] = {}
    personal_info: Dict[str, Any] = {}
    summary: Optional[str] = None
    experiences: List[CVExperience] = []
    education: List[CVEducation] = []
    skills: List[CVSkill] = []
    languages: List[CVLanguage] = []
    projects: List[CVProject] = []
    certifications: List[CVCertification] = []
    references: List[CVReference] = []
    custom_sections: Dict[str, Any] = {}

class CV(BaseModel):
    id: str
    user_id: str
    metadata: CVMetadata
    content: CVContent
    created_at: datetime
    updated_at: datetime

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
    experiences: Optional[List[CVExperience]] = None
    education: Optional[List[CVEducation]] = None
    skills: Optional[List[CVSkill]] = None
    languages: Optional[List[CVLanguage]] = None
    projects: Optional[List[CVProject]] = None
    certifications: Optional[List[CVCertification]] = None
    references: Optional[List[CVReference]] = None
    custom_sections: Optional[Dict[str, Any]] = None

# Mock database
MOCK_CVS = {}
MOCK_TEMPLATES = {
    "default": {
        "id": "default",
        "name": "Professional",
        "preview_image_url": "https://example.com/templates/professional.jpg",
        "description": "A clean and professional CV template.",
        "category": "Professional",
        "style_options": {
            "color_scheme": "blue",
            "font_family": "Roboto",
            "layout": "standard"
        }
    },
    "modern": {
        "id": "modern",
        "name": "Modern",
        "preview_image_url": "https://example.com/templates/modern.jpg",
        "description": "A modern and creative CV template.",
        "category": "Creative",
        "style_options": {
            "color_scheme": "teal",
            "font_family": "Montserrat",
            "layout": "sidebar"
        }
    },
    "minimalist": {
        "id": "minimalist",
        "name": "Minimalist",
        "preview_image_url": "https://example.com/templates/minimalist.jpg",
        "description": "A simple and minimalist CV template.",
        "category": "Simple",
        "style_options": {
            "color_scheme": "grayscale",
            "font_family": "Open Sans",
            "layout": "compact"
        }
    }
}

# Helper function to simulate authentication
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
        
        # Get user ID from payload
        user_id = payload.get("user_id")
        
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

# Helper function to get user's CVs
def get_user_cvs(user_id: str) -> List[CV]:
    if user_id not in MOCK_CVS:
        return []
    return list(MOCK_CVS[user_id].values())

# Helper function to create an empty CV
def create_empty_cv(user_id: str, name: str, description: Optional[str] = None, template_id: str = "default") -> CV:
    cv_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    cv = CV(
        id=cv_id,
        user_id=user_id,
        metadata=CVMetadata(
            name=name,
            description=description,
            is_default=False,
            version=1,
            last_modified=now
        ),
        content=CVContent(
            template_id=template_id,
            style_options=MOCK_TEMPLATES[template_id]["style_options"],
            personal_info={},
            summary=None,
            experiences=[],
            education=[],
            skills=[],
            languages=[],
            projects=[],
            certifications=[],
            references=[],
            custom_sections={}
        ),
        created_at=now,
        updated_at=now
    )
    
    # Add to mock database
    if user_id not in MOCK_CVS:
        MOCK_CVS[user_id] = {}
    
    MOCK_CVS[user_id][cv_id] = cv
    
    return cv

# Routes
@app.get("/")
async def root():
    return {"message": "CandidateV CV Service"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint for deployment verification"""
    import sys
    import platform
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "jwt_available": jwt is not None,
            "cwd": os.getcwd(),
            "files": os.listdir(".")[:10],  # First 10 files
        }
    }

@app.get("/api/cv/test")
async def test():
    """Test endpoint to check if CV service is working"""
    return {
        "message": "CV Service is responding",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/cv/templates", response_model=List[CVTemplate])
async def get_templates(auth: dict = Depends(verify_token)):
    """Get all CV templates."""
    return list(MOCK_TEMPLATES.values())

@app.get("/api/cv/templates/{template_id}", response_model=CVTemplate)
async def get_template(template_id: str, auth: dict = Depends(verify_token)):
    """Get a specific CV template."""
    if template_id not in MOCK_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    return MOCK_TEMPLATES[template_id]

@app.get("/api/cv", response_model=List[CV])
async def get_cvs(
    auth: dict = Depends(verify_token),
    limit: Optional[int] = Query(None, description="Limit the number of CVs returned"),
    source: Optional[str] = Query(None, description="Filter by CV creation source (e.g., 'wizard')")
):
    """Get all CVs for the current user, with optional filtering and limiting."""
    user_id = auth["user_id"]
    cvs = get_user_cvs(user_id)

    # Filter by source (stub: assume all CVs are from 'wizard' for now)
    if source:
        # If you later add a 'source' field to CV, filter here
        if source == "wizard":
            cvs = cvs  # All are from wizard in this mock
        else:
            cvs = []  # No other sources in mock

    # Sort by created_at descending (most recent first)
    cvs = sorted(cvs, key=lambda cv: cv.created_at, reverse=True)

    # Apply limit
    if limit is not None:
        cvs = cvs[:limit]

    return cvs

@app.post("/api/cv", response_model=CV, status_code=status.HTTP_201_CREATED)
async def create_cv(cv_data: CVCreate, auth: dict = Depends(verify_token)):
    """Create a new CV."""
    user_id = auth["user_id"]
    
    # Check if template exists
    if cv_data.template_id not in MOCK_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template not found"
        )
    
    # If copying from existing CV
    if cv_data.base_cv_id:
        # Check if base CV exists
        if user_id not in MOCK_CVS or cv_data.base_cv_id not in MOCK_CVS[user_id]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Base CV not found"
            )
        
        # Copy base CV
        base_cv = MOCK_CVS[user_id][cv_data.base_cv_id]
        cv = create_empty_cv(user_id, cv_data.name, cv_data.description, cv_data.template_id)
        
        # Copy content
        cv.content = base_cv.content.copy()
        cv.content.template_id = cv_data.template_id
        
        # Update metadata
        cv.metadata.name = cv_data.name
        cv.metadata.description = cv_data.description
        cv.metadata.is_default = cv_data.is_default
        
        # If this is the default CV, update other CVs
        if cv_data.is_default:
            for other_cv_id, other_cv in MOCK_CVS[user_id].items():
                if other_cv_id != cv.id:
                    other_cv.metadata.is_default = False
        
        MOCK_CVS[user_id][cv.id] = cv
        return cv
    
    # Create new empty CV
    cv = create_empty_cv(user_id, cv_data.name, cv_data.description, cv_data.template_id)
    
    # If this is the default CV, update other CVs
    if cv_data.is_default:
        for other_cv_id, other_cv in MOCK_CVS.get(user_id, {}).items():
            if other_cv_id != cv.id:
                other_cv.metadata.is_default = False
        
        cv.metadata.is_default = True
    
    return cv

@app.get("/api/cv/{cv_id}", response_model=CV)
async def get_cv(cv_id: str, auth: dict = Depends(verify_token)):
    """Get a specific CV."""
    user_id = auth["user_id"]
    
    # Check if CV exists
    if user_id not in MOCK_CVS or cv_id not in MOCK_CVS[user_id]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    return MOCK_CVS[user_id][cv_id]

@app.put("/api/cv/{cv_id}/metadata", response_model=CV)
async def update_cv_metadata(
    cv_id: str,
    metadata: CVUpdateMetadata,
    auth: dict = Depends(verify_token)
):
    """Update CV metadata."""
    user_id = auth["user_id"]
    
    # Check if CV exists
    if user_id not in MOCK_CVS or cv_id not in MOCK_CVS[user_id]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    cv = MOCK_CVS[user_id][cv_id]
    
    # Update metadata
    if metadata.name is not None:
        cv.metadata.name = metadata.name
    
    if metadata.description is not None:
        cv.metadata.description = metadata.description
    
    if metadata.is_default is not None:
        # If this is the default CV, update other CVs
        if metadata.is_default:
            for other_cv_id, other_cv in MOCK_CVS[user_id].items():
                if other_cv_id != cv_id:
                    other_cv.metadata.is_default = False
        
        cv.metadata.is_default = metadata.is_default
    
    # Update version and last modified
    cv.metadata.version += 1
    cv.metadata.last_modified = datetime.utcnow()
    cv.updated_at = datetime.utcnow()
    
    return cv

@app.put("/api/cv/{cv_id}/content", response_model=CV)
async def update_cv_content(
    cv_id: str,
    content: CVUpdateContent,
    auth: dict = Depends(verify_token)
):
    """Update CV content."""
    user_id = auth["user_id"]
    
    # Check if CV exists
    if user_id not in MOCK_CVS or cv_id not in MOCK_CVS[user_id]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    cv = MOCK_CVS[user_id][cv_id]
    
    # Update template
    if content.template_id is not None:
        # Check if template exists
        if content.template_id not in MOCK_TEMPLATES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Template not found"
            )
        
        cv.content.template_id = content.template_id
    
    # Update content fields
    if content.style_options is not None:
        cv.content.style_options = content.style_options
    
    if content.personal_info is not None:
        cv.content.personal_info = content.personal_info
    
    if content.summary is not None:
        cv.content.summary = content.summary
    
    if content.experiences is not None:
        cv.content.experiences = content.experiences
    
    if content.education is not None:
        cv.content.education = content.education
    
    if content.skills is not None:
        cv.content.skills = content.skills
    
    if content.languages is not None:
        cv.content.languages = content.languages
    
    if content.projects is not None:
        cv.content.projects = content.projects
    
    if content.certifications is not None:
        cv.content.certifications = content.certifications
    
    if content.references is not None:
        cv.content.references = content.references
    
    if content.custom_sections is not None:
        cv.content.custom_sections = content.custom_sections
    
    # Update version and last modified
    cv.metadata.version += 1
    cv.metadata.last_modified = datetime.utcnow()
    cv.updated_at = datetime.utcnow()
    
    return cv

@app.delete("/api/cv/{cv_id}")
async def delete_cv(cv_id: str, auth: dict = Depends(verify_token)):
    """Delete a CV."""
    user_id = auth["user_id"]
    
    # Check if CV exists
    if user_id not in MOCK_CVS or cv_id not in MOCK_CVS[user_id]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    # Delete CV
    del MOCK_CVS[user_id][cv_id]
    
    return {"message": "CV deleted"}

@app.post("/api/cv/{cv_id}/duplicate", response_model=CV, status_code=status.HTTP_201_CREATED)
async def duplicate_cv(
    cv_id: str,
    cv_data: CVCreate,
    auth: dict = Depends(verify_token)
):
    """Duplicate a CV."""
    user_id = auth["user_id"]
    
    # Check if source CV exists
    if user_id not in MOCK_CVS or cv_id not in MOCK_CVS[user_id]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CV not found"
        )
    
    # Check if template exists
    template_id = cv_data.template_id or MOCK_CVS[user_id][cv_id].content.template_id
    if template_id not in MOCK_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template not found"
        )
    
    # Create new CV
    source_cv = MOCK_CVS[user_id][cv_id]
    new_cv_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    new_cv = CV(
        id=new_cv_id,
        user_id=user_id,
        metadata=CVMetadata(
            name=cv_data.name,
            description=cv_data.description or f"Copy of {source_cv.metadata.name}",
            is_default=cv_data.is_default,
            version=1,
            last_modified=now
        ),
        content=source_cv.content.copy(),
        created_at=now,
        updated_at=now
    )
    
    # Update template if specified
    if cv_data.template_id:
        new_cv.content.template_id = cv_data.template_id
    
    # If this is the default CV, update other CVs
    if cv_data.is_default:
        for other_cv_id, other_cv in MOCK_CVS[user_id].items():
            if other_cv_id != new_cv_id:
                other_cv.metadata.is_default = False
    
    # Add to mock database
    MOCK_CVS[user_id][new_cv_id] = new_cv
    
    return new_cv

@app.get("/api/cv/{cv_id}/download")
async def download_cv(cv_id: str):
    # Assume generated CVs are stored as RTF files in 'generated_cvs/{cv_id}.rtf'
    file_path = os.path.join("generated_cvs", f"{cv_id}.rtf")
    if not os.path.exists(file_path):
        return {"detail": "CV file not found"}, 404
    return FileResponse(file_path, filename=f"cv_{cv_id}.rtf", media_type="application/rtf")

# For testing and development
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True) 