from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import time
from services.ai_service import extract_comprehensive_keywords, map_profile_to_job_comprehensive

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
