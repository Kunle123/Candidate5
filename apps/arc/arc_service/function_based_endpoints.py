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
        import time
        from cv_quality_validator import CVQualityValidator
        from cv_quality_metrics import get_metrics_tracker
        
        start_time = time.time()
        manager = get_profile_manager()
        
        # Get the original profile to extract static data
        original_profile = manager.get_profile(session_id)
        profile_size = CVQualityValidator()._categorize_profile_size(len(original_profile.get("work_experience", [])))
        
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
        
        # 🔍 QUALITY VALIDATION & AUTO-CORRECTION
        validator = CVQualityValidator()
        quality_report = validator.validate_cv(cv_data, original_profile, job_description)
        was_auto_corrected = False
        
        # If validation failed, attempt auto-correction
        if not quality_report.passed:
            logger.warning("[CV GENERATE] Quality validation failed, attempting auto-correction...")
            cv_data, was_corrected = validator.auto_correct_cv(cv_data, original_profile, quality_report)
            was_auto_corrected = was_corrected
            
            if was_corrected:
                logger.info("[CV GENERATE] ✅ CV auto-corrected successfully")
                # Re-validate after correction
                final_report = validator.validate_cv(cv_data, original_profile, job_description)
                if final_report.passed:
                    logger.info("[CV GENERATE] ✅ CV passed validation after auto-correction")
                else:
                    logger.warning("[CV GENERATE] ⚠️ CV still has issues after auto-correction")
                quality_report = final_report  # Use updated report for metrics
            else:
                logger.warning("[CV GENERATE] ⚠️ Auto-correction did not modify CV")
        else:
            logger.info("[CV GENERATE] ✅ CV passed quality validation on first attempt")
        
        # 📊 LOG METRICS
        generation_time = time.time() - start_time
        metrics_tracker = get_metrics_tracker()
        metrics_tracker.log_generation(
            session_id=session_id,
            quality_report=quality_report.to_dict(),
            generation_time_seconds=generation_time,
            model="gpt-4o",
            profile_size=profile_size,
            was_auto_corrected=was_auto_corrected
        )
        
        # Sort roles in reverse chronological order (most recent first)
        if "cv" in cv_data and "professional_experience" in cv_data["cv"] and "roles" in cv_data["cv"]["professional_experience"]:
            roles = cv_data["cv"]["professional_experience"]["roles"]
            
            def parse_date(date_str):
                """Parse date string to comparable format. Returns tuple (year, month) for sorting."""
                if not date_str or date_str.lower() == "present":
                    return (9999, 12)  # Present dates sort first
                
                # Try to extract year and month
                import re
                # Match formats like "Feb 2025", "2025-01", "Jan 2015", etc.
                month_map = {
                    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
                }
                
                # Try "Mon YYYY" format
                match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})', date_str.lower())
                if match:
                    return (int(match.group(2)), month_map[match.group(1)])
                
                # Try "YYYY-MM" format
                match = re.search(r'(\d{4})-(\d{2})', date_str)
                if match:
                    return (int(match.group(1)), int(match.group(2)))
                
                # Try just year "YYYY"
                match = re.search(r'(\d{4})', date_str)
                if match:
                    return (int(match.group(1)), 1)  # Default to January
                
                # Fallback
                return (0, 0)
            
            # Sort by start_date in descending order (most recent first)
            roles.sort(key=lambda role: parse_date(role.get("start_date", "")), reverse=True)
            logger.info(f"[CV GENERATE] Sorted {len(roles)} roles in reverse chronological order")
        
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
    auth_header = request_data.get("_auth_header")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")
    if not job_description:
        raise HTTPException(status_code=400, detail="Job description is required")
    
    # Deduct credits BEFORE generating CV
    if auth_header:
        import httpx
        import os
        
        # Get USER_SERVICE_URL or try multiple fallbacks
        USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
        
        # List of URLs to try in order
        urls_to_try = []
        if USER_SERVICE_URL:
            urls_to_try.append(USER_SERVICE_URL)
        
        # Add fallback URLs (use public URL first since internal DNS may not be configured)
        urls_to_try.extend([
            "https://c5userservice-production.up.railway.app/api",
            "http://user-service.railway.internal/api"  # Backup if internal DNS is configured
        ])
        
        credit_response = None
        last_error = None
        
        for url in urls_to_try:
            try:
                logger.info(f"[CV GENERATE] Attempting credit deduction via: {url}")
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    credit_response = await client.post(
                        f"{url}/user/credits/use",
                        json={"amount": 1},
                        headers={"Authorization": auth_header}
                    )
                    
                    if credit_response.status_code == 402:
                        raise HTTPException(status_code=402, detail="Insufficient credits to generate CV")
                    elif credit_response.status_code == 200:
                        logger.info(f"[CV GENERATE] ✅ Deducted 1 credit via {url}. Remaining: {credit_response.json()}")
                        break  # Success! Exit the loop
                    else:
                        logger.warning(f"[CV GENERATE] Credit deduction failed with {url}: {credit_response.status_code} {credit_response.text}")
                        last_error = f"Status {credit_response.status_code}: {credit_response.text}"
                        continue  # Try next URL
                        
            except httpx.TimeoutException as e:
                logger.warning(f"[CV GENERATE] Timeout with {url}: {e}")
                last_error = f"Timeout with {url}"
                continue  # Try next URL
            except HTTPException:
                raise  # Re-raise HTTPExceptions (like 402)
            except Exception as e:
                logger.warning(f"[CV GENERATE] Error with {url}: {e}")
                last_error = str(e)
                continue  # Try next URL
        
        # If we got here and credit_response is None or not 200, all URLs failed
        if credit_response is None or credit_response.status_code != 200:
            logger.error(f"[CV GENERATE] All credit deduction URLs failed. Last error: {last_error}")
            raise HTTPException(
                status_code=503,
                detail=f"Unable to verify credits - user service unavailable. Last error: {last_error}"
            )
    else:
        logger.warning("[CV GENERATE] No authorization header provided - skipping credit deduction")
    
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
