import os
import re
import logging
from fastapi import HTTPException
import openai
from .schemas import ArcData

def flatten_work_experience(ai_work_experience):
    flat = []
    for entry in ai_work_experience:
        company = entry.get("company")
        date_range = entry.get("date_range")
        # Split date_range into start_date and end_date if possible
        start_date, end_date = None, None
        if date_range and "–" in date_range:
            parts = [p.strip() for p in date_range.split("–")]
            if len(parts) == 2:
                start_date, end_date = parts
        roles = entry.get("roles", [])
        for role in roles:
            flat.append({
                "company": company,
                "title": role.get("title"),
                "start_date": start_date,
                "end_date": end_date,
                "description": "\n".join(role.get("description", [])) if isinstance(role.get("description"), list) else role.get("description", "")
            })
    return flat

def parse_cv_with_ai_chunk(text):
    logger = logging.getLogger("arc")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt_instructions = (
        """You are a professional CV/resume parser specialized in extracting structured information from various CV formats. Your task is to extract key information from the provided CV and organize it into a standardized JSON format.\n\nFollow these specific guidelines:\n\n1. WORK EXPERIENCE EXTRACTION:\n   - Identify all work experiences throughout the document\n   - Group experiences by company and date range\n   - When the same role appears in multiple sections (summary and detailed sections):\n     * Combine all descriptions into one comprehensive entry\n     * Be flexible with job titles - if titles vary slightly but date ranges and company match, treat as the same role\n     * If a role has multiple titles at the same company during the same period, include all titles separated by \" / \"\n   - For roles with overlapping date ranges at different companies, create separate entries\n   - Format each point in the description to start on a new line\n   - Ensure all experiences are listed in reverse chronological order (most recent first)\n   - Standardize date formats to \"MMM YYYY\" (e.g., \"Jan 2021\") or \"Present\" for current roles\n   - Preserve full company names including divisions or departments (e.g., \"Test Supply Chain DHSC/UKHSA\" not just \"UKHSA\")\n   - Only include information explicitly stated in the CV, do not add inferred or generic descriptions\n\n2. EDUCATION EXTRACTION:\n   - Extract all education entries with institution, degree, field, dates, and descriptions\n   - Format consistently even if original CV has varying levels of detail\n   - If field is not explicitly stated but can be inferred from degree name, extract it\n\n3. SKILLS EXTRACTION:\n   - Extract ALL skills mentioned throughout the document, including those embedded in work experience descriptions\n   - Be thorough in identifying technical skills (e.g., Azure, Mulesoft, Power Apps, Power BI)\n   - Include methodologies (e.g., Agile, PRINCE2, Scrum)\n   - Include domain expertise (e.g., project management, integration, digital transformation)\n   - Include certifications as skills AND as separate certification entries\n   - Deduplicate skills that appear multiple times\n   - Aim to extract at least 15-20 skills if they are present in the document\n\n4. PROJECTS EXTRACTION:\n   - Extract all projects mentioned throughout the document\n   - Include project name and comprehensive description\n   - Distinguish between regular job responsibilities and distinct projects\n   - If project names are not explicitly stated, create descriptive names based on the content\n\n5. CERTIFICATIONS EXTRACTION:\n   - Extract all certifications with name, issuer, and year when available\n   - Include certifications even if they also appear in the skills section\n   - For certification issuers:\n     * PRINCE2 Practitioner is issued by AXELOS (formerly OGC)\n     * Certified Scrum Master is issued by Scrum Alliance\n     * If not explicitly stated, research standard issuers for common certifications\n   - For certification years:\n     * If explicitly stated, use the stated year\n     * If not stated, make a reasonable estimate based on career progression:\n       - For PRINCE2: Estimate 2017-2018 (before the Npower Digital role where project management was heavily featured)\n       - For Scrum Master: Estimate 2016-2017 (before the role at Npower Digital where Scrum Master duties were mentioned)\n     * NEVER use \"Unknown\" for certification years or issuers - always provide a reasonable estimate based on career timeline\n\nOutput the extracted information in the following JSON format:\n{...}\n\nEnsure your extraction is thorough and captures all relevant information from the CV, even if it appears in different sections or formats. The goal is to create a comprehensive career chronicle that can be used to generate future CVs."""
    )
    prompt = prompt_instructions + text
    logger.info(f"[AI CHUNK] Raw text sent to OpenAI for this chunk:\n{text[:500]} ... (truncated)")
    # JSON Schema for strict structured output
    cv_json_schema = {
        "type": "object",
        "properties": {
            "work_experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "company": {"type": "string"},
                        "title": {"type": "string"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["id", "company", "title", "start_date", "end_date", "description"],
                    "additionalProperties": False
                }
            },
            "education": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "institution": {"type": "string"},
                        "degree": {"type": "string"},
                        "field": {"type": "string"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["id", "institution", "degree", "field", "start_date", "end_date", "description"],
                    "additionalProperties": False
                }
            },
            "skills": {
                "type": "array",
                "items": {"type": "string"}
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["id", "name", "description"],
                    "additionalProperties": False
                }
            },
            "certifications": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "issuer": {"type": "string"},
                        "year": {"type": "string"}
                    },
                    "required": ["id", "name", "issuer", "year"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["work_experience", "education", "skills", "projects", "certifications"],
        "additionalProperties": False
    }
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3500,
            temperature=0.2,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "cv_parsing",
                    "schema": cv_json_schema,
                    "strict": True
                }
            }
        )
        raw_response = response.choices[0].message.content
        logger.info(f"[AI CHUNK] Raw AI output for this chunk: {raw_response}")
        import json
        data = json.loads(raw_response)
        arc_data = ArcData(**data)
        return arc_data
    except Exception as e:
        logger.error(f"AI parsing failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {e}")

