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

# ===== 1. COMPREHENSIVE KEYWORD EXTRACTION PROMPT =====
KEYWORD_EXTRACTION_PROMPT = """
You are a job analysis and keyword extraction specialist. Analyze this job posting and extract both job metadata AND exactly 12-20 keywords for comprehensive ATS optimization.

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

### OUTPUT FORMAT

Respond ONLY with a valid JSON object matching this exact schema:
```json
{
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
  "keyword_priority": {
    "high": ["Oracle Database", "SQL Server", "Data Analysis", "5+ years experience"],
    "medium": ["Python", "AWS", "Project Management", "Leadership", "Financial Services"],
    "low": ["Communication", "Problem Solving", "Risk Management"]
  },
  "extraction_validation": {
    "job_metadata_extracted": true,
    "keywords_in_range": true,
    "categories_balanced": true
  }
}
```

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
"""

# ===== 2. GLOBAL CONTEXT CREATION PROMPT =====
GLOBAL_CONTEXT_PROMPT = """
You are a career analysis specialist. Analyze the provided career profile and job description to create global context standards for consistent, factually accurate CV generation.

### STRICT ANTI-FABRICATION POLICY
- NEVER invent information not present in the profile
- NEVER exaggerate experience levels or capabilities
- ONLY use data from the provided profile and job description
- Base all analysis on factual evidence from source materials
- Flag any gaps rather than fabricating solutions

### TASK: CREATE GLOBAL CONTEXT WITH JOB ALIGNMENT

**INPUT ANALYSIS:**
1. **Job Requirements Analysis:**
   - Extract explicit requirements (skills, experience, education)
   - Identify implicit requirements (soft skills, cultural fit)
   - Map GREEN keywords (exact matches in profile)
   - Map AMBER keywords (related/transferable skills in profile)
   - Identify RED keywords (missing from profile - do not fabricate)

2. **Profile Capability Inventory:**
   - Document demonstrated skills with evidence
   - Quantify experience levels factually
   - Identify transferable skills with clear rationale
   - Map achievements to potential job relevance
   - Note any gaps honestly

3. **Factual Alignment Strategy:**
   - Define safe keyword substitutions
   - Establish priority rankings based on evidence
   - Create content emphasis guidelines
   - Set boundaries for what can/cannot be claimed

### OUTPUT FORMAT (JSON):
```json
{
  "job_analysis": {
    "explicit_requirements": {
      "technical_skills": ["Oracle ERP", "Project Management"],
      "experience_years": "5+ years",
      "education": "Bachelor's degree",
      "certifications": ["PMP preferred"]
    },
    "implicit_requirements": {
      "soft_skills": ["Leadership", "Communication"],
      "cultural_fit": ["Innovation", "Collaboration"],
      "success_metrics": ["On-time delivery", "Budget management"]
    },
    "keyword_mapping": {
      "green_keywords": ["Oracle", "Database", "Team Leadership"],
      "amber_keywords": ["ERP", "Project Coordination"],
      "red_keywords": ["SAP", "Agile Certification"]
    }
  },
  "profile_inventory": {
    "demonstrated_skills": [
      {
        "skill": "Oracle Fusion",
        "evidence": "3 years experience, led implementation project",
        "proficiency_level": "advanced",
        "transferable_to": ["Oracle ERP"]
      }
    ],
    "quantified_achievements": [
      {
        "achievement": "Led Oracle implementation for 500+ users",
        "evidence_source": "Senior Developer role at Company X",
        "relevance_to_job": "high - demonstrates ERP implementation experience"
      }
    ],
    "experience_gaps": [
      {
        "missing_requirement": "SAP experience",
        "gap_severity": "high",
        "mitigation": "emphasize ERP principles and Oracle expertise"
      }
    ]
  },
  "alignment_strategy": {
    "safe_keyword_substitutions": [
      {
        "original": "Oracle Fusion",
        "optimized": "Oracle ERP (Fusion)",
        "rationale": "aligns with job terminology while maintaining accuracy"
      }
    ],
    "priority_definitions": {
      "priority_1": "Direct keyword matches with strong evidence - ALWAYS included in all CV lengths",
      "priority_2": "Transferable skills with clear rationale - Included in medium and long CVs",
      "priority_3": "Supporting experience relevant to role - Included in long CVs only",
      "priority_4": "General professional experience - Extended long CVs only",
      "priority_5": "Timeline completion only - Extended long CVs only"
    },
    "cv_length_control": {
      "short_cv": {
        "target_length": "1-2 pages",
        "priorities_included": [1],
        "content_focus": "Only highest priority job-aligned content",
        "experience_bullets": "2-3 per role maximum",
        "roles_included": "Recent 3-4 roles only",
        "achievements_section": "Top 3-4 achievements only"
      },
      "medium_cv": {
        "target_length": "2-3 pages", 
        "priorities_included": [1, 2],
        "content_focus": "High priority + strong transferable skills",
        "experience_bullets": "3-4 per role maximum",
        "roles_included": "Recent 5-6 roles",
        "achievements_section": "Top 5-6 achievements"
      },
      "long_cv": {
        "target_length": "3-4 pages",
        "priorities_included": [1, 2, 3],
        "content_focus": "Comprehensive career narrative",
        "experience_bullets": "4-5 per role maximum", 
        "roles_included": "All relevant roles",
        "achievements_section": "Top 6-8 achievements"
      },
      "extended_long_cv": {
        "target_length": "4+ pages",
        "priorities_included": [1, 2, 3, 4, 5],
        "content_focus": "Complete career history",
        "experience_bullets": "5-6 per role maximum",
        "roles_included": "Complete career timeline",
        "achievements_section": "Top 8-10 achievements"
      }
    },
    "content_boundaries": {
      "can_claim": ["skills with evidence", "achievements from profile"],
      "cannot_claim": ["missing certifications", "undemonstrated skills"],
      "must_avoid": ["fabricated metrics", "exaggerated experience levels"]
    }
  }
}
```
"""

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
- Apply safe substitutions from global context (e.g., "Oracle Fusion" → "Oracle ERP (Fusion)")
- Prioritize GREEN keywords (exact matches) over AMBER keywords (transferable)
- For RED keywords (missing), do not fabricate - focus on related strengths

