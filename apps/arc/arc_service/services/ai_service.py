import logging
import re
from fastapi import HTTPException
import openai
import os
import json
from concurrent.futures import ThreadPoolExecutor
import asyncio
import time

# --- ENHANCED KEYWORD MAPPING ---
def map_profile_to_job_comprehensive(profile, job_analysis):
    profile_text = str(profile).lower()
    all_keywords = (
        job_analysis.get("technical_skills", []) +
        job_analysis.get("functional_skills", []) +
        job_analysis.get("soft_skills", []) +
        job_analysis.get("industry_terms", []) +
        job_analysis.get("experience_qualifiers", [])
    )
    mapping = {
        "green_keywords": [],
        "amber_keywords": [],
        "red_keywords": [],
        "keyword_coverage": {
            "total_keywords": len(all_keywords),
            "matched_keywords": 0,
            "coverage_percentage": 0
        }
    }
    for keyword in all_keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in profile_text:
            mapping["green_keywords"].append({"keyword": keyword, "evidence": "Found in profile"})
            mapping["keyword_coverage"]["matched_keywords"] += 1
        else:
            # Simple related skill logic: check for partial match
            related = None
            for word in keyword_lower.split():
                if word in profile_text and len(word) > 3:
                    related = word
                    break
            if related:
                mapping["amber_keywords"].append({"keyword": keyword, "related_skill": related, "transfer_rationale": f"{related} is related to {keyword}"})
                mapping["keyword_coverage"]["matched_keywords"] += 1
            else:
                mapping["red_keywords"].append({"keyword": keyword, "gap_severity": "medium", "mitigation": f"Consider gaining experience or training in {keyword}"})
    if mapping["keyword_coverage"]["total_keywords"] > 0:
        mapping["keyword_coverage"]["coverage_percentage"] = round(
            mapping["keyword_coverage"]["matched_keywords"] / mapping["keyword_coverage"]["total_keywords"] * 100
        )
    return mapping

async def extract_comprehensive_keywords(job_description):
    import openai
    import os
    import json
    prompt = f'''
    You are a job analysis and keyword extraction specialist. Analyze this job posting and extract both job metadata AND exactly 12-20 keywords for comprehensive ATS optimization.

    Job Description: {job_description}

    ### JOB METADATA EXTRACTION (REQUIRED)

    **Extract the following information from the job description:**
    - **job_title:** The main job title being advertised (e.g., "Senior Software Developer", "Project Manager")
    - **company:** The company or organization name, if mentioned (use "Not specified" if not found)
    - **experience_level:** Required experience level (e.g., "Senior", "Mid-level", "Entry-level", "5+ years", "Executive")
    - **industry:** The industry or business sector (e.g., "Technology", "Financial Services", "Healthcare", "Manufacturing")

    ### KEYWORD EXTRACTION REQUIREMENTS

    **TOTAL TARGET: 12-20 keywords (no more, no less)**

    **CATEGORY DISTRIBUTION:**
    1. **TECHNICAL SKILLS (4-6 keywords):**
       - Software, tools, platforms, technologies
       - Programming languages, frameworks
       - Technical methodologies, certifications
       - Systems, databases, cloud platforms

    2. **FUNCTIONAL SKILLS (3-5 keywords):**
       - Core job responsibilities and functions
       - Business processes, analysis types
       - Management or operational capabilities
       - Industry-specific functions

    3. **SOFT SKILLS (2-4 keywords):**
       - Leadership, communication, teamwork
       - Problem-solving, analytical thinking
       - Project management, collaboration
       - Adaptability, innovation

    4. **INDUSTRY TERMS (2-4 keywords):**
       - Sector-specific terminology
       - Business domains, market segments
       - Regulatory, compliance, or standards terms
       - Company type or business model terms

    5. **EXPERIENCE QUALIFIERS (1-3 keywords):**
       - Years of experience requirements
       - Seniority levels, team size
       - Budget responsibility, scale indicators
       - Geographic or scope qualifiers

    ### EXTRACTION GUIDELINES

    **PRIORITIZATION RULES:**
    - Keywords mentioned multiple times = higher priority
    - Keywords in job title or requirements section = higher priority
    - Specific technical terms = higher priority than generic terms
    - Measurable qualifications = higher priority

    **KEYWORD SELECTION CRITERIA:**
    - ✅ Terms a recruiter would search for in an ATS
    - ✅ Specific skills, tools, or qualifications
    - ✅ Industry-standard terminology
    - ✅ Measurable experience indicators
    - ❌ Generic words like "experience," "skills," "ability"
    - ❌ Common verbs like "manage," "develop," "work"
    - ❌ Overly broad terms like "technology," "business"

    ### METADATA EXTRACTION GUIDELINES

    **Job Title Extraction:**
    - Look for phrases like "Job Title:", "Position:", "Role:", or titles in headers
    - Extract the most specific title mentioned (e.g., "Senior Software Developer" not just "Developer")
    - If multiple titles mentioned, use the primary/main one

    **Company Extraction:**
    - Look for company names, organization names, or "Company:" labels
    - Extract full company name if available
    - Use "Not specified" if no company name is found

    **Experience Level Extraction:**
    - Look for phrases like "X+ years", "Senior", "Junior", "Entry-level", "Executive"
    - Extract the most specific requirement (e.g., "5+ years" rather than just "experienced")
    - Combine seniority level with years if both present (e.g., "Senior (5+ years)")

    **Industry Extraction:**
    - Identify the business sector or industry context
    - Use standard industry terms (e.g., "Technology", "Financial Services", "Healthcare")
    - Infer from company type, job requirements, or explicit mentions

    ### OUTPUT FORMAT

    **Respond ONLY with a valid JSON object matching this exact schema:**

    {{
      "job_title": "Senior Oracle Developer",
      "company": "TechCorp Financial",
      "experience_level": "Senior (5+ years)",
      "industry": "Financial Services",
      "technical_skills": ["Oracle Database", "SQL Server", "Python", "AWS", "Agile Methodology"],
      "functional_skills": ["Data Analysis", "Project Management", "Business Intelligence", "Process Improvement"],
      "soft_skills": ["Leadership", "Communication", "Problem Solving"],
      "industry_terms": ["Financial Services", "Regulatory Compliance", "Risk Management"],
      "experience_qualifiers": ["5+ years experience", "Team Leadership"],
      "total_keywords": 16,
      "keyword_priority": {{"high": ["Oracle Database", "SQL Server"], "medium": ["Python", "AWS"], "low": ["Agile Methodology"]}}
    }}

    Respond ONLY with a valid JSON object.
    '''
    try:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key not set")
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a job analysis and keyword extraction specialist. Respond ONLY with a valid JSON object."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logging.error(f"[OPENAI EXCEPTION] {e}")
        raise HTTPException(status_code=500, detail=f"Keyword extraction failed: {e}")

