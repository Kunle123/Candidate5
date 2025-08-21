import os
import re
import logging
from fastapi import HTTPException
import openai
from .schemas import ArcData
from .models import UserArcData, WorkExperience, Education, Certification, Skill, Project

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
        """You are a professional CV/resume parser specialized in extracting structured information from various CV formats. Your task is to extract key information from the provided CV and organize it into a standardized JSON format.

Follow these specific guidelines:

1. WORK EXPERIENCE EXTRACTION:
   - Identify all work experiences throughout the document
   - Group experiences by company and date range
   - When the same role appears in multiple sections (summary and detailed sections):
     * Combine all descriptions into one comprehensive entry
     * Be flexible with job titles - if titles vary slightly but date ranges and company match, treat as the same role
     * If a role has multiple titles at the same company during the same period, include all titles separated by " / "
   - For roles with overlapping date ranges at different companies, create separate entries
   - Extract and format descriptions as individual bullet points in an array
   - Break down long paragraphs or sentences into separate, meaningful bullet points based on distinct accomplishments, responsibilities, or activities
   - Each bullet point should represent a single key achievement, responsibility, or task
   - Look for natural breakpoints like periods, semicolons, or logical topic changes to separate bullet points
   - Ensure each bullet point is concise and focuses on one main idea
   - Extract skills mentioned or implied for each role and list them separately
   - Ensure all experiences are listed in reverse chronological order (most recent first)
   - Standardize date formats to "MMM YYYY" (e.g., "Jan 2021") or "Present" for current roles
   - Preserve full company names including divisions or departments (e.g., "Test Supply Chain DHSC/UKHSA" not just "UKHSA")
   - Only include information explicitly stated in the CV, do not add inferred or generic descriptions

2. EDUCATION EXTRACTION:
   - Extract all education entries with institution, degree, field, dates, and descriptions
   - Format descriptions as individual bullet points in an array
   - Break down long paragraphs into separate, meaningful bullet points for better readability
   - Each bullet point should focus on a single achievement, coursework area, or relevant detail
   - Format consistently even if original CV has varying levels of detail

3. SKILLS, PROJECTS, CERTIFICATIONS:
   - Extract all skills, projects, and certifications as separate lists
   - For certifications, include name, issuer, and year
   - Format project descriptions as individual bullet points in an array
   - Break down project descriptions into separate bullet points covering different aspects like objectives, technologies used, outcomes, etc.
   - Each bullet point should represent a distinct aspect or achievement of the project

OUTPUT FORMAT:
Return ONLY a valid JSON object in the following schema:
{
  "work_experience": [
    {
      "id": "string",
      "company": "string",
      "title": "string",
      "start_date": "string",
      "end_date": "string",
      "description": ["bullet 1", "bullet 2"],
      "skills": ["Python", "AWS"]
    }
  ],
  "education": [
    {
      "id": "string",
      "institution": "string",
      "degree": "string",
      "field": "string",
      "start_date": "string",
      "end_date": "string",
      "description": ["bullet 1", "bullet 2"]
    }
  ],
  "skills": ["Python", "AWS"],
  "projects": [
    {
      "id": "string",
      "name": "string",
      "description": ["bullet 1", "bullet 2"]
    }
  ],
  "certifications": [
    {
      "id": "string",
      "name": "string",
      "issuer": "string",
      "year": "string"
    }
  ]
}
"""
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
    Extracts the full description and skills for a single work experience entry from the CV using OpenAI.
    work_exp_metadata should be a dict with keys: job_title, company, start_date, end_date, location (optional).
    Returns a dict with 'description' (array of bullets) and 'skills' (array).
    """
    logger = logging.getLogger("arc")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OpenAI API key not set in environment variables.")
        raise HTTPException(status_code=500, detail="OpenAI API key not set")
    client = openai.OpenAI(api_key=openai_api_key)
    # Use the user's stricter prompt
    prompt = (
        "Given the following CV, extract the full description and skills for the work experience at:\n\n"
        f"Company: {work_exp_metadata.get('company', '')}\n"
        f"Job Title: {work_exp_metadata.get('job_title', '')}\n"
        f"Start Date: {work_exp_metadata.get('start_date', '')}\n"
        f"End Date: {work_exp_metadata.get('end_date', '')}\n"
        f"Location: {work_exp_metadata.get('location', '') if work_exp_metadata.get('location') else ''}\n\n"
        "Extract and format the information as follows:\n\n"
        "1. DESCRIPTION EXTRACTION:\n"
        "   - Find all responsibilities, achievements, and accomplishments for this specific role\n"
        "   - Break down long paragraphs or sentences into separate, meaningful bullet points\n"
        "   - Each bullet point should represent a single key achievement, responsibility, or task\n"
        "   - Look for natural breakpoints like periods, semicolons, or logical topic changes\n"
        "   - Ensure each bullet point is concise and focuses on one main idea\n"
        "   - Include all relevant details mentioned for this position\n\n"
        "2. SKILLS EXTRACTION:\n"
        "   - Identify all technical skills, tools, technologies, and competencies mentioned or implied for this role\n"
        "   - Include programming languages, frameworks, software, methodologies, etc.\n"
        "   - Extract skills that are explicitly stated or clearly demonstrated through the described work\n\n"
        "Return ONLY a valid JSON object in the following format:\n"
        "{\n  \"description\": [\"bullet 1\", \"bullet 2\", \"bullet 3\"],\n  \"skills\": [\"Python\", \"AWS\", \"Docker\"]\n}\n\n"
        "IMPORTANT OUTPUT REQUIREMENTS:\n"
        "- Your response must be ONLY the JSON object, nothing else\n"
        "- Do not include any explanatory text, markdown formatting, or code blocks\n"
        "- Do not wrap the JSON in ```json``` or any other formatting\n"
        "- Ensure all strings are properly quoted with double quotes\n"
        "- Ensure proper comma placement between array elements\n"
        "- The response must start with { and end with }\n"
        "- If no skills are found, return an empty array: \"skills\": []\n"
        "- If no description is found, return an empty array: \"description\": []\n\n"
        "Here is the CV:\n\n"
        f"{cv_text}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        raw_response = response.choices[0].message.content.strip()
        logger.info(f"[AI DESCRIPTION] Extracted description for {work_exp_metadata.get('company', '')} - {work_exp_metadata.get('job_title', '')}: {raw_response[:200]}...")
        import json
        return json.loads(raw_response)
    except Exception as e:
        logger.error(f"AI description extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI description extraction failed: {e}")

def save_parsed_cv_to_db(parsed_data, user_id, db):
    import uuid
    # Ensure user_arc_data exists for this user
    user_arc_data = db.query(UserArcData).filter_by(user_id=user_id).first()
    if not user_arc_data:
        user_arc_data = UserArcData(user_id=user_id, arc_data={})
        db.add(user_arc_data)
        db.commit()
        db.refresh(user_arc_data)
    def norm(s):
        return (s or "").strip().lower()
    # Work Experience
    existing_work_exps = {
        (norm(wx.company), norm(wx.title), norm(wx.start_date), norm(wx.end_date)): wx
        for wx in db.query(WorkExperience).filter_by(user_id=user_id).all()
    }
    for idx, wx in enumerate(parsed_data.get("work_experience", [])):
        company = norm(wx.get("company", ""))
        title = norm(wx.get("title", wx.get("job_title", "")))
        start_date = norm(wx.get("start_date", ""))
        end_date = norm(wx.get("end_date", ""))
        key = (company, title, start_date, end_date)
        if key not in existing_work_exps:
            db.add(WorkExperience(
                id=uuid.uuid4(),
                user_id=user_id,
                company=wx.get("company", ""),
                title=wx.get("job_title", wx.get("title", "")),
                start_date=wx.get("start_date", ""),
                end_date=wx.get("end_date", ""),
                description=wx.get("description", None),
                order_index=idx
            ))
    # Education
    existing_educations = {(e.institution, e.degree, e.start_date, e.end_date, tuple(e.description) if isinstance(e.description, list) else e.description): e for e in db.query(Education).filter_by(user_id=user_id).all()}
    for idx, edu in enumerate(parsed_data.get("education", [])):
        desc = edu.get("description", None)
        desc_tuple = tuple(desc) if isinstance(desc, list) else desc
        key = (
            edu.get("institution", ""),
            edu.get("degree", ""),
            edu.get("start_date", None),
            edu.get("end_date", None),
            desc_tuple
        )
        if key not in existing_educations:
            db.add(Education(
                id=uuid.uuid4(),
                user_id=user_id,
                institution=edu.get("institution", ""),
                degree=edu.get("degree", ""),
                field=edu.get("field", None),
                start_date=edu.get("start_date", None),
                end_date=edu.get("end_date", None),
                description=desc,
                order_index=idx
            ))
    # Certifications
    existing_certs = {(c.name, c.issuer, c.year): c for c in db.query(Certification).filter_by(user_id=user_id).all()}
    for idx, cert in enumerate(parsed_data.get("certifications", [])):
        key = (
            cert.get("name", ""),
            cert.get("issuer", None),
            cert.get("year", cert.get("date", None))
        )
        if key not in existing_certs:
            db.add(Certification(
                id=uuid.uuid4(),
                user_id=user_id,
                name=cert.get("name", ""),
                issuer=cert.get("issuer", None),
                year=cert.get("year", cert.get("date", None)),
                order_index=idx
            ))
    # Skills
    existing_skills = set(s.skill for s in db.query(Skill).filter_by(user_id=user_id).all())
    for skill in parsed_data.get("skills", []):
        if skill not in existing_skills:
            db.add(Skill(
                id=uuid.uuid4(),
                user_id=user_id,
                skill=skill
            ))
    # Projects
    existing_projects = set((p.name, tuple(p.description) if isinstance(p.description, list) else p.description) for p in db.query(Project).filter_by(user_id=user_id).all())
    for idx, proj in enumerate(parsed_data.get("projects", [])):
        desc = proj.get("description", None)
        desc_tuple = tuple(desc) if isinstance(desc, list) else desc
        key = (proj.get("name", ""), desc_tuple)
        if key not in existing_projects:
            db.add(Project(
                id=uuid.uuid4(),
                user_id=user_id,
                name=proj.get("name", ""),
                description=desc,
                order_index=idx
            ))
    db.commit() 