**CONTENT PRIORITIZATION:**
- Priority 1: Direct job keyword matches with quantified achievements from profile
- Priority 2: Strong job alignment using transferable skills with evidence
- Priority 3: Supporting experience relevant to job requirements

### OUTPUT FORMAT (JSON):
```json
{
  "chunk_type": "recent_roles",
  "processing_validation": {
    "job_keywords_available": true,
    "profile_context_complete": true,
    "anti_fabrication_rules_applied": true
  },
  "raw_experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "dates": "Start Date - End Date",
      "location": "Location",
      "bullets": [
        {
          "content": "Led Oracle ERP (Fusion) implementation for 500+ users, improving financial processing efficiency by 40%",
          "priority": 1,
          "keywords_used": ["Oracle ERP", "implementation", "financial processing"],
          "evidence_source": "Original profile: Led Oracle Fusion upgrade for accounting team",
          "fabrication_check": "PASS - rephrased existing achievement with job-aligned terminology"
        }
      ]
    }
  ],
  "raw_achievements": [
    {
      "content": "Delivered Oracle ERP implementation 2 weeks ahead of schedule, resulting in £200K cost savings",
      "priority": 1,
      "source_role": "Company Name",
      "keywords_used": ["Oracle ERP", "project delivery", "cost savings"],
      "evidence_source": "Original profile achievement with job-aligned terminology",
      "fabrication_check": "PASS - factual achievement with optimized presentation"
    }
  ],
  "raw_skills": [
    {
      "skill": "Oracle ERP (Fusion)",
      "priority": 1,
      "evidence": "3 years hands-on experience, led major implementation",
      "proficiency": "Advanced",
      "job_alignment": "Direct match to job requirement"
    }
  ],
  "anti_fabrication_summary": {
    "skills_validated": "All skills traced to profile evidence",
    "achievements_validated": "All achievements based on original profile content",
    "experience_levels_accurate": "No exaggeration of years or responsibility",
    "keyword_substitutions_safe": "All substitutions factually supported"
  }
}
```
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

