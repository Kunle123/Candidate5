from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import time
from services.ai_service import (
    extract_comprehensive_keywords,
    map_profile_to_job_comprehensive,
    analyze_payload,
    select_chunking_strategy,
    create_adaptive_chunks,
    process_chunk_with_openai,
    assemble_unified_cv,
    update_cv_with_openai,
    ProfileFileManager,
    handle_large_profile
)
import os
import json
from concurrent.futures import ThreadPoolExecutor
import asyncio
from utils.profile_fetch import get_user_profile
import logging
import io
import openai
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from profile_session_manager import get_profile_session_manager
from openai import OpenAI

logger = logging.getLogger(__name__)

router = APIRouter()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
profile_manager = ProfileFileManager(openai_client)

class CVPreviewRequest(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    job_description: str = Field(..., description="Job description to analyze against")

@router.post("/cv/preview")
async def cv_preview(request: CVPreviewRequest):
    try:
        session_manager = get_profile_session_manager()
        file_id = session_manager.get_file_id(request.session_id)
        if not file_id:
            raise HTTPException(status_code=404, detail="Session not found or expired. Start a new session.")
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a CV analysis expert. Analyze the uploaded profile against the job description and return JSON insights."},
                {"role": "user", "content": f"Analyze this job description: {request.job_description}", "attachments": [{"file_id": file_id, "tools": [{"type": "file_search"}]}]}
            ],
            temperature=0.3
        )
        try:
            analysis_result = json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            analysis_result = {"raw_response": response.choices[0].message.content}
        return {"preview_ready": True, "session_id": request.session_id, **analysis_result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CV preview failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CV preview: {str(e)}")

@router.post("/cv/generate")
async def cv_full_generation(request: Request):
    data = await request.json()
    profile = data.get("profile")
    job_description = data.get("jobDescription") or data.get("job_description")
    if not profile or not job_description:
        return JSONResponse(status_code=400, content={"error": "profile and jobDescription are required"})
    profile_file_id = await handle_large_profile(profile, profile_manager)
    try:
        messages = [
            {"role": "system", "content": "You are a professional CV writer. Use the uploaded profile to create tailored CV content."}
        ]
        sections = ["professional_summary", "work_experience", "skills", "education"]
        cv_sections = {}
        for section in sections:
            messages.append({
                "role": "user",
                "content": f"""
Generate the {section} section for this job description: {job_description}

Requirements:
- Tailor to job requirements
- Use relevant keywords
- Professional tone

Return only the {section} content.
""",
                "attachments": [
                    {"file_id": profile_file_id, "tools": [{"type": "file_search"}]}
                ]
            })
            response = openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=messages
            )
            section_content = response.choices[0].message.content
            cv_sections[section] = section_content
            messages.append({
                "role": "assistant",
                "content": section_content
            })
        messages.append({
            "role": "user",
            "content": f"Now generate a cover letter for this job: {job_description}"
        })
        cover_response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages
        )
        return {
            "cv": cv_sections,
            "cover_letter": cover_response.choices[0].message.content,
            "strategy": "conversation_based",
            "analysis": "Generated using file context"
        }
    finally:
        await profile_manager.cleanup_file(profile_file_id)

@router.post("/cv/update")
async def cv_update(request: Request):
    data = await request.json()
    current_cv = data.get("currentCV")
    update_request = data.get("updateRequest")
    profile = data.get("originalProfile")
    job_description = data.get("jobDescription") or data.get("job_description")
    if not current_cv or not update_request or not profile or not job_description:
        return JSONResponse(status_code=400, content={"error": "currentCV, updateRequest, originalProfile, and jobDescription are required"})
    profile_file_id = await handle_large_profile(profile, profile_manager)
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a CV editor. Update the existing CV based on user instructions."},
                {
                    "role": "user",
                    "content": f"""
Current CV: {json.dumps(current_cv)}

Update Request: {update_request}
Job Description: {job_description}

Please update the CV according to the request while maintaining professional quality.
Return the updated CV in the same JSON structure.
""",
                    "attachments": [
                        {"file_id": profile_file_id, "tools": [{"type": "file_search"}]}
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        updated_cv = json.loads(response.choices[0].message.content)
        return updated_cv
    finally:
        await profile_manager.cleanup_file(profile_file_id)

@router.post("/cv/generate-single-thread")
async def cv_generate_single_thread(request: Request):
    import openai
    import os
    import json
    import time
    logger = logging.getLogger("arc_service")
    data = await request.json()
    profile = data.get("profile")
    job_description = data.get("jobDescription") or data.get("job_description")
    if not profile or not job_description:
        return JSONResponse(status_code=400, content={"error": "profile and jobDescription are required"})
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        return JSONResponse(status_code=500, content={"error": "OpenAI API key not set"})
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    # 1. Upload profile as file
    profile_json = json.dumps(profile, indent=2)
    file_obj = io.BytesIO(profile_json.encode('utf-8'))
    file_obj.name = f"profile_{int(time.time())}.json"
    file = client.files.create(file=file_obj, purpose="assistants")
    file_id = file.id
    try:
        # 2. Compose prompt
        prompt = f"""
You are a professional CV writer. Using the attached profile, generate a complete CV and cover letter tailored to the following job description:\n\n{job_description}\n\nReturn the result as a JSON object with keys: cv, cover_letter.
"""
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You are a professional CV writer."},
                {
                    "role": "user",
                    "content": prompt,
                    "attachments": [
                        {"file_id": file_id, "tools": [{"type": "file_search"}]}
                    ]
                }
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        try:
            result = json.loads(content)
        except Exception as e:
            logger.error(f"[CV GENERATE SINGLE THREAD] Failed to parse LLM response: {e}")
            return JSONResponse(status_code=500, content={"error": "Failed to parse LLM response as JSON", "raw": content})
        return result
    finally:
        try:
            client.files.delete(file_id)
        except Exception as e:
            logger.warning(f"[CV GENERATE SINGLE THREAD] Failed to delete file {file_id}: {e}")
