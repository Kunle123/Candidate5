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
CV_SERVICE_URL = os.getenv("CV_SERVICE_URL")
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

class GenerateCVRequest(BaseModel):
    profile: dict
    job_description: str
    keywords: Optional[list[str]] = None

class GenerateCVResponse(BaseModel):
    cv: str
    cover_letter: str

class UpdateCVRequest(BaseModel):
    profile: dict
    job_description: str
    additional_keypoints: list[str]
    previous_cv: str

class UpdateCVResponse(BaseModel):
    cv: str
    cover_letter: str

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
    logger.info("[DEBUG] /api/ai/keywords endpoint hit")
    if client:
        try:
            N = 20
            logger.info("[DEBUG] Using OpenAI for keyword extraction")
            prompt = f"""
You are an expert ATS (Applicant Tracking System) keyword extraction specialist. Your task is to analyze the following job description and extract EXACTLY {N} of the most critical keywords and phrases that recruiters and ATS systems prioritize when filtering and ranking resumes.

**CRITICAL REQUIREMENT: You MUST return exactly {N} keywords - no more, no less.**

**EXTRACTION CRITERIA:**
Select the top {N} keywords prioritizing them in this order:

1. **HARD SKILLS & TECHNICAL REQUIREMENTS** (Highest Priority)
   - Programming languages, software, tools, platforms
   - Technical certifications and credentials  
   - Industry-specific technologies and methodologies
   - Measurable technical competencies

2. **QUALIFICATIONS & EXPERIENCE REQUIREMENTS** (High Priority)
   - Education requirements (degree types, fields of study)
   - Years of experience (specific numbers: \"3+ years\", \"5-7 years\")
   - Professional certifications and licenses
   - Industry experience requirements

3. **JOB TITLES & ROLE-SPECIFIC TERMS** (Medium-High Priority)
   - Exact job titles mentioned
   - Related role titles and seniority levels
   - Department or function names
   - Industry-specific role terminology

4. **SOFT SKILLS & COMPETENCIES** (Medium Priority - only if space allows)
   - Communication, leadership, teamwork abilities
   - Problem-solving and analytical thinking
   - Project management and organizational skills
   - Only include if explicitly mentioned as requirements

**PRIORITIZATION RULES:**
- Prioritize keywords that appear multiple times in the job description
- Give higher weight to terms in \"Requirements\" or \"Qualifications\" sections
- Include both exact phrases and individual component words when relevant
- Focus on \"must-have\" requirements over \"nice-to-have\" preferences
- If multiple similar terms exist, choose the most commonly used industry standard

**KEYWORD FORMAT GUIDELINES:**
- Include both acronyms and full terms when both appear (e.g., \"SQL\", \"Structured Query Language\")
- Preserve exact capitalization and formatting as written
- Include compound phrases as single keywords when they represent unified concepts
- Maintain industry-standard terminology and spelling

**COUNT ENFORCEMENT:**
- Count your keywords before finalizing
- If you have more than {N}, remove the least critical ones
- If you have fewer than {N}, add the next most important keywords from the job description
- Double-check that your final array contains exactly {N} elements

**OUTPUT FORMAT:**
Return ONLY a JSON array containing exactly {N} strings, ordered by priority (most critical first). 
Example format for {N} keywords: [\"keyword1\", \"keyword2\", \"keyword3\", \"keyword4\"]
No additional text, explanations, or formatting outside the JSON array.

**JOB DESCRIPTION:**
{request.text}
"""
            response = client.chat.completions.create(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting keywords from text. Respond with only a JSON array of keywords."},
                    {"role": "user", "content": prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "keyword_extraction",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "keywords": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "minItems": 20,
                                    "maxItems": 20
                                }
                            },
                            "required": ["keywords"],
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                },
                temperature=0.2,
            )
            logger.info(f"[DEBUG] OpenAI response: {response}")
            content = response.choices[0].message.content
            if isinstance(content, str):
                import json
                content = json.loads(content)
            keywords = content["keywords"]
            logger.info(f"[DEBUG] Returning {len(keywords)} keywords from OpenAI")
            return KeywordsResponse(keywords=keywords)
        except Exception as e:
            logger.error(f"[ERROR] OpenAI keyword extraction failed: {str(e)}. Falling back to rule-based extraction.")
            # Fallback to rule-based extraction below
    logger.info("[DEBUG] Using fallback rule-based keyword extraction")
    words = set(word.strip('.,!?()[]{}:;"\'').lower() for word in request.text.split())
    keywords = [w for w in words if len(w) > 3]
    logger.info(f"[DEBUG] Returning {len(keywords)} keywords from fallback")
    return KeywordsResponse(keywords=keywords) 

