from fastapi import APIRouter, Depends, HTTPException, status
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
class OptimizationTarget(BaseModel):
    section: str
    content: str
    target_job: Optional[str] = None
    target_industry: Optional[str] = None
    tone: Optional[str] = "professional"
    keywords: Optional[List[str]] = None

class OptimizationRequest(BaseModel):
    cv_id: str
    targets: List[OptimizationTarget]

class OptimizedContent(BaseModel):
    section: str
    original_content: str
    optimized_content: str
    improvements: List[str]
    keywords_added: List[str] = []

class OptimizationResponse(BaseModel):
    cv_id: str
    optimized_sections: List[OptimizedContent]
    timestamp: datetime

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
async def optimize_text_with_openai(
    section: str, 
    content: str, 
    target_job: Optional[str] = None,
    target_industry: Optional[str] = None,
    tone: Optional[str] = "professional",
    keywords: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Optimize CV text using OpenAI API."""
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured"
        )
    
    try:
        # Prepare context information
        context = ""
        if target_job:
            context += f"\nTarget Job: {target_job}"
        if target_industry:
            context += f"\nTarget Industry: {target_industry}"
        
        # Prepare keyword information
        keyword_info = ""
        if keywords and len(keywords) > 0:
            keyword_info = f"\nKeywords to include: {', '.join(keywords)}"
        
        # Prepare the prompt for GPT
        prompt = f"""
        You are a professional resume writer and career coach. Optimize the following {section} section:
        
        ORIGINAL CONTENT:
        {content}
        
        {context}
        Desired Tone: {tone}{keyword_info}
        
        Enhance this content to make it more impactful, clear, and tailored to the target job/industry.
        Focus on:
        1. Using active language and quantifiable achievements
        2. Removing fluff and unnecessary words
        3. Highlighting skills and accomplishments relevant to the target role
        4. Incorporating relevant keywords naturally
        5. Maintaining a {tone} tone
        
        Format your response as structured JSON with the following schema:
        {{
            "optimized_content": "The improved content",
            "improvements": ["List of specific improvements made"],
            "keywords_added": ["List of keywords successfully incorporated"]
        }}
        
        Respond with ONLY the JSON structure above, no other text.
        """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a CV optimization expert that provides structured improvements in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        
        # Extract and parse the response
        optimization_json = response.choices[0].message.content
        optimization_data = json.loads(optimization_json)
        
        # Create the result
        result = {
            "section": section,
            "original_content": content,
            "optimized_content": optimization_data.get("optimized_content", ""),
            "improvements": optimization_data.get("improvements", []),
            "keywords_added": optimization_data.get("keywords_added", [])
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Error optimizing text with OpenAI: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error optimizing CV text: {str(e)}"
        )

@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_cv(
    request: OptimizationRequest,
    user_token: str = Depends(oauth2_scheme) # Keep user token
):
    """
    Optimize sections of a CV using AI to improve content and incorporate keywords.
    """
    
    # Check if service token is configured - Needed to potentially fetch full CV if context requires
    if not CV_SERVICE_AUTH_TOKEN:
        logger.warning("CV_SERVICE_AUTH_TOKEN not set. Authentication to CV service may be needed.")
        # Depending on implementation, might not need to fetch CV, so just log warning for now
        # We might only optimize provided content directly.
    
    # For testing purposes or if OpenAI client is not configured
    if not client:
        logger.warning("OpenAI client not configured. Returning mock optimization data.")
        # Create mock response if needed for testing or fallback
        mock_optimized = [
            OptimizedContent(
                section=t.section,
                original_content=t.content,
                optimized_content=f"Mock optimized content for {t.section}.",
                improvements=["Mock improvement 1", "Mock improvement 2"],
                keywords_added=t.keywords or []
            ) for t in request.targets
        ]
        return OptimizationResponse(cv_id=request.cv_id, optimized_sections=mock_optimized, timestamp=datetime.utcnow())

    optimized_results: List[OptimizedContent] = []

    # NOTE: Current implementation optimizes ONLY the provided content. 
    # If full CV context is needed, uncomment the fetch_cv_data call below.
    # If fetching the full CV, ensure CV_SERVICE_AUTH_TOKEN check above raises HTTPException.
    
    # # Fetch full CV data if needed for context (currently commented out)
    # try:
    #     if not CV_SERVICE_AUTH_TOKEN: # Re-check if fetch is uncommented
    #         raise HTTPException(status_code=503, detail="CV Service auth token missing.")
    #     cv_data = await fetch_cv_data(request.cv_id, CV_SERVICE_AUTH_TOKEN)
    # except HTTPException as e:
    #     raise e
    # except Exception as e:
    #     logger.error(f"Error fetching CV for optimization: {e}")
    #     raise HTTPException(status_code=500, detail="Error fetching CV data.")

    for target in request.targets:
        try:
            # Optimize the text using OpenAI
            optimization_result_dict = await optimize_text_with_openai(
                section=target.section,
                content=target.content,
                target_job=target.target_job,
                target_industry=target.target_industry,
                tone=target.tone,
                keywords=target.keywords
            )
            # Convert dict to Pydantic model instance
            optimized_content = OptimizedContent(**optimization_result_dict)
            optimized_results.append(optimized_content)
            
        except HTTPException as e:
            # If OpenAI call fails, log and continue to next target? Or raise immediately?
            # Currently, let's raise immediately to signal failure.
            logger.error(f"Error optimizing section '{target.section}': {e.detail}")
            raise HTTPException(
                status_code=e.status_code,
                detail=f"Error optimizing section '{target.section}': {e.detail}"
            )
        except Exception as e:
            logger.error(f"Unexpected error optimizing section '{target.section}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error optimizing section '{target.section}': {str(e)}"
            )

    # Prepare the final response
    response = OptimizationResponse(
        cv_id=request.cv_id,
        optimized_sections=optimized_results,
        timestamp=datetime.utcnow()
    )

    return response 

@router.post("/optimize-cv", response_model=OptimizationResponse)
async def optimize_cv_spec(
    request: OptimizationRequest,
    user_token: str = Depends(oauth2_scheme)
):
    """
    API spec-compliant endpoint for optimizing a CV.
    """
    return await optimize_cv(request, user_token) 