import json
import logging
from typing import Dict, Any
from fastapi import HTTPException, Request
from function_based_profile_manager import get_profile_manager
import httpx

logger = logging.getLogger(__name__)

USER_SERVICE_URL_TEMPLATE = "https://api-gw-production.up.railway.app/api/v1/users/{user_id}/all_sections"

def load_prompt(filename: str) -> str:
    try:
        with open(f"prompts/{filename}", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {filename}")
        raise HTTPException(status_code=500, detail=f"Prompt file not found: {filename}")

def parse_json_response(response_text: str) -> Dict[str, Any]:
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response text: {text[:500]}...")
        raise HTTPException(status_code=500, detail={"error": "Failed to parse LLM response as JSON", "raw_response": text[:1000]})

async def session_start(profile: Dict[str, Any], user_id: str = None) -> Dict[str, Any]:
    try:
        manager = get_profile_manager()
        session_id = manager.start_session(profile, user_id)
        return {
            "session_id": session_id,
            "status": "started",
            "message": "Profile session started successfully"
        }
    except Exception as e:
        logger.error(f"Failed to start session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

async def session_end(session_id: str) -> Dict[str, Any]:
    try:
        manager = get_profile_manager()
        success = manager.end_session(session_id)
        return {
            "session_id": session_id,
            "status": "ended" if success else "not_found",
            "message": "Session ended successfully" if success else "Session not found"
        }
    except Exception as e:
        logger.error(f"Failed to end session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to end session: {str(e)}")

async def cv_preview_function_based(session_id: str, job_description: str) -> Dict[str, Any]:
    try:
        manager = get_profile_manager()
        prompt = load_prompt("cv_preview.txt")
        
        # Preview only needs high-level analysis, not full role enumeration
        response_text = manager.generate_with_profile_function(
            session_id=session_id,
            prompt=prompt,
            user_message=f"Analyze the candidate's profile against this job description and provide a detailed preview with keyword extraction and job match scoring:\n\n{job_description}",
            model="gpt-4o"
        )
        preview_data = parse_json_response(response_text)
        preview_data.update({
            "session_id": session_id,
            "preview_ready": True,
            "generation_method": "function_based"
        })
        return preview_data
    except ValueError as e:
        logger.error(f"Session error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate CV preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CV preview: {str(e)}")

async def cv_generate_function_based(session_id: str, job_description: str) -> Dict[str, Any]:
    try:
        manager = get_profile_manager()
        
        # Get the original profile to extract static data
        original_profile = manager.get_profile(session_id)
        
        # Use batched prompt that instructs LLM to fetch roles in groups of 5
        prompt = load_prompt("cv_generate_batched.txt")
        
        # Use batched approach (5 roles at a time) instead of sending all roles at once
        response_text = manager.generate_with_batched_roles(
            session_id=session_id,
            prompt=prompt,
            user_message=f"Generate a complete CV and cover letter tailored for this job description:\n\n{job_description}",
            model="gpt-4o"
        )
        cv_data = parse_json_response(response_text)
        
        # Merge back static data (education, certifications) that was filtered out
        if "cv" in cv_data:
            # Add education from original profile if not present in AI response
            if "education" not in cv_data["cv"] or not cv_data["cv"]["education"]:
                cv_data["cv"]["education"] = original_profile.get("education", [])
                logger.info(f"[CV GENERATE] Merged {len(original_profile.get('education', []))} education entries from original profile")
            
            # Add certifications from original profile if not present in AI response
            if "certifications" not in cv_data["cv"] or not cv_data["cv"]["certifications"]:
                cv_data["cv"]["certifications"] = original_profile.get("certifications", [])
                logger.info(f"[CV GENERATE] Merged {len(original_profile.get('certifications', []))} certifications from original profile")
        
        cv_data.update({
            "session_id": session_id,
            "generation_method": "function_based",
            "job_description": job_description
        })
        return cv_data
    except ValueError as e:
        logger.error(f"Session error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate CV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CV: {str(e)}")

async def cv_update_function_based(session_id: str, current_cv: Dict[str, Any], update_request: str, job_description: str = None) -> Dict[str, Any]:
    import time
    try:
        manager = get_profile_manager()
        prompt = load_prompt("cv_update.txt")
        update_message = f"""
Update the following CV based on this request: {update_request}

Current CV:
{json.dumps(current_cv, indent=2)}
"""
        if job_description:
            update_message += f"\n\nJob Description Context:\n{job_description}"
        response_text = manager.generate_with_profile_function(
            session_id=session_id,
            prompt=prompt,
            user_message=update_message,
            model="gpt-4o"
        )
        logger.info(f"[CV UPDATE] Raw LLM response: {response_text[:1000]}")
        try:
            updated_cv = parse_json_response(response_text)
        except HTTPException as e:
            logger.error(f"[CV UPDATE] JSON parsing failed. Returning raw response.")
            raise
        updated_cv.update({
            "session_id": session_id,
            "generation_method": "function_based",
            "update_request": update_request,
            "updated_at": int(time.time())
        })
        # Ensure certifications are handled gracefully
        if "certifications" not in updated_cv.get("updated_cv", {}):
            updated_cv["updated_cv"]["certifications"] = []
        return updated_cv
    except ValueError as e:
        logger.error(f"Session error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update CV: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update CV: {str(e)}")

# FastAPI endpoint implementations
async def handle_session_start(request_data: Dict[str, Any], request: Request = None) -> Dict[str, Any]:
    profile = request_data.get("profile")
    user_id = request_data.get("user_id")
    
    # If no profile provided and request available, try to auto-fetch
    if (not profile or profile == {}) and request is not None:
        # Extract user_id from JWT token if not provided
        if not user_id:
            auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
                try:
                    import jwt
                    import os
                    JWT_SECRET = os.getenv("JWT_SECRET", "development_secret_key")
                    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
                    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
                    user_id = payload.get("user_id") or payload.get("id")
                    logger.info(f"Extracted user_id {user_id} from JWT token")
                except Exception as e:
                    logger.warning(f"Failed to decode JWT token: {e}")
        
        # Now try to fetch profile with user_id
        if user_id:
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=400, detail="Authorization header required to auto-fetch profile")
        try:
            async with httpx.AsyncClient() as client:
                url = USER_SERVICE_URL_TEMPLATE.format(user_id=user_id)
                resp = await client.get(url, headers={"Authorization": auth_header})
                if resp.status_code == 200:
                    profile = resp.json()
                    logger.info(f"Fetched profile for user {user_id} from user service.")
                else:
                    logger.warning(f"Failed to fetch profile for user {user_id}: {resp.status_code} {resp.text}")
                    raise HTTPException(status_code=404, detail=f"Could not fetch profile for user {user_id}")
        except Exception as e:
            logger.error(f"Error fetching profile for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Error fetching profile for user {user_id}: {e}")
    if not profile:
        raise HTTPException(status_code=400, detail="Profile data is required")
    return await session_start(profile, user_id)

async def handle_session_end(request_data: Dict[str, Any]) -> Dict[str, Any]:
    session_id = request_data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    return await session_end(session_id)

async def handle_cv_preview(request_data: Dict[str, Any]) -> Dict[str, Any]:
    session_id = request_data.get("session_id")
    job_description = request_data.get("jobDescription")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not job_description:
        raise HTTPException(status_code=400, detail="Job description is required")
    return await cv_preview_function_based(session_id, job_description)

async def handle_cv_generate(request_data: Dict[str, Any]) -> Dict[str, Any]:
    session_id = request_data.get("session_id")
    job_description = request_data.get("jobDescription")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not job_description:
        raise HTTPException(status_code=400, detail="Job description is required")
    return await cv_generate_function_based(session_id, job_description)

async def handle_cv_update(request_data: Dict[str, Any]) -> Dict[str, Any]:
    session_id = request_data.get("session_id")
    current_cv = request_data.get("currentCV")
    update_request = request_data.get("updateRequest")
    job_description = request_data.get("jobDescription")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not current_cv:
        raise HTTPException(status_code=400, detail="Current CV is required")
    if not update_request:
        raise HTTPException(status_code=400, detail="Update request is required")
    return await cv_update_function_based(session_id, current_cv, update_request, job_description)