### OUTPUT FORMAT (JSON):
```json
{
  "chunk_type": "supporting_roles",
  "processing_validation": {
    "job_keywords_available": true,
    "profile_context_complete": true,
    "anti_fabrication_rules_applied": true
  },
  "raw_experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "dates": "Start Date - End Date",
      "location": "Location",
      "bullets": [
        {
          "content": "Demonstrated skill progression and career advancement in supporting roles.",
          "priority": 2,
          "keywords_used": ["Skill progression", "career advancement"],
          "evidence_source": "Original profile: Supporting role evidence",
          "fabrication_check": "PASS - supporting experience validated"
        }
      ]
    }
  ],
  "raw_achievements": [
    {
      "content": "Contributed to major project delivery as a supporting team member.",
      "priority": 2,
      "source_role": "Company Name",
      "keywords_used": ["project delivery", "team contribution"],
      "evidence_source": "Original profile achievement",
      "fabrication_check": "PASS - factual achievement with supporting role focus"
    }
  ],
  "raw_skills": [
    {
      "skill": "Supporting role skill",
      "priority": 2,
      "evidence": "Demonstrated in supporting roles",
      "proficiency": "Intermediate",
      "job_alignment": "Transferable skill relevant to job requirement"
    }
  ],
  "anti_fabrication_summary": {
    "skills_validated": "All skills traced to profile evidence",
    "achievements_validated": "All achievements based on original profile content",
    "experience_levels_accurate": "No exaggeration of years or responsibility",
    "keyword_substitutions_safe": "All substitutions factually supported"
  }
}
```
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

