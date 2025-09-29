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
    chunk_type = chunk.get("chunk_type") or chunk.get("type") or "recent_roles"
    if chunk_type == "recent_roles":
        prompt = f"""
You are a CV content processor for RECENT CAREER ROLES. You will receive:
- CHUNK DATA: Specific roles to process (2020-present typically)
- GLOBAL CONTEXT: Job analysis and alignment strategies
- JOB DESCRIPTION: Full job posting for direct keyword reference
- PROFILE CONTEXT: Complete candidate profile for validation

### STRICT ANTI-FABRICATION ENFORCEMENT

**SKILL VALIDATION RULES:**
- ONLY include skills explicitly mentioned or clearly demonstrated in the profile
- NEVER claim experience with tools/technologies not in the candidate's history
- Use intelligent keyword substitution ONLY where factually supported
- If a job-required skill is missing, DO NOT fabricate it

**ACHIEVEMENT VALIDATION RULES:**
- ONLY rephrase existing achievements from the profile
- NEVER invent metrics, outcomes, or accomplishments
- Every achievement must be traceable to original profile content
- Maintain factual accuracy of all quantified results

**EXPERIENCE VALIDATION RULES:**
- NEVER exaggerate years of experience or seniority levels
- Match responsibility levels to demonstrated complexity in profile
- Preserve accurate timeline and career progression
- Do not inflate job titles or scope of work

### JOB ALIGNMENT WITH FACTUAL BOUNDARIES

**KEYWORD OPTIMIZATION:**
- Use job description keywords where candidate has relevant experience
- Apply safe substitutions from global context (e.g., \"Oracle Fusion\" → \"Oracle ERP (Fusion)\")
- Prioritize GREEN keywords (exact matches) over AMBER keywords (transferable)
- For RED keywords (missing), do not fabricate - focus on related strengths

**CONTENT PRIORITIZATION:**
- Priority 1: Direct job keyword matches with quantified achievements from profile
- Priority 2: Strong job alignment using transferable skills with evidence
- Priority 3: Supporting experience relevant to job requirements

### OUTPUT FORMAT (JSON):
<output as previously specified>

Chunk Data: {json.dumps(chunk)}
Global Context: {json.dumps(profile.get('global_context', {}))}
Job Description: {job_description}
Profile Context: {json.dumps(profile)}
"""
    elif chunk_type == "supporting_roles":
        prompt = f"""
You are a CV content processor for SUPPORTING CAREER ROLES (typically 2010-2019). You receive the same comprehensive input as the recent roles processor.

### ANTI-FABRICATION ENFORCEMENT
Apply the same strict validation rules as recent roles processor:
- Only demonstrated skills and achievements
- No exaggeration of experience levels
- Factual accuracy maintained throughout

### PRIORITY CONSTRAINTS
**You can ONLY assign priorities 2, 3, or 4 to content in this chunk**
- Priority 2: Strong job alignment with transferable skills
- Priority 3: Relevant supporting experience
- Priority 4: General professional development

### FOCUS AREAS
- Skill progression and development evidence
- Career advancement demonstration
- Supporting evidence for job requirements
- Professional growth trajectory

### OUTPUT FORMAT
Same structure as recent roles processor with:
- Supporting role focus
- Priority range 2-4
- Emphasis on skill development and progression
- Anti-fabrication validation for all content

Chunk Data: {json.dumps(chunk)}
Global Context: {json.dumps(profile.get('global_context', {}))}
Job Description: {job_description}
Profile Context: {json.dumps(profile)}
"""
    elif chunk_type == "timeline_roles":
        prompt = f"""
You are a CV content processor for TIMELINE COMPLETION ROLES (typically pre-2010). Same comprehensive input and anti-fabrication enforcement.

### PRIORITY CONSTRAINTS
**You can ONLY assign priorities 3, 4, or 5 to content in this chunk**
- Priority 3: Relevant early career achievements
- Priority 4: Professional foundation building
- Priority 5: Timeline completion only

### FOCUS AREAS
- Career foundation and early development
- Timeline continuity maintenance
- Basic professional competency demonstration
- Educational and training background

### OUTPUT FORMAT
Same structure as recent roles processor with:
- Timeline role focus
- Priority range 3-5
- Emphasis on foundation and continuity
- Anti-fabrication validation for all content

Chunk Data: {json.dumps(chunk)}
Global Context: {json.dumps(profile.get('global_context', {}))}
Job Description: {job_description}
Profile Context: {json.dumps(profile)}
"""
    else:
        prompt = f"""
You are a CV content processor. Process the provided chunk as per the instructions. Respond ONLY with a valid JSON object.
Chunk: {json.dumps(chunk)}
Profile: {json.dumps(profile)}
Job Description: {job_description}
"""
    try:
        logging.getLogger("arc_service").info(f"[OPENAI CHUNK PROMPT] {prompt}")
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

