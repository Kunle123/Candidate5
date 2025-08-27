# Implementation Recommendations for OpenAI Assistants Migration

## Overview
Based on the analysis of the current two-pass CV import system, this document provides detailed implementation recommendations for migrating to OpenAI Assistants while maintaining functionality and improving performance.

## Current System Analysis

### Frontend Implementation (CareerArk.tsx)
- **File Upload:** `handleFileChange` function handles file selection and upload
- **Progress Tracking:** Custom XMLHttpRequest implementation for upload progress
- **Polling Logic:** Frontend polls status endpoint using returned `taskId`
- **File Support:** PDF, DOC, DOCX formats supported

### Backend Implementation (Arc Service)
- **Endpoint:** `POST /api/career-ark/cv` in `career_ark_router.py`
- **File Processing:** Temporary file storage and text extraction
- **Task Management:** Asynchronous processing with unique `taskId`
- **Two-Pass AI:** Metadata extraction followed by detailed description extraction
- **Status Polling:** `GET /api/career-ark/cv/status?taskId=...` endpoint

## Migration Implementation Plan

### Phase 1: OpenAI Assistant Setup

#### 1.1 Create Assistant
```python
# New file: apps/arc/arc_service/assistant_manager.py
import openai
from typing import Dict, Any

class CVAssistantManager:
    def __init__(self):
        self.client = openai.OpenAI()
        self.assistant_id = os.getenv("OPENAI_CV_ASSISTANT_ID")
    
    def create_assistant(self) -> str:
        """Create CV parsing assistant with optimized instructions"""
        assistant = self.client.beta.assistants.create(
            name="CV Parser Pro",
            instructions=self._get_parsing_instructions(),
            model="gpt-4o",
            tools=[]
        )
        return assistant.id
    
    def _get_parsing_instructions(self) -> str:
        """Return comprehensive CV parsing instructions"""
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

    def process_cv(self, cv_text: str) -> Dict[str, Any]:
        """Process CV text using the assistant"""
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
            return json.loads(response_content)
        else:
            raise Exception(f"Assistant processing failed: {run.status}")
```

#### 1.2 Environment Configuration
```bash
# Add to .env files
OPENAI_CV_ASSISTANT_ID=asst_your_assistant_id_here
```

### Phase 2: Backend Integration

#### 2.1 New Assistant Endpoint
```python
# Modify: apps/arc/arc_service/career_ark_router.py
from .assistant_manager import CVAssistantManager

@router.post("/cv/assistant")
async def upload_cv_assistant(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """New endpoint using OpenAI Assistant for CV processing"""
    try:
        # Validate file type
        if not file.filename.lower().endswith(('.pdf', '.doc', '.docx')):
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Extract text from file
        cv_text = await extract_text_from_file(file)
        
        # Process with assistant
        assistant = CVAssistantManager()
        parsed_data = assistant.process_cv(cv_text)
        
        # Save to database
        cv_record = await save_cv_data(parsed_data, current_user.id, file.filename)
        
        # Return structured data directly (no polling needed)
        return {
            "success": True,
            "cv_id": cv_record.id,
            "data": parsed_data
        }
        
    except Exception as e:
        logger.error(f"CV processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="CV processing failed")

# Keep existing endpoint for backward compatibility
@router.post("/cv")
async def upload_cv_legacy(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Legacy endpoint with two-pass processing"""
    # Existing implementation remains unchanged
    pass
```

#### 2.2 Feature Flag Implementation
```python
# New file: apps/arc/arc_service/feature_flags.py
import os
from typing import Dict, Any

class FeatureFlags:
    @staticmethod
    def use_assistant_processing() -> bool:
        """Check if assistant processing should be used"""
        return os.getenv("USE_ASSISTANT_CV_PROCESSING", "false").lower() == "true"
    
    @staticmethod
    def get_processing_config() -> Dict[str, Any]:
        """Get processing configuration"""
        return {
            "use_assistant": FeatureFlags.use_assistant_processing(),
            "fallback_enabled": os.getenv("ENABLE_FALLBACK", "true").lower() == "true",
            "max_retries": int(os.getenv("ASSISTANT_MAX_RETRIES", "3"))
        }
```

