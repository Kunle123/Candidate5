# AI Service API Endpoints (Frontend Integration Guide)

All endpoints are **POST** and are available under the `/api/ai` prefix (e.g., `/api/ai/optimize-cv`).

---

## 1. Optimize CV

**Endpoint:**  
`POST /api/ai/optimize-cv`

**Request Body:**
```json
{
  "cv_id": "string",                // The ID of the CV to optimize
  "targets": [
    {
      "section": "string",          // e.g., "experience", "summary"
      "content": "string",          // The text to optimize
      "target_job": "string",       // (optional) Target job title
      "target_industry": "string",  // (optional) Target industry
      "tone": "string",             // (optional, default: "professional")
      "keywords": ["string"]        // (optional) List of keywords to include
    }
  ]
}
```

**Response:**
```json
{
  "cv_id": "string",
  "optimized_sections": [
    {
      "section": "string",
      "original_content": "string",
      "optimized_content": "string",
      "improvements": ["string"],
      "keywords_added": ["string"]
    }
  ],
  "timestamp": "ISO8601 datetime"
}
```

---

## 2. Generate Cover Letter

**Endpoint:**  
`POST /api/ai/generate-cover-letter`

**Request Body:**
```json
{
  "cv_id": "string",                // The ID of the CV to use
  "job_description": "string",      // The job description text
  "user_comments": "string",        // (optional) Additional comments
  "tone": "string",                 // (optional, default: "professional")
  "company_name": "string",         // (optional)
  "recipient_name": "string",       // (optional)
  "position_title": "string"        // (optional)
}
```

**Response:**
```json
{
  "cv_id": "string",
  "cover_letter": "string",         // The generated cover letter text
  "key_points": ["string"],         // Main points highlighted
  "keywords_used": ["string"],      // Keywords incorporated
  "timestamp": "ISO8601 datetime"
}
```

---

## 3. Extract Keywords

**Endpoint:**  
`POST /api/ai/keywords`

**Request Body:**
```json
{
  "text": "string"                  // The text to extract keywords from
}
```

**Response:**
```json
{
  "keywords": ["string"]            // List of extracted keywords
}
```

---

## 4. Analyze CV

**Endpoint:**  
`POST /api/ai/analyze`

**Request Body:**
```json
{
  "cv_id": "string",                // The ID of the CV to analyze
  "sections": ["string"]            // (optional) List of sections to analyze
}
```

**Response:**  
A detailed analysis object, including score, feedback, suggestions, strengths, weaknesses, industry fit, and keyword analysis.

---

## General Notes for Frontend Devs

- All endpoints require a valid JWT Bearer token in the `Authorization` header.
- All endpoints return JSON.
- Use the `/docs` endpoint on your deployed service for live Swagger/OpenAPI documentation and testing.
- If you need to pass raw CV content instead of `cv_id`, you may need to adjust the backend or coordinate with the backend team.

---

**If you need example fetch/axios code, or want to see a sample request/response for a specific endpoint, let me know!** 