# --- Helper: Safe JSON parse with logging ---
def safe_json_parse(content, logger=None, context="OpenAI response"):
    try:
        return json.loads(content)
    except Exception as e:
        if logger:
            logger.error(f"[OPENAI JSON PARSE ERROR] {context}: {e}")
            logger.error(f"[OPENAI RAW RESPONSE] {content[:1000]}")
        return None

def assemble_unified_cv(chunk_results, global_context, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID):
    # Final assembly step using OpenAI
    assembly_prompt = """You are a CV reconstruction specialist. Take the raw content from multiple processed chunks and reconstruct it into a single, unified, professional CV with cover letter.

### INPUT DATA
You will receive:
- **Raw chunks:** Content from recent roles, supporting roles, and timeline roles
- **Global context:** Job analysis and alignment strategies
- **Original profile:** Complete candidate profile for validation
- **Job description:** Target job posting for final optimization

### RECONSTRUCTION REQUIREMENTS

**CONTENT CONSOLIDATION:**
- Merge all raw experience from chunks into chronological order (most recent first)
- Combine all achievements, removing duplicates while preserving unique value
- Consolidate skills from all chunks, prioritizing by job relevance
- Integrate education and certifications from original profile

**PRIORITY-BASED ORGANIZATION:**
- Priority 1 content: Featured prominently in summary and top achievements
- Priority 2-3 content: Main experience bullets and core competencies
- Priority 4-5 content: Supporting experience and timeline completion

**FINAL OPTIMIZATION:**
- Apply job-specific keyword optimization throughout
- Ensure natural keyword integration (avoid stuffing)
- Maintain UK English spelling and terminology
- Create cohesive narrative flow

**ANTI-FABRICATION VALIDATION:**
- Verify all content traces back to original profile chunks
- Ensure no skills or achievements are invented
- Maintain factual accuracy of all metrics and timelines
- Preserve authentic experience levels

### OUTPUT STRUCTURE

Generate a complete CV with these sections:
1. **Professional Summary** (2-3 lines, Priority 1 content)
2. **Key Achievements** (4-6 bullet points, Priority 1-2 content)
3. **Professional Experience** (chronological, all roles with prioritized bullets)
4. **Core Competencies** (skills organized by relevance)
5. **Education & Certifications** (from original profile)

### COVER LETTER REQUIREMENTS

Create a single, unified cover letter that:
- Uses only factual highlights from the candidate's profile
- Addresses the specific job requirements
- Demonstrates clear value proposition
- Maintains professional tone
- Length: 3-4 paragraphs maximum

### FINAL OUTPUT FORMAT

(see prompt collection for full JSON structure)

### RECONSTRUCTION VALIDATION CHECKLIST

Before finalizing, verify:
- ✓ All content traces to original profile chunks
- ✓ No fabricated skills, achievements, or experience
- ✓ Chronological order maintained in experience section
- ✓ Priority-based content organization applied
- ✓ Job keywords naturally integrated throughout
- ✓ UK English spelling and grammar used
- ✓ Professional tone and formatting consistent
- ✓ Cover letter uses only factual profile highlights
- ✓ Single unified CV (not multiple versions)
- ✓ All required sections included and properly formatted
"""
    user_message = json.dumps({
        "chunks": chunk_results,
        "global_context": global_context,
        "profile": profile,
        "job_description": job_description,
        "instructions": assembly_prompt
    })
    logger = logging.getLogger("arc_service")
    logger.info(f"[OPENAI ASSEMBLY PROMPT] {user_message}")
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
        logger.info(f"[OPENAI RAW ASSEMBLY RESPONSE] {content[:1000]}")
        content_json = safe_json_parse(content, logger, context="OpenAI assembly")
        if content_json is None:
            return {"error": "Failed to parse OpenAI assembly response as JSON. See logs for details."}
        return content_json
    except Exception as e:
        logger.error(f"[OPENAI ASSEMBLY ERROR] {e}")
        return {"error": f"Assembly OpenAI error: {e}"}