### Phase 3: Frontend Updates

#### 3.1 Update CareerArk.tsx
```typescript
// Modify: src/pages/CareerArk.tsx
const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
  const file = event.target.files?.[0];
  if (!file) return;

  setIsUploading(true);
  setUploadProgress(0);

  try {
    // Check feature flag for assistant processing
    const useAssistant = await checkAssistantFeatureFlag();
    
    if (useAssistant) {
      // New assistant-based processing (direct response)
      const result = await uploadCVWithAssistant(file, (progress) => {
        setUploadProgress(progress);
      });
      
      // Process result directly (no polling needed)
      handleCVProcessingComplete(result.data);
      
    } else {
      // Legacy two-pass processing with polling
      const { taskId } = await uploadCVLegacy(file, (progress) => {
        setUploadProgress(progress);
      });
      
      // Start polling for results
      pollForResults(taskId);
    }
    
  } catch (error) {
    console.error('CV upload failed:', error);
    setError('Failed to process CV. Please try again.');
  } finally {
    setIsUploading(false);
  }
};

const uploadCVWithAssistant = async (
  file: File, 
  onProgress: (progress: number) => void
): Promise<any> => {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const progress = (e.loaded / e.total) * 100;
        onProgress(progress);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        const response = JSON.parse(xhr.responseText);
        resolve(response);
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`));
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed'));
    });

    xhr.open('POST', '/api/career-ark/cv/assistant');
    xhr.setRequestHeader('Authorization', `Bearer ${getAuthToken()}`);
    xhr.send(formData);
  });
};

const checkAssistantFeatureFlag = async (): Promise<boolean> => {
  try {
    const response = await fetch('/api/career-ark/feature-flags');
    const flags = await response.json();
    return flags.use_assistant_processing;
  } catch {
    return false; // Default to legacy processing if flag check fails
  }
};
```

#### 3.2 API Integration Updates
```typescript
// Modify: src/api/careerArkApi.ts
export const uploadCVAssistant = async (file: File): Promise<CVProcessingResult> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch('/api/career-ark/cv/assistant', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`
    },
    body: formData
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status}`);
  }

  return response.json();
};

export const getFeatureFlags = async (): Promise<FeatureFlags> => {
  const response = await fetch('/api/career-ark/feature-flags', {
    headers: {
      'Authorization': `Bearer ${getAuthToken()}`
    }
  });

  if (!response.ok) {
    throw new Error('Failed to fetch feature flags');
  }

  return response.json();
};
```

### Phase 4: Migration Strategy

#### 4.1 Gradual Rollout Plan
```python
# Environment-based rollout configuration
# Development: USE_ASSISTANT_CV_PROCESSING=true
# Staging: USE_ASSISTANT_CV_PROCESSING=true  
# Production: Start with false, gradually enable for user segments

class UserSegmentManager:
    @staticmethod
    def should_use_assistant(user_id: str) -> bool:
        """Determine if user should use assistant processing"""
        if os.getenv("ASSISTANT_ROLLOUT_PERCENTAGE", "0") == "100":
            return True
        
        # Gradual rollout based on user ID hash
        rollout_percentage = int(os.getenv("ASSISTANT_ROLLOUT_PERCENTAGE", "0"))
        user_hash = hash(user_id) % 100
        return user_hash < rollout_percentage
