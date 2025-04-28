from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os
import logging
from datetime import datetime
import json
import httpx
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import urljoin

# Configure logging
logger = logging.getLogger(__name__)

# Set up OAuth2 with Bearer token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Initialize router
router = APIRouter(prefix="/api/ai")

# OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY environment variable is not set. AI features will not work correctly.")

# Initialize OpenAI client
client = None
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)

# CV Service URL
CV_SERVICE_URL = os.getenv("CV_SERVICE_URL", "http://localhost:8002")
CV_SERVICE_AUTH_TOKEN = os.getenv("CV_SERVICE_AUTH_TOKEN")
if not CV_SERVICE_AUTH_TOKEN:
    logger.warning("CV_SERVICE_AUTH_TOKEN environment variable is not set. AI service cannot authenticate to CV service.")

# Pydantic models for request and response
class CVAnalysisRequest(BaseModel):
    cv_id: str
    sections: Optional[List[str]] = None

class AnalysisResult(BaseModel):
    score: float = Field(..., ge=0, le=10)
    feedback: List[Dict[str, Any]] = []
    improvement_suggestions: List[Dict[str, Any]] = []
    strengths: List[str] = []
    weaknesses: List[str] = []
    industry_fit: List[Dict[str, Any]] = []
    keywords_analysis: Dict[str, Any] = {}

class CVAnalysisResponse(BaseModel):
    cv_id: str
    analysis: AnalysisResult
    timestamp: datetime

class KeywordsRequest(BaseModel):
    text: str

class KeywordsResponse(BaseModel):
    keywords: List[str]

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.5, max=10))
async def fetch_cv_data(cv_id: str, token: str) -> Dict[str, Any]:
    """Fetch CV data from the CV service."""
    
    # Ensure the base URL has a trailing slash for urljoin
    base_url = CV_SERVICE_URL
    if not base_url.endswith('/'):
        base_url += '/'
        
    # Construct the full URL robustly
    target_path = f"api/cv/{cv_id}"
    full_url = urljoin(base_url, target_path)
    logger.info(f"Constructed CV fetch URL: {full_url}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.get(full_url, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch CV data from {full_url}: {response.status_code} {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to fetch CV data from CV service: {response.status_code}"
                )
            
            logger.info(f"Successfully fetched CV data from {full_url}")
            return response.json()
    except httpx.RequestError as e:
        logger.error(f"Error fetching CV data from {full_url}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error communicating with CV service: {str(e)}"
        )

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.5, max=10))
async def analyze_cv_with_openai(cv_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze CV data using OpenAI API."""
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured"
        )
    
    try:
        # Extract CV content from the CV data
        cv_content = {
            "personal_info": cv_data.get("personal_info", {}),
            "summary": cv_data.get("summary", ""),
            "experience": cv_data.get("experience", []),
            "education": cv_data.get("education", []),
            "skills": cv_data.get("skills", []),
            "certifications": cv_data.get("certifications", []),
        }
        
        # Prepare the prompt for GPT
        prompt = f"""
        You are a professional resume reviewer and career coach. Analyze the following CV:
        
        CV_DATA: {json.dumps(cv_content, indent=2)}
        
        Provide a detailed analysis with the following:
        1. Overall score (0-10)
        2. Specific feedback on each section
        3. Improvement suggestions
        4. Strengths
        5. Weaknesses
        6. Industry fit assessment
        7. Keywords analysis for ATS systems
        
        Format your response as structured JSON with the following schema:
        {{
            "score": float,
            "feedback": [
                {{"section": string, "comments": string, "score": float}}
            ],
            "improvement_suggestions": [
                {{"section": string, "suggestion": string, "importance": string}}
            ],
            "strengths": [string],
            "weaknesses": [string],
            "industry_fit": [
                {{"industry": string, "fit_score": float, "reasons": string}}
            ],
            "keywords_analysis": {{
                "found_keywords": [string],
                "missing_keywords": [string],
                "recommendation": string
            }}
        }}
        
        Respond with ONLY the JSON structure above, no other text.
        """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a CV analysis expert that provides structured feedback in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        
        # Extract and parse the response
        analysis_json = response.choices[0].message.content
        analysis_data = json.loads(analysis_json)
        
        return analysis_data
        
    except Exception as e:
        logger.error(f"Error analyzing CV with OpenAI: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing CV: {str(e)}"
        )

@router.post("/analyze", response_model=CVAnalysisResponse)
async def analyze_cv(
    request: CVAnalysisRequest,
    user_token: str = Depends(oauth2_scheme) # Keep user token for potential future endpoint protection
):
    """
    Analyze a CV using AI to provide feedback and suggestions for improvement.
    """
    # Check if service token is configured
    if not CV_SERVICE_AUTH_TOKEN:
        logger.error("CV_SERVICE_AUTH_TOKEN not set. Cannot fetch CV data.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Internal configuration error: CV Service authentication token missing."
        )
        
    # Fetch CV data using the service token
    try:
        # Pass the SERVICE token, not the user's token
        cv_data_response = await fetch_cv_data(request.cv_id, CV_SERVICE_AUTH_TOKEN) 
    except HTTPException as e:
        # Propagate HTTP errors from fetch_cv_data (like 502 Bad Gateway)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during CV data fetch: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error fetching CV data: {str(e)}"
        )
        
    # Extract the actual CV data dictionary from the response 
    # (Assuming fetch_cv_data returns the parsed JSON response)
    cv_data = cv_data_response 

    # Check if OpenAI client is available before proceeding
    if not client:
        logger.error("OpenAI client not available.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI service is not configured or unavailable."
        )

    # Analyze CV data with OpenAI
    try:
        analysis_data = await analyze_cv_with_openai(cv_data)
    except HTTPException as e:
        # Propagate HTTP errors from analyze_cv_with_openai
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during OpenAI analysis: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error analyzing CV: {str(e)}"
        )

    # Structure the final response
    response = CVAnalysisResponse(
        cv_id=request.cv_id,
        analysis=AnalysisResult(**analysis_data), # Ensure data fits the model
        timestamp=datetime.utcnow()
    )

    return response 

@router.post("/keywords", response_model=KeywordsResponse)
async def extract_keywords(request: KeywordsRequest):
    """
    API spec-compliant endpoint for extracting keywords from text.
    """
    # Simple keyword extraction: split by spaces and filter unique words longer than 3 chars
    words = set(word.strip('.,!?()[]{}:;"\'').lower() for word in request.text.split())
    keywords = [w for w in words if len(w) > 3]
    return KeywordsResponse(keywords=keywords) 