def update_cv_with_openai(current_cv, update_request, original_profile, job_description):
    # Determine which prompt to use based on the update_request
    update_request_lower = (update_request or "").lower()
    if any(word in update_request_lower for word in ["emphasis", "focus", "highlight"]):
        prompt = f'''
Adjust the emphasis in this CV based on the user request: "{update_request}"

Current CV: {json.dumps(current_cv)}
Original Profile: {json.dumps(original_profile)}

Rules:
- Only use content from the original profile
- Reorder and rephrase existing content to match the emphasis request
- Do not fabricate new achievements or skills
- Maintain factual accuracy
- Preserve the overall CV structure

Return the updated CV in the same JSON format.
'''
    elif any(word in update_request_lower for word in ["keyword", "optimiz", "ats"]):
        prompt = f'''
Optimize keywords in this CV based on: "{update_request}"

Current CV: {json.dumps(current_cv)}
Job Description: {job_description}

Rules:
- Use intelligent keyword substitution where factually supported
- Maintain all factual accuracy
- Focus on natural keyword integration
- Do not add skills not demonstrated in the original content

Return the updated CV with optimized keywords.
'''
    elif any(word in update_request_lower for word in ["length", "shorten", "expand", "longer", "shorter"]):
        prompt = f'''
Adjust the length of this CV based on: "{update_request}"

Current CV: {json.dumps(current_cv)}

Rules:
- If shortening: Remove lower priority content first
- If expanding: Add more detail to existing achievements
- Maintain factual accuracy
- Preserve the most important information

Return the length-adjusted CV.
'''
    else:
        # Default to emphasis adjustment if not clear
        prompt = f'''
Adjust the emphasis in this CV based on the user request: "{update_request}"

Current CV: {json.dumps(current_cv)}
Original Profile: {json.dumps(original_profile)}

Rules:
- Only use content from the original profile
- Reorder and rephrase existing content to match the emphasis request
- Do not fabricate new achievements or skills
- Maintain factual accuracy
- Preserve the overall CV structure

Return the updated CV in the same JSON format.
'''
    # Append the critical validation checklist
    prompt += '''\n\nCRITICAL VALIDATION CHECKLIST:\n- ✓ Job description used for keyword optimization throughout\n- ✓ All skills have evidence in original profile\n- ✓ All achievements traced to profile content\n- ✓ No exaggerated experience levels or capabilities\n- ✓ Single CV and single cover letter generated\n- ✓ Maximum job alignment within factual boundaries\n- ✓ Anti-fabrication compliance verified at every stage\n- ✓ 12-20 keywords extracted for comprehensive coverage\n- ✓ Realistic ATS scoring (0-100% range)\n- ✓ UK English maintained throughout\n'''
    try:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key not set")
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a CV update specialist. Respond ONLY with a valid JSON object."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logging.error(f"[OPENAI CV UPDATE ERROR] {e}")
        return {"error": f"CV update OpenAI error: {e}"}
