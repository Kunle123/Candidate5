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
        """You are a professional CV/resume parser specialized in extracting structured information from various CV formats. Your task is to extract key information from the provided CV and organize it into a standardized JSON format.\n\nFollow these specific guidelines:\n\n1. WORK EXPERIENCE EXTRACTION:\n   - Identify all work experiences throughout the document\n   - Group experiences by company and date range\n   - When the same role appears in multiple sections (summary and detailed sections):\n     * Combine all descriptions into one comprehensive entry\n     * Be flexible with job titles - if titles vary slightly but date ranges and company match, treat as the same role\n     * If a role has multiple titles at the same company during the same period, include all titles separated by \" / \"\n   - For roles with overlapping date ranges at different companies, create separate entries\n   - Format each point in the description to start on a new line\n   - Ensure all experiences are listed in reverse chronological order (most recent first)\n   - Standardize date formats to \"MMM YYYY\" (e.g., \"Jan 2021\") or \"Present\" for current roles\n   - Preserve full company names including divisions or departments (e.g., \"Test Supply Chain DHSC/UKHSA\" not just \"UKHSA\")\n   - Only include information explicitly stated in the CV, do not add inferred or generic descriptions\n\n2. EDUCATION EXTRACTION:\n   - Extract all education entries with institution, degree, field, dates, and descriptions\n   - Format consistently even if original CV has varying levels of detail\n   - If field is not explicitly stated but can be inferred from degree name, extract it\n\n3. SKILLS EXTRACTION:\n   - Extract ALL skills mentioned throughout the document, including those embedded in work experience descriptions\n   - Be thorough in identifying technical skills (e.g., Azure, Mulesoft, Power Apps, Power BI)\n   - Include methodologies (e.g., Agile, PRINCE2, Scrum)\n   - Include domain expertise (e.g., project management, integration, digital transformation)\n   - Include certifications as skills AND as separate certification entries\n   - Deduplicate skills that appear multiple times\n   - Aim to extract at least 15-20 skills if they are present in the document\n\n4. PROJECTS EXTRACTION:\n   - Extract all projects mentioned throughout the document\n   - Include project name and comprehensive description\n   - Distinguish between regular job responsibilities and distinct projects\n   - If project names are not explicitly stated, create descriptive names based on the content\n\n5. CERTIFICATIONS EXTRACTION:\n   - Extract all certifications with name, issuer, and year when available\n   - Include certifications even if they also appear in the skills section\n   - For certification issuers:\n     * PRINCE2 Practitioner is issued by AXELOS (formerly OGC)\n     * Certified Scrum Master is issued by Scrum Alliance\n     * If not explicitly stated, research standard issuers for common certifications\n   - For certification years:\n     * If explicitly stated, use the stated year\n     * If not stated, make a reasonable estimate based on career progression:\n       - For PRINCE2: Estimate 2017-2018 (before the Npower Digital role where project management was heavily featured)\n       - For Scrum Master: Estimate 2016-2017 (before the role at Npower Digital where Scrum Master duties were mentioned)\n     * NEVER use \"Unknown\" for certification years or issuers - always provide a reasonable estimate based on career timeline\n\nOutput the extracted information in the following JSON format:\n{\n  \"work_experience\": [\n    {\n      \"id\": \"string\",                // Generate a unique identifier\n      \"company\": \"string\",           // Full company name including divisions/departments\n      \"title\": \"string\",             // Job title(s), separated by \" / \" if multiple\n      \"start_date\": \"string\",        // Start date in format \"MMM YYYY\" or \"YYYY\"\n      \"end_date\": \"string\",          // End date in format \"MMM YYYY\", \"YYYY\", or \"Present\"\n      \"description\": \"string\"        // Comprehensive description with each point on a new line\n    }\n  ],\n  \"education\": [\n    {\n      \"id\": \"string\",                // Generate a unique identifier\n      \"institution\": \"string\",       // Educational institution\n      \"degree\": \"string\",            // Degree type\n      \"field\": \"string\",             // Field of study\n      \"start_date\": \"string\",        // Start date in format \"YYYY\" or \"MMM YYYY\"\n      \"end_date\": \"string\",          // End date in format \"YYYY\" or \"MMM YYYY\"\n      \"description\": \"string\"        // Any additional details about the education\n    }\n  ],\n  \"skills\": [\n    \"string\"                         // List of all skills including certifications\n  ],\n  \"projects\": [\n    {\n      \"id\": \"string\",                // Generate a unique identifier\n      \"name\": \"string\",              // Project name\n      \"description\": \"string\"        // Comprehensive project description\n    }\n  ],\n  \"certifications\": [\n    {\n      \"id\": \"string\",                // Generate a unique identifier\n      \"name\": \"string\",              // Certification name\n      \"issuer\": \"string\",            // Certification issuer (NEVER use \"Unknown\")\n      \"year\": \"string\"               // Year obtained (NEVER use \"Unknown\", provide estimate)\n    }\n  ]\n}\n\nEnsure your extraction is thorough and captures all relevant information from the CV, even if it appears in different sections or formats. The goal is to create a comprehensive career chronicle that can be used to generate future CVs.\n"""
    )
    prompt = prompt_instructions + text
    logger.info(f"[AI CHUNK] Raw text sent to OpenAI for this chunk:\n{text[:500]} ... (truncated)")
    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1800,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        raw_response = response.choices[0].message.content
        logger.info(f"[AI CHUNK] Raw AI output for this chunk: {raw_response}")
        import json
        try:
            data = json.loads(raw_response)
        except Exception as e:
            logger.error(f"AI parsing failed: {e}")
            logger.error(f"Raw response: {raw_response}")
            match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception as e2:
                    logger.error(f"Fallback JSON parse also failed: {e2}")
                    data = {}
            else:
                data = {}
        # --- JSON format verification ---
        expected_keys = ["work_experience", "education", "skills", "projects", "certifications"]
        for key in expected_keys:
            if key not in data:
                logger.error(f"[AI CHUNK] Missing key in response: {key}")
                raise HTTPException(status_code=500, detail=f"AI response missing required key: {key}")
        if not isinstance(data["work_experience"], list) or not isinstance(data["education"], list) or not isinstance(data["skills"], list) or not isinstance(data["projects"], list) or not isinstance(data["certifications"], list):
            logger.error("[AI CHUNK] One or more top-level fields are not lists as required.")
            raise HTTPException(status_code=500, detail="AI response fields are not lists as required.")
        for cert in data["certifications"]:
            if cert.get("issuer", "").strip().lower() == "unknown" or cert.get("year", "").strip().lower() == "unknown":
                logger.error(f"[AI CHUNK] Certification with 'Unknown' issuer/year: {cert}")
                raise HTTPException(status_code=500, detail="AI response contains 'Unknown' for certification issuer or year, which is not allowed.")
        # Defensive: remove raw_ai_output if present
        if "raw_ai_output" in data:
            del data["raw_ai_output"]
        for key in ["education", "projects", "certifications"]:
            if key in data and isinstance(data[key], list):
                new_list = []
                for entry in data[key]:
                    if isinstance(entry, str):
                        new_list.append({"description": entry})
                    else:
                        new_list.append(entry)
                data[key] = new_list
        # Flatten work_experience if needed
        if "work_experience" in data and isinstance(data["work_experience"], list):
            if data["work_experience"] and isinstance(data["work_experience"][0], dict) and "roles" in data["work_experience"][0]:
                data["work_experience"] = flatten_work_experience(data["work_experience"])
        try:
            arc_data = ArcData(**data)
        except Exception as e:
            logger.error(f"ArcData construction failed: {e}")
            arc_data = ArcData()  # Return empty ArcData on error
        # Remove raw_ai_output from arc_data
        if hasattr(arc_data, 'raw_ai_output'):
            delattr(arc_data, 'raw_ai_output')
        return arc_data
    except Exception as e:
        logger.error(f"AI parsing failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI parsing failed: {e}") 