def analyze_payload(profile):
    # Example: count roles, estimate size, etc.
    work_experience = profile.get("work_experience", [])
    size_kb = len(json.dumps(profile).encode("utf-8")) / 1024
    role_count = len(work_experience)
    # Estimate career years
    years = set()
    for role in work_experience:
        start = role.get("start_date", "")
        end = role.get("end_date", "")
        for date in (start, end):
            if date and date.isdigit():
                years.add(int(date[:4]))
    career_years = max(years) - min(years) + 1 if years else 0
    return {"sizeKB": size_kb, "roleCount": role_count, "careerYears": career_years}

def select_chunking_strategy(analysis):
    # Example: simple thresholds
    if analysis["roleCount"] <= 3 and analysis["sizeKB"] < 20:
        return {"chunkCount": 1, "strategy": "single"}
    elif analysis["roleCount"] <= 6:
        return {"chunkCount": 2, "strategy": "dual"}
    elif analysis["roleCount"] <= 10:
        return {"chunkCount": 3, "strategy": "triple"}
    else:
        return {"chunkCount": 4, "strategy": "multi"}

def create_adaptive_chunks(profile, job_description, strategy):
    # Example: split work_experience into N chunks
    work_experience = profile.get("work_experience", [])
    chunk_count = strategy["chunkCount"]
    chunk_size = max(1, len(work_experience) // chunk_count)
    chunks = []
    for i in range(chunk_count):
        chunk_roles = work_experience[i*chunk_size:(i+1)*chunk_size]
        chunk = {
            "roles": chunk_roles,
            "profile": profile,
            "job_description": job_description,
            "chunk_index": i
        }
        chunks.append(chunk)
    return chunks

def process_chunk_with_openai(chunk, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID):
    # Example: call OpenAI for each chunk
    prompt = f"""
    You are a CV content processor. Process the provided chunk as per the instructions. Respond ONLY with a valid JSON object.
    Chunk: {json.dumps(chunk)}
    Profile: {json.dumps(profile)}
    Job Description: {job_description}
    """
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a CV content processor. Respond ONLY with a valid JSON object."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logging.error(f"[OPENAI CHUNK ERROR] {e}")
        return {"error": str(e)}

def assemble_unified_cv(chunk_results, global_context, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID):
    # Final assembly step using OpenAI
    assembly_prompt = "You are a CV assembly specialist. Combine processed chunks into a unified CV with strict factual accuracy. Respond ONLY with a valid JSON object."
    user_message = json.dumps({
        "chunks": chunk_results,
        "global_context": global_context,
        "profile": profile,
        "job_description": job_description,
        "instructions": assembly_prompt
    })
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": assembly_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=3072,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logging.error(f"[OPENAI ASSEMBLY ERROR] {e}")
        return {"error": f"Assembly OpenAI error: {e}"}
