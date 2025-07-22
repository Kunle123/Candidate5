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
        """You are a professional CV/resume parser specialized in extracting structured information from various CV formats. Your task is to extract key information from the provided CV and organize it into a standardized JSON format.\n\n"
        "Follow these specific guidelines:\n\n"
        "1. WORK EXPERIENCE EXTRACTION:\n"
        "   - Identify all work experiences throughout the document\n"
        "   - Group experiences by company and date range\n"
        "   - When the same role appears in multiple sections (summary and detailed sections):\n"
        "     * Combine all descriptions into one comprehensive entry\n"
        "     * Be flexible with job titles - if titles vary slightly but date ranges and company match, treat as the same role\n"
        "     * If a role has multiple titles at the same company during the same period, include all titles separated by \" / \"\n"
        "   - For roles with overlapping date ranges at different companies, create separate entries\n"
        "   - Extract and format descriptions as individual bullet points in an array\n"
        "   - Extract skills mentioned or implied for each role and list them separately\n"
        "   - Ensure all experiences are listed in reverse chronological order (most recent first)\n"
        "   - Standardize date formats to \"MMM YYYY\" (e.g., \"Jan 2021\") or \"Present\" for current roles\n"
        "   - Preserve full company names including divisions or departments (e.g., \"Test Supply Chain DHSC/UKHSA\" not just \"UKHSA\")\n"
        "   - Only include information explicitly stated in the CV, do not add inferred or generic descriptions\n\n"
        "2. EDUCATION EXTRACTION:\n"
        "   - Extract all education entries with institution, degree, field, dates, and descriptions\n"
        "   - Format descriptions as individual bullet points in an array\n"
        "   - Format consistently even if original CV has varying levels of detail\n\n"
        "3. SKILLS, PROJECTS, CERTIFICATIONS:\n"
        "   - Extract all skills, projects, and certifications as separate lists\n"
        "   - For certifications, include name, issuer, and year\n"
        "   - Format project descriptions as individual bullet points in an array\n\n"
        "OUTPUT FORMAT:\n"
        "Return ONLY a valid JSON object in the following schema:\n"
        "{\n"
        "  \"work_experience\": [\n"
        "    {\n"
        "      \"id\": \"string\",\n"
        "      \"company\": \"string\",\n"
        "      \"title\": \"string\",\n"
        "      \"start_date\": \"string\",\n"
        "      \"end_date\": \"string\",\n"
        "      \"description\": [\"bullet 1\", \"bullet 2\"],\n"
        "      \"skills\": [\"Python\", \"AWS\"]\n"
        "    }\n"
        "  ],\n"
        "  \"education\": [\n"
        "    {\n"
        "      \"id\": \"string\",\n"
        "      \"institution\": \"string\",\n"
        "      \"degree\": \"string\",\n"
        "      \"field\": \"string\",\n"
        "      \"start_date\": \"string\",\n"
        "      \"end_date\": \"string\",\n"
        "      \"description\": [\"bullet 1\", \"bullet 2\"]\n"
        "    }\n"
        "  ],\n"
        "  \"skills\": [\"Python\", \"AWS\"],\n"
        "  \"projects\": [\n"
        "    {\n"
        "      \"id\": \"string\",\n"
        "      \"name\": \"string\",\n"
        "      \"description\": [\"bullet 1\", \"bullet 2\"]\n"
        "    }\n"
        "  ],\n"
        "  \"certifications\": [\n"
        "    {\n"
        "      \"id\": \"string\",\n"
        "      \"name\": \"string\",\n"
        "      \"issuer\": \"string\",\n"
        "      \"year\": \"string\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
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
                        "description": {"type": "array", "items": {"type": "string"}},
                        "skills": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["id", "company", "title", "start_date", "end_date", "description", "skills"],
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
                        "description": {"type": "array", "items": {"type": "string"}}
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
                        "description": {"type": "array", "items": {"type": "string"}}
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