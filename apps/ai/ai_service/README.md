# CandidateV AI Optimization Service

This service provides AI-powered CV analysis and optimization for the CandidateV application.

## Features

- **CV Analysis**: Analyze CV content to provide scores, feedback, and suggestions for improvement
- **CV Optimization**: Generate improved content for CV sections based on target jobs and industries
- **Keyword Integration**: Identify and incorporate relevant keywords to improve ATS matching

## Technologies

- FastAPI
- OpenAI GPT-4 API
- SpaCy for NLP processing
- NLTK for text analysis
- JWT authentication

## Setup and Installation

### Prerequisites

- Python 3.10+
- OpenAI API key
- Access to CV Service API

### Local Development

1. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install SpaCy model:
   ```
   python -m spacy download en_core_web_sm
   ```

4. Set environment variables:
   ```
   export OPENAI_API_KEY=your_openai_api_key
   export CV_SERVICE_URL=http://localhost:8002
   ```

5. Run the service:
   ```
   uvicorn main:app --reload --port 8004
   ```

### Production Deployment

For deployment on Railway:

1. Set the following environment variables in the Railway project:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `CV_SERVICE_URL`: URL of the CV service
   - `PORT`: Port for the service (default 8004)

2. The service will be automatically deployed with the Railway configuration in `railway.json`.

## API Endpoints

### Health Check

```
GET /api/health
```

Returns the health status of the service, including OpenAI API and CV Service connectivity.

### CV Analysis

```
POST /api/ai/analyze
```

Analyzes a CV and provides detailed feedback and suggestions.

Request body:
```json
{
  "cv_id": "uuid-of-cv",
  "sections": ["summary", "experience", "education"]  // Optional
}
```

### CV Optimization

```
POST /api/ai/optimize
```

Optimizes sections of a CV based on target job, industry, and keywords.

Request body:
```json
{
  "cv_id": "uuid-of-cv",
  "targets": [
    {
      "section": "summary",
      "content": "Current content...",
      "target_job": "Software Engineer",
      "target_industry": "Technology",
      "tone": "professional",
      "keywords": ["Python", "cloud", "leadership"]
    }
  ]
}
```

### Job Match

```
POST /api/ai/job-match
```

Calculate match score between a CV and job description.

Request body:
```json
{
  "cv_id": "uuid-of-cv",
  "job_description": "Full job description..."
}
```

### Job Match Analysis

```
POST /api/ai/job-match/analyze
```

Provide detailed analysis and optimization suggestions for a CV based on a job description.

Request body:
```json
{
  "cv_id": "uuid-of-cv",
  "job_description": "Full job description...",
  "detailed": true
}
```

## Authentication

All endpoints require a valid JWT token passed in the Authorization header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Rate Limiting

API calls to OpenAI are rate-limited to prevent excessive usage. Retry logic is implemented to handle temporary failures. 