@router.post("/generate-cv", response_model=GenerateCVResponse)
async def generate_cv(request: GenerateCVRequest):
    """
    Generate a CV and cover letter using the user's profile and job description.
    Emphasize the provided keywords if present. Do NOT include any content from the job advert in the CV.
    Follows strict source fidelity and completeness rules.
    """
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured.")
    try:
        # Build the system prompt from docs/assistant_system_instructions.md
        system_prompt = """
You are an expert career assistant and professional resume writer, specializing in creating comprehensive, executive-level CVs for senior technology leaders. Your task is to generate a tailored CV and personalized cover letter that strategically positions the candidate's COMPLETE experience to match specific job requirements while staying strictly within the bounds of the source material.

[...TRUNCATED: Use the full prompt from docs/assistant_system_instructions.md here...]

USER CV DATA (JSON):\n{profile}\n\nJOB ADVERT (FOR STRATEGIC TAILORING REFERENCE ONLY - DO NOT INCLUDE CONTENT FROM THIS IN THE CV):\n{job_description}\n\nRESPONSE FORMAT:\n{{\n  \"cv\": \"...\",\n  \"cover_letter\": \"...\"\n}}\n"""
        # Format the prompt with user data
        prompt = system_prompt.format(profile=request.profile, job_description=request.job_description)
        if request.keywords:
            prompt += f"\nKEYWORDS TO EMPHASIZE: {', '.join(request.keywords)}\n"
        # Call OpenAI (assume chat completion)
        completion = await client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.3,
            max_tokens=3000
        )
        # Parse response
        import json as pyjson
        try:
            result = pyjson.loads(completion.choices[0].message.content)
        except Exception:
            raise HTTPException(status_code=500, detail="AI response was not valid JSON.")
        return GenerateCVResponse(**result)
    except Exception as e:
        logger.error(f"Error generating CV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating CV: {str(e)}") 

@router.post("/update-cv", response_model=UpdateCVResponse)
async def update_cv(request: UpdateCVRequest):
    """
    Update a CV and cover letter by integrating additional key points. Maintains all previous requirements for source fidelity and structure.
    """
    if not client:
        raise HTTPException(status_code=503, detail="OpenAI client not configured.")
    try:
        # Build the system prompt from docs/assistant_system_instructions.md
        system_prompt = """
You are an expert career assistant and professional resume writer, specializing in creating comprehensive, executive-level CVs for senior technology leaders. Your task is to generate a tailored CV and personalized cover letter that strategically positions the candidate's COMPLETE experience to match specific job requirements while staying strictly within the bounds of the source material.

[...TRUNCATED: Use the full prompt from docs/assistant_system_instructions.md here...]

USER CV DATA (JSON):\n{profile}\n\nJOB ADVERT (FOR STRATEGIC TAILORING REFERENCE ONLY - DO NOT INCLUDE CONTENT FROM THIS IN THE CV):\n{job_description}\n\nPREVIOUS CV:\n{previous_cv}\n\nADDITIONAL KEY POINTS TO INTEGRATE:\n{additional_keypoints}\n\nRESPONSE FORMAT:\n{{\n  \"cv\": \"...updated...\",\n  \"cover_letter\": \"...\"\n}}\n"""
        # Format the prompt with user data
        prompt = system_prompt.format(
            profile=request.profile,
            job_description=request.job_description,
            previous_cv=request.previous_cv,
            additional_keypoints="\n".join(request.additional_keypoints)
        )
        # Call OpenAI (assume chat completion)
        completion = await client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.3,
            max_tokens=3000
        )
        # Parse response
        import json as pyjson
        try:
            result = pyjson.loads(completion.choices[0].message.content)
        except Exception:
            raise HTTPException(status_code=500, detail="AI response was not valid JSON.")
        return UpdateCVResponse(**result)
    except Exception as e:
        logger.error(f"Error updating CV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating CV: {str(e)}") 