# --- Two-Pass Extraction: First Pass (Metadata Only) ---
def extract_cv_metadata_with_ai(cv_text):
    """
    Extracts only metadata (no descriptions) for work experience, education, and certifications from a CV using OpenAI.
    Returns a dict with lists of work_experiences, education, and certifications.
    """
    logger = logging.getLogger("arc")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    prompt = (
        """
        Given the following CV, extract ONLY the metadata for each work experience, education, and training/certification entry.\n
        For work experience, return a list of objects with:\n
        - job_title\n        - company\n        - start_date\n        - end_date\n        - location (if available)\n        Do NOT include any job descriptions, bullet points, or responsibilities.\n
        For education and training/certifications, return similar metadata (degree, institution, dates, etc.).\n
        Output valid JSON in this schema:\n        {\n          \"work_experiences\": [\n            {\n              \"job_title\": \"...\",\n              \"company\": \"...\",\n              \"start_date\": \"...\",\n              \"end_date\": \"...\",\n              \"location\": \"...\"\n            }\n          ],\n          \"education\": [\n            {\n              \"degree\": \"...\",\n              \"institution\": \"...\",\n              \"start_date\": \"...\",\n              \"end_date\": \"...\"\n            }\n          ],\n          \"certifications\": [\n            {\n              \"name\": \"...\",\n              \"issuer\": \"...\",\n              \"date\": \"...\"\n            }\n          ]\n        }\n
        Here is the CV:\n\n"""
    ) + cv_text
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        raw_response = response.choices[0].message.content
        logger.info(f"[AI METADATA] Raw AI output for metadata extraction: {raw_response}")
        import json
        data = json.loads(raw_response)
        return data
    except Exception as e:
        logger.error(f"AI metadata extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI metadata extraction failed: {e}")

# --- Two-Pass Extraction: Second Pass (Description for Single Work Experience) ---
def extract_work_experience_description_with_ai(cv_text, work_exp_metadata):
    """
    Extracts the full description for a single work experience entry from the CV using OpenAI.
    work_exp_metadata should be a dict with keys: job_title, company, start_date, end_date, location (optional).
    Returns the description as a string.
    """
    logger = logging.getLogger("arc")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    # Build the prompt step by step
    prompt = "Given the following CV, extract the full description (responsibilities, achievements, bullet points, etc.) for the work experience at:\n\n"
    prompt += f"Company: {work_exp_metadata.get('company', '')}\n"
    prompt += f"Job Title: {work_exp_metadata.get('job_title', '')}\n"
    prompt += f"Start Date: {work_exp_metadata.get('start_date', '')}\n"
    prompt += f"End Date: {work_exp_metadata.get('end_date', '')}\n"
    if work_exp_metadata.get('location'):
        prompt += f"Location: {work_exp_metadata.get('location', '')}\n"
    prompt += "Return ONLY the description for this job, as plain text.\n\nHere is the CV:\n\n"
    prompt += cv_text
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.2,
            response_format={"type": "text"}
        )
        description = response.choices[0].message.content.strip()
        logger.info(f"[AI DESCRIPTION] Extracted description for {work_exp_metadata.get('company', '')} - {work_exp_metadata.get('job_title', '')}: {description[:200]}...")
        return description
    except Exception as e:
        logger.error(f"AI description extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI description extraction failed: {e}") 