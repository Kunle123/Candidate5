# Current CV Import Architecture Analysis

## Overview
Based on the repository analysis and user-provided information, the current CV import system uses a two-pass AI processing approach with the following architecture:

## Frontend Implementation (C5Frontend)
**Repository:** https://github.com/Kunle123/C5Frontend

### Key Components:
- **Main UI:** `src/pages/CareerArk.tsx` - Contains the CV import interface
- **File Handler:** `handleFileChange` function manages file upload process
- **API Integration:** Custom XMLHttpRequest implementation for progress tracking
- **File Support:** PDF, DOC, DOCX formats

### Current Flow:
1. User clicks "Import a CV" button (triggers hidden file input)
2. File selection triggers `handleFileChange` function
3. File uploaded via POST request to `/api/career-ark/cv`
4. Returns `taskId` for polling extraction status
5. Frontend polls for completion status

## Backend Implementation (Candidate5)
**Repository:** https://github.com/Kunle123/Candidate5

### Architecture:
- **Microservices-based:** Python backend with multiple services
- **Main Service:** `apps/arc/arc_service/` (CareerArk service)
- **Database:** PostgreSQL with UUID-based models
- **AI Processing:** Two-pass extraction system

### Key Files:
- `career_ark_router.py` - API endpoints and routing
- `ai_utils.py` - Two-pass AI processing logic (contains the code from original prompt)
- `cv_utils.py` - CV file processing utilities
- `career_ark_models.py` - Database models
- `arc_schemas.py` - API request/response schemas

### Two-Pass AI Processing:
**First Pass:** Metadata extraction only
- Extracts basic information (job titles, companies, dates)
- Uses `extract_cv_metadata_with_ai()` function
- Returns structured metadata without descriptions

**Second Pass:** Detailed description extraction
- Processes each work experience individually
- Uses `extract_work_experience_description_with_ai()` function
- Extracts full descriptions and skills for each role
- Combines with metadata from first pass

## Current API Endpoint
**Endpoint:** `POST /api/career-ark/cv`
**Authentication:** Bearer token in Authorization header
**Response:** `{"taskId": "uuid"}` for polling status

## Integration Points
1. **File Upload:** CareerArk.tsx → API Gateway → Arc Service
2. **AI Processing:** Arc Service → OpenAI API (GPT-4o-2024-08-06)
3. **Database Storage:** Processed data stored in PostgreSQL
4. **Status Polling:** Frontend polls for completion status
5. **Result Retrieval:** Structured CV data returned to frontend

## Current Strengths
- **Reliable Processing:** Two-pass approach ensures comprehensive data extraction
- **Progress Tracking:** Real-time upload progress and status polling
- **Structured Output:** Consistent JSON schema for CV data
- **File Format Support:** Handles multiple document formats
- **Error Handling:** Robust error handling and logging

## Current Limitations
- **Complex Architecture:** Multiple API calls and polling required
- **Processing Time:** Two separate AI calls increase latency
- **Resource Usage:** Higher token consumption due to duplicate processing
- **Maintenance Overhead:** Custom polling and status management logic

