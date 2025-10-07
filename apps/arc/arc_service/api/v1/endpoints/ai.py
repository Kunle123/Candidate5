from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import time
import os
import json
import logging
import io
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from profile_session_manager import get_profile_session_manager
from function_based_endpoints import handle_cv_preview, handle_cv_generate, handle_cv_update

logger = logging.getLogger(__name__)

router = APIRouter()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

PROMPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../prompts"))

def load_prompt(filename):
    with open(os.path.join(PROMPT_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()

import re
def try_parse_json_from_string(s):
    s = s.strip()
    if s.startswith('```json'):
        s = s[7:]
    if s.startswith('```'):
        s = s[3:]
    if s.endswith('```'):
        s = s[:-3]
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    match = re.search(r'\{[\s\S]*\}', s)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return None

class CVPreviewRequest(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    job_description: str = Field(..., description="Job description to analyze against")

class CVGenerateRequest(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    job_description: str = Field(..., description="Job description for CV tailoring")

class CVUpdateRequest(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    current_cv: Dict[str, Any] = Field(..., description="Current CV to update")
    update_request: str = Field(..., description="Update instructions")
    job_description: str = Field(..., description="Job description for context")

@router.post("/cv/preview")
async def cv_preview(request: Request):
    data = await request.json()
    return await handle_cv_preview(data)

@router.post("/cv/generate")
async def cv_full_generation(request: Request):
    data = await request.json()
    # Extract Authorization header for credit deduction
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header:
        data["_auth_header"] = auth_header
    return await handle_cv_generate(data)

@router.post("/cv/update")
async def cv_update(request: Request):
    data = await request.json()
    return await handle_cv_update(data)

@router.post("/cv/generate-single-thread")
async def cv_generate_single_thread(request: Request):
    try:
        data = await request.json()
        profile = data.get("profile")
        job_description = data.get("jobDescription") or data.get("job_description")
        if not profile or not job_description:
            return JSONResponse(
                status_code=400, 
                content={"error": "profile and jobDescription are required"}
            )
        session_manager = get_profile_session_manager()
        session_id = await session_manager.start_session(profile)
        try:
            generate_request = CVGenerateRequest(
                session_id=session_id,
                job_description=job_description
            )
            result = await cv_generate(generate_request)
            if "session_id" in result:
                del result["session_id"]
            if "strategy" in result:
                del result["strategy"]
            return result
        finally:
            await session_manager.end_session(session_id)
    except Exception as e:
        logger.error(f"Legacy CV generation failed: {e}")
        return JSONResponse(
            status_code=500, 
            content={"error": f"Failed to generate CV: {str(e)}"}
        )

@router.get("/cv/health")
async def health_check():
    try:
        session_manager = get_profile_session_manager()
        stats = session_manager.get_stats()
        return {
            "status": "healthy",
            "service": "cv_workflow",
            "api_type": "responses_api_vector_store",
            "session_stats": stats,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )
