import openai
import os
import time
import json

class CVAssistantManager:
    def __init__(self):
        self.client = openai.OpenAI()
        self.assistant_id = os.getenv("OPENAI_CV_ASSISTANT_ID")
        if not self.assistant_id:
            raise Exception("OPENAI_CV_ASSISTANT_ID not set in environment variables.")

    def _get_parsing_instructions(self) -> str:
        return """
You are a professional CV/resume parser specialized in extracting structured information from CVs and resumes. When provided with CV content, extract and return a comprehensive JSON structure containing all relevant professional information.

EXTRACTION GUIDELINES:
1. WORK EXPERIENCE: Extract all work experiences in reverse chronological order, group by company and date range, break descriptions into individual bullet points, extract skills mentioned for each role, standardize dates to "MMM YYYY" format.
2. EDUCATION: Extract all education entries with complete details, format descriptions as bullet point arrays.
3. SKILLS & CERTIFICATIONS: Create comprehensive skills list, extract all certifications with issuer and dates.
4. PERSONAL INFORMATION: Extract contact details, name, location, professional summary, LinkedIn, portfolio links.

OUTPUT FORMAT: Return ONLY a valid JSON object using this exact schema:
{
  "personal_info": {"name": "string", "email": "string", "phone": "string", "location": "string", "linkedin": "string", "portfolio": "string", "summary": "string"},
  "work_experience": [{"id": "string", "company": "string", "title": "string", "start_date": "string", "end_date": "string", "location": "string", "description": ["bullet 1", "bullet 2"], "skills": ["skill1", "skill2"]}],
  "education": [{"id": "string", "institution": "string", "degree": "string", "field": "string", "start_date": "string", "end_date": "string", "location": "string", "description": ["achievement 1", "achievement 2"]}],
  "skills": ["Python", "JavaScript", "AWS"],
  "projects": [{"id": "string", "name": "string", "date": "string", "description": ["objective", "technology used", "outcome"], "technologies": ["React", "Node.js"]}],
  "certifications": [{"id": "string", "name": "string", "issuer": "string", "year": "string", "expiry": "string"}],
  "languages": [{"language": "string", "proficiency": "string"}]
}

CRITICAL REQUIREMENTS:
- Return ONLY the JSON object, no explanatory text
- No markdown formatting or code blocks
- Proper JSON syntax with double quotes
- Generate unique IDs using key identifiers
- Empty arrays for missing sections
- Consistent date formatting throughout
"""

    def process_cv(self, cv_text: str) -> dict:
        thread = self.client.beta.threads.create()
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=f"Please parse this CV:\n\n{cv_text}"
        )
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant_id
        )
        # Wait for completion
        while run.status in ['queued', 'in_progress']:
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
        if run.status == 'completed':
            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id
            )
            response_content = messages.data[0].content[0].text.value
            print("RAW ASSISTANT RESPONSE:", response_content)
            import logging
            logging.getLogger().info(f"RAW ASSISTANT RESPONSE: {response_content}")
            try:
                return json.loads(response_content)
            except Exception as e:
                logging.getLogger().error(f"JSON decode error: {e}")
                logging.getLogger().error(f"RAW ASSISTANT RESPONSE: {response_content}")
                raise Exception(f"Assistant returned invalid JSON: {response_content}")
        else:
            raise Exception(f"Assistant processing failed: {run.status}")
