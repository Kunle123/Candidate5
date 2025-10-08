"""
CV Import Assistant Endpoint

This endpoint handles CV file uploads, extracts text, and uses OpenAI Assistant
to parse the CV into structured JSON format.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Depends
from sqlalchemy.orm import Session
import tempfile
import os
from assistant_manager import CVAssistantManager
from ai_utils import save_parsed_cv_to_db
from db.database import get_db
from auth import get_current_user
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain"
}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

def get_mime_type(filename):
    import mimetypes
    mime, _ = mimetypes.guess_type(filename)
    return mime

async def validate_upload(file: UploadFile):
    # Check MIME type
    mime_type = file.content_type or get_mime_type(file.filename)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")
    # Save to temp file for processing
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name
    return contents, tmp_path

@router.post("/importassistant")
@limiter.limit("5/minute")
async def import_cv_assistant(
    request: Request,  # Required for SlowAPI
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Import a CV file, extract its text, send it to the OpenAI Assistant for parsing,
    persist to DB, and return structured JSON.
    
    Supports: PDF, DOCX, TXT files (max 2MB)
    Rate limit: 5 requests per minute
    """
    # 1. Validate and scan upload
    contents, tmp_path = await validate_upload(file)
    
    # 2. Extract text from file (support PDF, DOCX, TXT)
    ext = file.filename.split('.')[-1].lower()
    if ext == "pdf":
        import pdfplumber
        with pdfplumber.open(tmp_path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    elif ext in ("docx", "doc"):
        from docx import Document
        doc = Document(tmp_path)
        text = "\n".join([p.text for p in doc.paragraphs])
    elif ext == "txt":
        text = contents.decode("utf-8", errors="ignore")
    else:
        os.unlink(tmp_path)
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF, DOCX, and TXT are supported.")
    
    os.unlink(tmp_path)
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the file.")
    
    # 3. Process with OpenAI Assistant
    try:
        assistant = CVAssistantManager()
        parsed_data = assistant.process_cv(text)
        save_parsed_cv_to_db(parsed_data, user_id, db)
        return {"success": True, "data": parsed_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV processing failed: {e}")