```

#### 4.2 Monitoring and Fallback
```python
# Enhanced error handling with fallback
@router.post("/cv/assistant")
async def upload_cv_assistant_with_fallback(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Assistant processing with automatic fallback"""
    try:
        # Try assistant processing first
        assistant = CVAssistantManager()
        parsed_data = assistant.process_cv(cv_text)
        
        # Log success metrics
        logger.info(f"Assistant processing successful for user {current_user.id}")
        
        return {"success": True, "data": parsed_data, "method": "assistant"}
        
    except Exception as e:
        logger.error(f"Assistant processing failed: {str(e)}")
        
        # Fallback to legacy processing
        if FeatureFlags.get_processing_config()["fallback_enabled"]:
            logger.info(f"Falling back to legacy processing for user {current_user.id}")
            return await process_cv_legacy(file, current_user)
        else:
            raise HTTPException(status_code=500, detail="CV processing failed")
```

## Testing Strategy

### Unit Tests
```python
# tests/test_assistant_processing.py
import pytest
from apps.arc.arc_service.assistant_manager import CVAssistantManager

class TestCVAssistantManager:
    def test_cv_processing_success(self):
        """Test successful CV processing"""
        manager = CVAssistantManager()
        sample_cv = "John Doe\nSoftware Engineer\n..."
        
        result = manager.process_cv(sample_cv)
        
        assert "personal_info" in result
        assert "work_experience" in result
        assert result["personal_info"]["name"] == "John Doe"

    def test_cv_processing_error_handling(self):
        """Test error handling in CV processing"""
        manager = CVAssistantManager()
        
        with pytest.raises(Exception):
            manager.process_cv("")  # Empty CV should fail
```

### Integration Tests
```python
# tests/test_cv_endpoints.py
import pytest
from fastapi.testclient import TestClient

def test_assistant_endpoint_success(client: TestClient):
    """Test assistant endpoint with valid CV"""
    with open("test_cv.pdf", "rb") as f:
        response = client.post(
            "/api/career-ark/cv/assistant",
            files={"file": ("test_cv.pdf", f, "application/pdf")},
            headers={"Authorization": "Bearer test_token"}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data

def test_fallback_mechanism(client: TestClient):
    """Test fallback to legacy processing"""
    # Mock assistant failure
    with patch('apps.arc.arc_service.assistant_manager.CVAssistantManager.process_cv') as mock_process:
        mock_process.side_effect = Exception("Assistant failed")
        
        with open("test_cv.pdf", "rb") as f:
            response = client.post(
                "/api/career-ark/cv/assistant",
                files={"file": ("test_cv.pdf", f, "application/pdf")},
                headers={"Authorization": "Bearer test_token"}
            )
        
        # Should fallback successfully
        assert response.status_code == 200
```

## Performance Monitoring

### Metrics to Track
```python
# apps/arc/arc_service/metrics.py
import time
import logging
from typing import Dict, Any

class ProcessingMetrics:
    @staticmethod
    def log_processing_time(method: str, duration: float, user_id: str):
        """Log processing time for analysis"""
        logger.info(f"CV_PROCESSING_TIME method={method} duration={duration:.2f}s user_id={user_id}")
    
    @staticmethod
    def log_processing_success(method: str, user_id: str, token_usage: int = None):
        """Log successful processing"""
        metrics = f"CV_PROCESSING_SUCCESS method={method} user_id={user_id}"
        if token_usage:
            metrics += f" tokens={token_usage}"
        logger.info(metrics)
    
    @staticmethod
    def log_processing_failure(method: str, error: str, user_id: str):
        """Log processing failure"""
        logger.error(f"CV_PROCESSING_FAILURE method={method} error={error} user_id={user_id}")
```

## Deployment Checklist

### Pre-Deployment
- [ ] Create OpenAI Assistant and obtain ID
- [ ] Update environment variables
- [ ] Deploy backend changes with feature flag disabled
- [ ] Run integration tests
- [ ] Verify fallback mechanism works

### Deployment
- [ ] Deploy frontend changes
- [ ] Enable feature flag for small user segment (5%)
- [ ] Monitor error rates and performance
- [ ] Gradually increase rollout percentage
- [ ] Monitor token usage and costs

### Post-Deployment
- [ ] Compare processing times (expect 50-70% improvement)
- [ ] Verify data quality matches legacy system
- [ ] Monitor user feedback
- [ ] Remove legacy code after successful migration

This comprehensive implementation plan provides a safe, gradual migration path to OpenAI Assistants while maintaining system reliability and user experience.

