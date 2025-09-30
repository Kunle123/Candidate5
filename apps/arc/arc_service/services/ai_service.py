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

import os
import json
PROMPT_DIR = os.path.join(os.path.dirname(__file__), "../prompts")

def load_prompt(filename):
    with open(os.path.join(PROMPT_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()

# ===== 1. COMPREHENSIVE KEYWORD EXTRACTION PROMPT =====
# KEYWORD_EXTRACTION_PROMPT = """
# You are a job analysis and keyword extraction specialist. Analyze this job posting and extract both job metadata AND exactly 12-20 keywords for comprehensive ATS optimization.

# ### JOB METADATA EXTRACTION (REQUIRED)

# **Extract the following information from the job description:**
# - **job_title:** The main job title being advertised (e.g., "Senior Software Developer", "Project Manager")
# - **company:** The company or organization name, if mentioned (use "Not specified" if not found)
# - **experience_level:** Required experience level (e.g., "Senior", "Mid-level", "Entry-level", "5+ years", "Executive")
# - **industry:** The industry or business sector (e.g., "Technology", "Financial Services", "Healthcare", "Manufacturing")

# ### KEYWORD EXTRACTION REQUIREMENTS

# **TOTAL TARGET: 12-20 keywords (no more, no less)**

# **CATEGORY DISTRIBUTION:**
# 1. **TECHNICAL SKILLS (4-6 keywords):**
#    - Software, tools, platforms, technologies
#    - Programming languages, frameworks
#    - Technical methodologies, certifications
#    - Systems, databases, cloud platforms

# 2. **FUNCTIONAL SKILLS (3-5 keywords):**
#    - Core job responsibilities and functions
#    - Business processes, analysis types
#    - Management or operational capabilities
#    - Industry-specific functions

# 3. **SOFT SKILLS (2-4 keywords):**
#    - Leadership, communication, teamwork
#    - Problem-solving, analytical thinking
#    - Project management, collaboration
#    - Adaptability, innovation

# 4. **INDUSTRY TERMS (2-4 keywords):**
#    - Sector-specific terminology
#    - Business domains, market segments
#    - Regulatory, compliance, or standards terms
#    - Company type or business model terms

# 5. **EXPERIENCE QUALIFIERS (1-3 keywords):**
#    - Years of experience requirements
#    - Seniority levels, team size
#    - Budget responsibility, scale indicators
#    - Geographic or scope qualifiers

# ### EXTRACTION GUIDELINES

# **PRIORITIZATION RULES:**
# - Keywords mentioned multiple times = higher priority
# - Keywords in job title or requirements section = higher priority
# - Specific technical terms = higher priority than generic terms
# - Measurable qualifications = higher priority

# **KEYWORD SELECTION CRITERIA:**
# - ✅ Terms a recruiter would search for in an ATS
# - ✅ Specific skills, tools, or qualifications
# - ✅ Industry-standard terminology
# - ✅ Measurable experience indicators
# - ❌ Generic words like "experience," "skills," "ability"
# - ❌ Common verbs like "manage," "develop," "work"
# - ❌ Overly broad terms like "technology," "business"

# ### OUTPUT FORMAT

# Respond ONLY with a valid JSON object matching this exact schema:
# ```json
# {
#   "job_title": "Senior Oracle Developer",
#   "company": "TechCorp Financial",
#   "experience_level": "Senior (5+ years)",
#   "industry": "Financial Services",
#   "technical_skills": ["Oracle Database", "SQL Server", "Python", "AWS", "Agile Methodology"],
#   "functional_skills": ["Data Analysis", "Project Management", "Business Intelligence", "Process Improvement"],
#   "soft_skills": ["Leadership", "Communication", "Problem Solving"],
#   "industry_terms": ["Financial Services", "Regulatory Compliance", "Risk Management"],
#   "experience_qualifiers": ["5+ years experience", "Team Leadership"],
#   "total_keywords": 16,
#   "keyword_priority": {
#     "high": ["Oracle Database", "SQL Server", "Data Analysis", "5+ years experience"],
#     "medium": ["Python", "AWS", "Project Management", "Leadership", "Financial Services"],
#     "low": ["Communication", "Problem Solving", "Risk Management"]
#   },
#   "extraction_validation": {
#     "job_metadata_extracted": true,
#     "keywords_in_range": true,
#     "categories_balanced": true
#   }
# }
# ```

# ### METADATA EXTRACTION GUIDELINES

# **Job Title Extraction:**
# - Look for phrases like "Job Title:", "Position:", "Role:", or titles in headers
# - Extract the most specific title mentioned (e.g., "Senior Software Developer" not just "Developer")
# - If multiple titles mentioned, use the primary/main one

# **Company Extraction:**
# - Look for company names, organization names, or "Company:" labels
# - Extract full company name if available
# - Use "Not specified" if no company name is found

# **Experience Level Extraction:**
# - Look for phrases like "X+ years", "Senior", "Junior", "Entry-level", "Executive"
# - Extract the most specific requirement (e.g., "5+ years" rather than just "experienced")
# - Combine seniority level with years if both present (e.g., "Senior (5+ years)")

# **Industry Extraction:**
# - Identify the business sector or industry context
# - Use standard industry terms (e.g., "Technology", "Financial Services", "Healthcare")
# - Infer from company type, job requirements, or explicit mentions
# """

# ===== 2. GLOBAL CONTEXT CREATION PROMPT =====
# GLOBAL_CONTEXT_PROMPT = """
# You are a career analysis specialist. Analyze the provided career profile and job description to create global context standards for consistent, factually accurate CV generation.

# ### STRICT ANTI-FABRICATION POLICY
# - NEVER invent information not present in the profile
# - NEVER exaggerate experience levels or capabilities
# - ONLY use data from the provided profile and job description
# - Base all analysis on factual evidence from source materials
# - Flag any gaps rather than fabricating solutions

# ### TASK: CREATE GLOBAL CONTEXT WITH JOB ALIGNMENT

# **INPUT ANALYSIS:**
# 1. **Job Requirements Analysis:**
#    - Extract explicit requirements (skills, experience, education)
#    - Identify implicit requirements (soft skills, cultural fit)
#    - Map GREEN keywords (exact matches in profile)
#    - Map AMBER keywords (related/transferable skills in profile)
#    - Identify RED keywords (missing from profile - do not fabricate)

# 2. **Profile Capability Inventory:**
#    - Document demonstrated skills with evidence
#    - Quantify experience levels factually
#    - Identify transferable skills with clear rationale
#    - Map achievements to potential job relevance
#    - Note any gaps honestly

# 3. **Factual Alignment Strategy:**
#    - Define safe keyword substitutions
#    - Establish priority rankings based on evidence
#    - Create content emphasis guidelines
#    - Set boundaries for what can/cannot be claimed

# ### OUTPUT FORMAT (JSON):
# ```json
# {
#   "job_analysis": {
#     "explicit_requirements": {
#       "technical_skills": ["Oracle ERP", "Project Management"],
#       "experience_years": "5+ years",
#       "education": "Bachelor's degree",
#       "certifications": ["PMP preferred"]
#     },
#     "implicit_requirements": {
#       "soft_skills": ["Leadership", "Communication"],
#       "cultural_fit": ["Innovation", "Collaboration"],
#       "success_metrics": ["On-time delivery", "Budget management"]
#     },
#     "keyword_mapping": {
#       "green_keywords": ["Oracle", "Database", "Team Leadership"],
#       "amber_keywords": ["ERP", "Project Coordination"],
#       "red_keywords": ["SAP", "Agile Certification"]
#     }
#   },
#   "profile_inventory": {
#     "demonstrated_skills": [
#       {
#         "skill": "Oracle Fusion",
#         "evidence": "3 years experience, led implementation project",
#         "proficiency_level": "advanced",
#         "transferable_to": ["Oracle ERP"]
#       }
#     ],
#     "quantified_achievements": [
#       {
#         "achievement": "Led Oracle implementation for 500+ users",
#         "evidence_source": "Senior Developer role at Company X",
#         "relevance_to_job": "high - demonstrates ERP implementation experience"
#       }
#     ],
#     "experience_gaps": [
#       {
#         "missing_requirement": "SAP experience",
#         "gap_severity": "high",
#         "mitigation": "emphasize ERP principles and Oracle expertise"
#       }
#     ]
#   },
#   "alignment_strategy": {
#     "safe_keyword_substitutions": [
#       {
#         "original": "Oracle Fusion",
#         "optimized": "Oracle ERP (Fusion)",
#         "rationale": "aligns with job terminology while maintaining accuracy"
#       }
#     ],
#     "priority_definitions": {
#       "priority_1": "Direct keyword matches with strong evidence - ALWAYS included in all CV lengths",
#       "priority_2": "Transferable skills with clear rationale - Included in medium and long CVs",
#       "priority_3": "Supporting experience relevant to role - Included in long CVs only",
#       "priority_4": "General professional experience - Extended long CVs only",
#       "priority_5": "Timeline completion only - Extended long CVs only"
#     },
#     "cv_length_control": {
#       "short_cv": {
#         "target_length": "1-2 pages",
#         "priorities_included": [1],
#         "content_focus": "Only highest priority job-aligned content",
#         "experience_bullets": "2-3 per role maximum",
#         "roles_included": "Recent 3-4 roles only",
#         "achievements_section": "Top 3-4 achievements only"
#       },
#       "medium_cv": {
#         "target_length": "2-3 pages", 
#         "priorities_included": [1, 2],
#         "content_focus": "High priority + strong transferable skills",
#         "experience_bullets": "3-4 per role maximum",
#         "roles_included": "Recent 5-6 roles",
#         "achievements_section": "Top 5-6 achievements"
#       },
#       "long_cv": {
#         "target_length": "3-4 pages",
#         "priorities_included": [1, 2, 3],
#         "content_focus": "Comprehensive career narrative",
#         "experience_bullets": "4-5 per role maximum", 
#         "roles_included": "All relevant roles",
#         "achievements_section": "Top 6-8 achievements"
#       },
#       "extended_long_cv": {
#         "target_length": "4+ pages",
#         "priorities_included": [1, 2, 3, 4, 5],
#         "content_focus": "Complete career history",
#         "experience_bullets": "5-6 per role maximum",
#         "roles_included": "Complete career timeline",
#         "achievements_section": "Top 8-10 achievements"
#       }
#     },
#     "content_boundaries": {
#       "can_claim": ["skills with evidence", "achievements from profile"],
#       "cannot_claim": ["missing certifications", "undemonstrated skills"],
#       "must_avoid": ["fabricated metrics", "exaggerated experience levels"]
#     }
#   }
# }
# """

async def extract_comprehensive_keywords(job_description):
    import openai
    import os
    import json
    prompt = load_prompt("keyword_extraction.txt")
    prompt = prompt + f"\n\nJob Description: {job_description}\n"
    try:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key not set")
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
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
    work_experience = profile.get("work_experience", [])
    chunk_count = strategy["chunkCount"]
    chunk_size = max(1, len(work_experience) // chunk_count)
    chunks = []
    for i in range(chunk_count):
        chunk_roles = work_experience[i*chunk_size:(i+1)*chunk_size]
        # Assign chunk_type based on position
        if i == 0:
            chunk_type = "recent_roles"
        elif i == chunk_count - 1 and chunk_count > 2:
            chunk_type = "timeline_roles"
        else:
            chunk_type = "supporting_roles"
        chunk = {
            "roles": chunk_roles,
            "profile": profile,
            "job_description": job_description,
            "chunk_type": chunk_type
        }
        chunks.append(chunk)
    return chunks

def process_chunk_with_openai(chunk, profile, job_description, OPENAI_API_KEY, OPENAI_ASSISTANT_ID):
    chunk_type = chunk.get("chunk_type") or chunk.get("type") or "recent_roles"
    if chunk_type == "recent_roles":
        prompt = load_prompt("chunk_recent_roles.txt")
    elif chunk_type == "supporting_roles":
        prompt = load_prompt("chunk_supporting_roles.txt")
    elif chunk_type == "timeline_roles":
        prompt = load_prompt("chunk_timeline_roles.txt")
    else:
        prompt = load_prompt("chunk_supporting_roles.txt")
    try:
        logging.getLogger("arc_service").info(f"[OPENAI CHUNK PROMPT] {prompt}")
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
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
    assembly_prompt = load_prompt("cv_assembly.txt")
    def size(obj):
        if isinstance(obj, str):
            return len(obj.encode("utf-8"))
        return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    logger = logging.getLogger("arc_service")
    logger.info(f"[PAYLOAD SECTION SIZES] chunks: {size(chunk_results)} bytes, global_context: {size(global_context)} bytes, profile: {size(profile)} bytes, job_description: {size(job_description)} bytes, instructions: {size(assembly_prompt)} bytes")
    user_message = json.dumps({
        "chunks": chunk_results,
        "global_context": global_context,
        "profile": profile,
        "job_description": job_description,
        "instructions": assembly_prompt
    })
    logger.info(f"[OPENAI ASSEMBLY PROMPT] {user_message}")
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
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
    update_request_lower = (update_request or "").lower()
    if any(word in update_request_lower for word in ["emphasis", "focus", "highlight"]):
        prompt = load_prompt("cv_update_emphasis.txt")
    elif any(word in update_request_lower for word in ["keyword", "optimise", "optimize"]):
        prompt = load_prompt("cv_update_keyword.txt")
    elif any(word in update_request_lower for word in ["length", "shorten", "expand"]):
        prompt = load_prompt("cv_update_length.txt")
    else:
        prompt = "Update the CV as per the user request. Respond ONLY with a valid JSON object.\n" + \
                 f"Current CV: {json.dumps(current_cv)}\nOriginal Profile: {json.dumps(original_profile)}\nJob Description: {job_description}\nUpdate Request: {update_request}\n"
    try:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OpenAI API key not set")
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
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
