from fastapi import APIRouter, Request
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
    update_cv_with_openai
)
import os
import json
from concurrent.futures import ThreadPoolExecutor
import asyncio
from arc_service.utils.profile_fetch import get_user_profile

router = APIRouter()

@router.post("/cv/preview")
async def cv_keyword_preview(request: Request):
    """
    Fast keyword preview and job analysis for user review before full CV generation.
    Input: { profile, jobDescription }
    Output: { preview_ready, processing_time, job_analysis, keyword_analysis, match_score, processing_strategy, user_options }
    """
    data = await request.json()
    profile = data.get("profile")
    job_description = data.get("jobDescription") or data.get("job_description")
    start = time.time()
    # 1. Extract comprehensive keywords from job description
    job_analysis = await extract_comprehensive_keywords(job_description)
    # 2. Map profile to keywords for RAG status
    keyword_mapping = map_profile_to_job_comprehensive(profile, job_analysis)
    # 3. Build preview response (leave fields blank/empty if missing, never use mock data)
    match_score = keyword_mapping.get("keyword_coverage", {}).get("coverage_percentage", 0)
    preview = {
        "preview_ready": True,
        "processing_time": f"{round(time.time() - start, 2)} seconds",
        "job_analysis": {
            "job_title": job_analysis.get("job_title", ""),
            "company": job_analysis.get("company", ""),
            "experience_level": job_analysis.get("experience_level", ""),
            "industry": job_analysis.get("industry", ""),
            "primary_keywords": (job_analysis.get("technical_skills") or []) + (job_analysis.get("functional_skills") or [])
        },
        "keyword_analysis": keyword_mapping,
        "match_score": match_score,
        "processing_strategy": {
            "chunking_approach": "auto",
            "estimated_time": "28 seconds",
            "optimization_focus": job_analysis.get("keyword_priority", {}).get("high", [])
        },
        "user_options": {
            "proceed_with_generation": True,
            "modify_keyword_emphasis": True,
            "adjust_focus_areas": True,
            "custom_instructions": True
        }
    }
    return JSONResponse(content=preview)

@router.post("/cv/generate")
async def cv_full_generation(request: Request):
    """
    Full CV generation with user preferences and preview data.
    Input: { profile, user_id/profile_id, jobDescription, previewData, userPreferences }
    Output: { ...full CV, cover letter, validation, update capabilities... }
    """
    data = await request.json()
    profile = data.get("profile")
    user_id = data.get("user_id") or data.get("profile_id")
    job_description = data.get("jobDescription") or data.get("job_description")
    preview_data = data.get("previewData")
    user_preferences = data.get("userPreferences", {})
    # If profile is not provided, fetch it using user_id/profile_id
    if not profile and user_id:
        # Try to get the Authorization header from the request
        token = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]
        if not token:
            return JSONResponse(status_code=401, content={"error": "Authorization token required to fetch profile by user_id."})
        try:
            profile = await get_user_profile(user_id, token)
        except Exception as e:
            return JSONResponse(status_code=404, content={"error": f"Profile not found for user_id: {user_id}. {str(e)}"})
    if not profile:
        return JSONResponse(status_code=400, content={"error": "No profile or user_id provided"})
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
    if not OPENAI_API_KEY or not OPENAI_ASSISTANT_ID:
        return {"error": "OpenAI API key or Assistant ID not set"}
    # 1. Analyze
    analysis = analyze_payload(profile)
    strategy = select_chunking_strategy(analysis)
    # 2. Create chunks
    chunks = create_adaptive_chunks(profile, job_description, strategy)
    # 3. Create global context (if needed)
    global_context = {}  # Optionally, call OpenAI for global context if required
    # 4. Process chunks for raw content only, passing job description and anti-fabrication rules
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=strategy["chunkCount"]) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                process_chunk_with_openai,
                chunk,
                profile,
                job_description,
                OPENAI_API_KEY,
                OPENAI_ASSISTANT_ID
            ) for chunk in chunks
        ]
        chunk_results = await asyncio.gather(*tasks)
    # 5. Final assembly: single unified CV and cover letter
    assembled = assemble_unified_cv(chunk_results, global_context, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID)
    if not assembled or (isinstance(assembled, dict) and "error" in assembled):
        return JSONResponse(status_code=500, content=assembled if assembled else {"error": "Unknown error in CV assembly."})
    return {
        **assembled,
        "strategy": strategy,
        "analysis": analysis,
        "chunks": chunk_results
    }

@router.post("/cv/update")
async def cv_update(request: Request):
    """
    User-driven CV update endpoint (emphasis, keywords, length, etc.).
    Input: { currentCV, updateRequest, originalProfile, jobDescription }
    Output: { ...updated CV... }
    """
    data = await request.json()
    current_cv = data.get("currentCV")
    update_request = data.get("updateRequest")
    original_profile = data.get("originalProfile")
    job_description = data.get("jobDescription") or data.get("job_description")
    updated_cv = update_cv_with_openai(current_cv, update_request, original_profile, job_description)
    return JSONResponse(content=updated_cv)
