from fastapi import APIRouter, HTTPException, Request
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
async def cv_preview(request: CVPreviewRequest):
    try:
        session_manager = get_profile_session_manager()
        vector_store_id = session_manager.get_vector_store_id(request.session_id)
        if not vector_store_id:
            raise HTTPException(
                status_code=404, 
                detail="Session not found or expired. Start a new session."
            )
        prompt = load_prompt("cv_preview.txt")
        logger.debug(f"[CV PREVIEW] Using vector store {vector_store_id}")
        response = openai_client.responses.create(
            model="gpt-4o",
            input=f"{prompt}\n\nAnalyze this job description: {request.job_description}",
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            temperature=0.3
        )
        content = None
        for output_item in response.output:
            if output_item.type == "message":
                for content_item in output_item.content:
                    if content_item.type == "output_text":
                        content = content_item.text
                        break
                break
        if not content:
            raise Exception("No content found in response")
        try:
            analysis_result = json.loads(content)
            return {
                "preview_ready": True, 
                "session_id": request.session_id, 
                **analysis_result
            }
        except Exception:
            parsed = try_parse_json_from_string(content)
            if parsed:
                return {
                    "preview_ready": True, 
                    "session_id": request.session_id, 
                    **parsed
                }
            return {
                "preview_ready": True,
                "session_id": request.session_id,
                "raw_response": content,
                "error": "Could not parse LLM response as JSON"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CV preview failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate CV preview: {str(e)}"
        )

@router.post("/cv/generate")
async def cv_generate(request: CVGenerateRequest):
    try:
        session_manager = get_profile_session_manager()
        vector_store_id = session_manager.get_vector_store_id(request.session_id)
        if not vector_store_id:
            raise HTTPException(
                status_code=404, 
                detail="Session not found or expired. Start a new session."
            )
        prompt = load_prompt("cv_generate.txt")
        logger.info(f"[CV GENERATE] Using vector store {vector_store_id}")
        response = openai_client.responses.create(
            model="gpt-4o",
            input=f"{prompt}\n\nGenerate a complete CV and cover letter tailored to this job description:\n\n{request.job_description}",
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            temperature=0.3
        )
        content = None
        for output_item in response.output:
            if output_item.type == "message":
                for content_item in output_item.content:
                    if content_item.type == "output_text":
                        content = content_item.text
                        break
                break
        if not content:
            raise Exception("No content found in response")
        try:
            result = json.loads(content)
            return {
                **result,
                "strategy": "responses_api_vector_store",
                "session_id": request.session_id,
                "job_description": request.job_description
            }
        except Exception as e:
            parsed = try_parse_json_from_string(content)
            if parsed:
                return {
                    **parsed,
                    "strategy": "responses_api_vector_store",
                    "session_id": request.session_id,
                    "job_description": request.job_description
                }
            logger.error(f"[CV GENERATE] Failed to parse response as JSON: {e}")
            return {
                "error": "Failed to parse LLM response as JSON",
                "raw_response": content[:1000],
                "session_id": request.session_id
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CV generation failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate CV: {str(e)}"
        )

@router.post("/cv/update")
async def cv_update(request: CVUpdateRequest):
    try:
        session_manager = get_profile_session_manager()
        vector_store_id = session_manager.get_vector_store_id(request.session_id)
        if not vector_store_id:
            raise HTTPException(
                status_code=404, 
                detail="Session not found or expired. Start a new session."
            )
        prompt = load_prompt("cv_update.txt")
        logger.info(f"[CV UPDATE] Using vector store {vector_store_id}")
        update_input = f"""
{prompt}

Current CV: {json.dumps(request.current_cv, indent=2)}

Update Request: {request.update_request}

Job Description: {request.job_description}
"""
        response = openai_client.responses.create(
            model="gpt-4o",
            input=update_input,
            tools=[{
                "type": "file_search",
                "vector_store_ids": [vector_store_id]
            }],
            temperature=0.3
        )
        content = None
        for output_item in response.output:
            if output_item.type == "message":
                for content_item in output_item.content:
                    if content_item.type == "output_text":
                        content = content_item.text
                        break
                break
        if not content:
            raise Exception("No content found in response")
        try:
            updated_cv = json.loads(content)
            return {
                **updated_cv,
                "session_id": request.session_id
            }
        except Exception as e:
            parsed = try_parse_json_from_string(content)
            if parsed:
                return {
                    **parsed,
                    "session_id": request.session_id
                }
            logger.error(f"[CV UPDATE] Failed to parse response as JSON: {e}")
            return {
                "error": "Failed to parse LLM response as JSON",
                "raw_response": content[:1000],
                "session_id": request.session_id
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CV update failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to update CV: {str(e)}"
        )

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