### OUTPUT FORMAT (JSON):
```json
{
  "chunk_type": "timeline_roles",
  "processing_validation": {
    "job_keywords_available": true,
    "profile_context_complete": true,
    "anti_fabrication_rules_applied": true
  },
  "raw_experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "dates": "Start Date - End Date",
      "location": "Location",
      "bullets": [
        {
          "content": "Demonstrated early career achievement or professional foundation.",
          "priority": 3,
          "keywords_used": ["early career", "foundation"],
          "evidence_source": "Original profile: Timeline role evidence",
          "fabrication_check": "PASS - timeline experience validated"
        }
      ]
    }
  ],
  "raw_achievements": [
    {
      "content": "Completed foundational training or early career milestone.",
      "priority": 3,
      "source_role": "Company Name",
      "keywords_used": ["training", "milestone"],
      "evidence_source": "Original profile achievement",
      "fabrication_check": "PASS - factual achievement with timeline focus"
    }
  ],
  "raw_skills": [
    {
      "skill": "Timeline role skill",
      "priority": 3,
      "evidence": "Demonstrated in early career roles",
      "proficiency": "Basic",
      "job_alignment": "Foundation skill relevant to job requirement"
    }
  ],
  "anti_fabrication_summary": {
    "skills_validated": "All skills traced to profile evidence",
    "achievements_validated": "All achievements based on original profile content",
    "experience_levels_accurate": "No exaggeration of years or responsibility",
    "keyword_substitutions_safe": "All substitutions factually supported"
  }
}
```
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
    assembly_prompt = """# ENHANCED PROMPTS FOR FULL USER PREFERENCE ALIGNMENT

## ENHANCED CV RECONSTRUCTION PROMPT (Updated)

You are a CV reconstruction specialist. Take the raw content from multiple processed chunks and reconstruct it into a single, unified, professional CV with cover letter that meets strict formatting and content requirements.

### CRITICAL JSON SCHEMA REQUIREMENTS

**ALL keys at every level MUST use lower_snake_case:**
- Top-level: cv, cover_letter, reconstruction_metadata, job_title, company_name
- CV sections: professional_summary, key_achievements, professional_experience, core_competencies, education, certifications
- Nested objects: content, priority, keywords_used, source_chunk, etc.
- NEVER use: CV, Cover Letter, Professional Summary, keywordsUsed, sourceChunk

**Required field validation before response:**
- Verify all required top-level fields present
- Confirm all nested objects use snake_case
- Validate JSON structure completeness

### UK ENGLISH REQUIREMENTS (Mandatory)

**Spelling Standards:**
- organisation (not organization), realise (not realize), colour (not color)
- specialise (not specialize), analyse (not analyze), centre (not center)
- programme (not program), licence (not license), defence (not defense)

**Terminology Standards:**
- CV (not resume), mobile (not cell phone), postcode (not zip code)
- university (not college), A-levels (not high school diploma)
- managing director (not CEO), finance director (not CFO)

**Date Formats:**
- "January 2023 - Present" or "Jan 2023 - Dec 2023"
- Never use MM/DD/YYYY format

### PRIORITY-BASED LENGTH CONTROL (Explicit)

**Short CV (1-2 pages) - Priority 1 ONLY:**
- Professional summary: 2 lines maximum
- Key achievements: Top 3-4 only (Priority 1)
- Experience bullets: 2-3 per role maximum
- Roles included: Recent 3-4 roles only
- Core competencies: Top 8-10 skills only

**Medium CV (2-3 pages) - Priority 1-2:**
- Professional summary: 2-3 lines
- Key achievements: Top 5-6 (Priority 1-2)
- Experience bullets: 3-4 per role maximum
- Roles included: Recent 5-6 roles
- Core competencies: 10-15 skills

**Long CV (3-4 pages) - Priority 1-3:**
- Professional summary: 3-4 lines
- Key achievements: Top 6-8 (Priority 1-3)
- Experience bullets: 4-5 per role maximum
- Roles included: All relevant roles
- Core competencies: 15-20 skills

**Extended Long CV (4+ pages) - Priority 1-5:**
- Professional summary: 4-5 lines
- Key achievements: Top 8-10 (all priorities)
- Experience bullets: 5-6 per role maximum
- Roles included: Complete career timeline
- Core competencies: 20+ skills

### COVER LETTER STRUCTURE (Mandatory 4-Paragraph Format)

**Paragraph 1 (Opening - 30-40 words):**
Express interest in specific position and company. Brief introduction of candidacy.

**Paragraph 2 (Key Achievements - 60-80 words):**
Highlight 2-3 most relevant achievements from profile that directly align with job requirements. Include quantified results where available.

**Paragraph 3 (Job Alignment - 50-70 words):**
Demonstrate specific understanding of role requirements and how candidate's experience addresses company needs. Show company research and cultural fit.

**Paragraph 4 (Closing - 20-30 words):**
Professional closing with call to action. Express enthusiasm for interview opportunity.

**Total word count: 160-220 words maximum**

### ANTI-FABRICATION VALIDATION (Enhanced)

**Content Traceability:**
Every achievement, skill, and experience claim must include evidence_source field pointing to original profile content. No exceptions.

**Fabrication Detection:**
- Skills not demonstrated in profile = FORBIDDEN
- Achievements not in original profile = FORBIDDEN
- Exaggerated metrics or timelines = FORBIDDEN
- Invented certifications or qualifications = FORBIDDEN

**Validation Process:**
1. Cross-reference every CV claim with original profile
2. Verify all quantified achievements exist in source
3. Confirm skill proficiency levels match demonstrated experience
4. Validate timeline accuracy and career progression logic

### FINAL OUTPUT SCHEMA (Mandatory Structure)

```json
{
  "cv": {
    "name": "Full Name",
    "contact": {
      "email": "email@domain.com",
      "mobile": "+44 XXXX XXXXXX",
      "location": "City, UK",
      "linkedin": "linkedin.com/in/profile"
    },
    "professional_summary": {
      "content": "2-5 lines based on target CV length",
      "keywords_included": ["keyword1", "keyword2"],
      "priority_level": 1
    },
    "key_achievements": [
      {
        "content": "Achievement with quantified results",
        "priority": 1,
        "source_chunk": "recent_roles",
        "evidence_source": "Original profile location",
        "keywords_used": ["keyword1", "keyword2"]
      }
    ],
    "professional_experience": [
      {
        "company": "Company Name",
        "title": "Job Title",
        "dates": "Jan 2020 - Present",
        "location": "City, UK",
        "bullets": [
          {
            "content": "Achievement or responsibility",
            "priority": 1,
            "keywords_used": ["keyword1"],
            "evidence_source": "Original profile reference"
          }
        ]
      }
    ],
    "core_competencies": {
      "technical_skills": [
        {
          "skill": "Skill Name",
          "proficiency": "Expert/Advanced/Intermediate",
          "priority": 1,
          "evidence_source": "Profile reference"
        }
      ],
      "functional_skills": [
        {
          "skill": "Skill Name",
          "proficiency": "Advanced",
          "priority": 2
        }
      ]
    },
    "education": [
      {
        "degree": "Degree Name",
        "institution": "University Name",
        "year": "2015",
        "classification": "First Class Honours",
        "relevant_modules": ["Module 1", "Module 2"]
      }
    ],
    "certifications": [
      {
        "name": "Certification Name",
        "issuer": "Issuing Organisation",
        "year": "2023",
        "status": "Active/Expired"
      }
    ]
  },
  "cover_letter": {
    "content": "Four-paragraph cover letter following mandatory structure",
    "word_count": 180,
    "paragraph_breakdown": {
      "opening": "Paragraph 1 content",
      "achievements": "Paragraph 2 content", 
      "alignment": "Paragraph 3 content",
      "closing": "Paragraph 4 content"
    },
    "keywords_naturally_included": ["keyword1", "keyword2"],
    "job_alignment_score": 87
  },
  "reconstruction_metadata": {
    "chunks_processed": 3,
    "total_content_items": 45,
    "priority_distribution": {
      "priority_1_items": 8,
      "priority_2_items": 12,
      "priority_3_items": 15,
      "priority_4_items": 7,
      "priority_5_items": 3
    },
    "duplicates_removed": 3,
    "keywords_optimized": 16,
    "uk_english_validated": true,
    "json_schema_validated": true,
    "anti_fabrication_compliance": "100% - all content traced to original profile"
  },
  "job_title": "Extracted from job description",
  "company_name": "Extracted from job description"
}
```

### PRE-RESPONSE VALIDATION CHECKLIST

Before returning response, verify:
- ✓ All keys use lower_snake_case (no exceptions)
- ✓ All required top-level fields present
- ✓ UK English spelling throughout
- ✓ Cover letter follows 4-paragraph structure
- ✓ Word count within 160-220 range
- ✓ Priority-based content inclusion matches target length
- ✓ All content traceable to original profile
- ✓ JSON structure valid and complete
- ✓ No fabricated skills, achievements, or experience
- ✓ Chronological order maintained

## ENHANCED UK ENGLISH VALIDATION PROMPT

Add this validation step to all prompts:

### UK ENGLISH COMPLIANCE CHECK

**Mandatory Spelling Corrections:**
- Check and correct: organization→organisation, realize→realise, analyze→analyse
- Verify: specialise, colour, centre, programme, licence, defence
- Validate: CV (not resume), mobile (not cell), postcode (not zip code)

**Professional Terminology:**
- Use: managing director (not CEO), finance director (not CFO)
- Use: university (not college), A-levels (not high school)
- Use: programme (for initiatives), program (for software only)

**Date and Number Formats:**
- Dates: "January 2023" or "Jan 2023 - Dec 2023"
- Phone: "+44 XXXX XXXXXX" format
- Currency: £ symbol before amountyes 
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

### OUTPUT FORMAT

Respond ONLY with a valid JSON object matching this exact schema:

```json
{
  "cv": {
    "name": "Full Name",
    "contact": {
      "email": "email@domain.com",
      "mobile": "+44 XXXX XXXXXX",
      "location": "City, UK",
      "linkedin": "linkedin.com/in/profile"
    },
    "professional_summary": {
      "content": "2-5 lines based on target CV length",
      "keywords_included": ["keyword1", "keyword2"],
      "priority_level": 1
    },
    "key_achievements": [
      {
        "content": "Achievement with quantified results",
        "priority": 1,
        "source_chunk": "recent_roles",
        "evidence_source": "Original profile location",
        "keywords_used": ["keyword1", "keyword2"]
      }
    ],
    "professional_experience": [
      {
        "company": "Company Name",
        "title": "Job Title",
        "dates": "Jan 2020 - Present",
        "location": "City, UK",
        "bullets": [
          {
            "content": "Achievement or responsibility",
            "priority": 1,
            "keywords_used": ["keyword1"],
            "evidence_source": "Original profile reference"
          }
        ]
      }
    ],
    "core_competencies": {
      "technical_skills": [
        {
          "skill": "Skill Name",
          "proficiency": "Expert/Advanced/Intermediate",
          "priority": 1,
          "evidence_source": "Profile reference"
        }
      ],
      "functional_skills": [
        {
          "skill": "Skill Name",
          "proficiency": "Advanced",
          "priority": 2
        }
      ]
    },
    "education": [
      {
        "degree": "Degree Name",
        "institution": "University Name",
        "year": "2015",
        "classification": "First Class Honours",
        "relevant_modules": ["Module 1", "Module 2"]
      }
    ],
    "certifications": [
      {
        "name": "Certification Name",
        "issuer": "Issuing Organisation",
        "year": "2023",
        "status": "Active/Expired"
      }
    ]
  },
  "cover_letter": {
    "content": "Four-paragraph cover letter following mandatory structure",
    "word_count": 180,
    "paragraph_breakdown": {
      "opening": "Paragraph 1 content",
      "achievements": "Paragraph 2 content", 
      "alignment": "Paragraph 3 content",
      "closing": "Paragraph 4 content"
    },
    "keywords_naturally_included": ["keyword1", "keyword2"],
    "job_alignment_score": 87
  },
  "reconstruction_metadata": {
    "chunks_processed": 3,
    "total_content_items": 45,
    "priority_distribution": {
      "priority_1_items": 8,
      "priority_2_items": 12,
      "priority_3_items": 15,
      "priority_4_items": 7,
      "priority_5_items": 3
    },
    "duplicates_removed": 3,
    "keywords_optimized": 16,
    "uk_english_validated": true,
    "json_schema_validated": true,
    "anti_fabrication_compliance": "100% - all content traced to original profile"
  },
  "job_title": "Extracted from job description",
  "company_name": "Extracted from job description"
}
```

### PRE-RESPONSE VALIDATION CHECKLIST

Before returning response, verify:
- ✓ All keys use lower_snake_case (no exceptions)
- ✓ All required top-level fields present
- ✓ UK English spelling throughout
- ✓ Cover letter follows 4-paragraph structure
- ✓ Word count within 160-220 range
- ✓ Priority-based content inclusion matches target length
- ✓ All content traceable to original profile
- ✓ JSON structure valid and complete
- ✓ No fabricated skills, achievements, or experience
- ✓ Chronological order maintained

## ENHANCED UK ENGLISH VALIDATION PROMPT

Add this validation step to all prompts:

### UK ENGLISH COMPLIANCE CHECK

**Mandatory Spelling Corrections:**
- Check and correct: organization→organisation, realize→realise, analyze→analyse
- Verify: specialise, colour, centre, programme, licence, defence
- Validate: CV (not resume), mobile (not cell), postcode (not zip code)

**Professional Terminology:**
- Use: managing director (not CEO), finance director (not CFO)
- Use: university (not college), A-levels (not high school)
- Use: programme (for initiatives), program (for software only)

**Date and Number Formats:**
- Dates: "January 2023" or "Jan 2023 - Dec 2023"
- Phone: "+44 XXXX XXXXXX" format
- Currency: £ symbol before amountyes 
"""
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
