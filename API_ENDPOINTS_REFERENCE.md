# API Endpoints Reference — Frontend Integration

This document describes all **non-auth API endpoints** (AI, CV, and Payments) as called by the frontend. Backend developers must ensure their implementation matches these specifications **exactly**—including URL paths, HTTP methods, request/response structure, and authentication. All requests are routed through the API Gateway.

---

## Base URL (API Gateway)

```
https://api-gw-production.up.railway.app
```

All endpoints below are relative to this base URL.

---

## 1. AI Service Endpoints

**Base:** `/api/ai`

### a. Extract Keywords
- **POST** `/api/ai/keywords`
- **Headers:**
  - `Authorization: Bearer <JWT>`
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  { "text": "string" }
  ```
- **Response:**
  ```json
  { "keywords": ["string", ...] }
  ```

### b. Analyze CV
- **POST** `/api/ai/analyze`
- **Headers:**
  - `Authorization: Bearer <JWT>`
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  { "cv_id": "string", "sections": ["string"] (optional) }
  ```
- **Response:**
  - JSON object with analysis results (score, feedback, suggestions, etc.)

### c. Optimize CV
- **POST** `/api/ai/optimize-cv`
- **Headers:**
  - `Authorization: Bearer <JWT>`
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "cv_id": "string",
    "targets": [
      {
        "section": "string",
        "content": "string",
        "target_job": "string",
        "tone": "string",
        "keywords": ["string"]
      }
    ]
  }
  ```
- **Response:**
  - JSON object with optimized CV sections and metadata

### d. Generate Cover Letter
- **POST** `/api/ai/generate-cover-letter`
- **Headers:**
  - `Authorization: Bearer <JWT>`
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "cv_id": "string",
    "job_description": "string",
    "user_comments": "string",
    "tone": "string",
    "company_name": "string",
    "recipient_name": "string",
    "position_title": "string"
  }
  ```
- **Response:**
  - JSON object with generated cover letter and key points

---

## 2. CV Service Endpoints

**Base:** `/cvs`

### a. List User's CVs
- **GET** `/cvs`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - Array of CV objects (each with `id`, `filename` or `name`, `content`, etc.)

### b. Upload New CV
- **POST** `/cvs`
- **Headers:**
  - `Authorization: Bearer <JWT>`
  - `Content-Type: multipart/form-data`
- **Body:**
  - FormData with a `file` field
- **Response:**
  - New CV object

### c. Get CV Details
- **GET** `/cvs/{cvId}`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - CV object

### d. Update CV
- **PUT** `/cvs/{cvId}`
- **Headers:**
  - `Authorization: Bearer <JWT>`
  - `Content-Type: application/json`
- **Request Body:**
  - JSON with updated CV fields
- **Response:**
  - Updated CV object

### e. Delete CV
- **DELETE** `/cvs/{cvId}`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - Success message

### f. Analyze CV for Keywords
- **POST** `/cvs/{cvId}/analyze`
- **Headers:**
  - `Authorization: Bearer <JWT>`
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  { "jobDescription": "string" }
  ```
- **Response:**
  - JSON object with missing keywords, etc.

### g. Download CV
- **GET** `/cvs/{cvId}/download`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - File download (JSON, PDF, or DOCX)

---

## 3. Payments Service Endpoints

**Base:** `/api/payments`

### a. Get Payment Methods
- **GET** `/api/payments/methods/{userId}`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - Array of payment method objects

### b. Add Payment Method
- **POST** `/api/payments/methods/add`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - New payment method object

### c. Delete Payment Method
- **DELETE** `/api/payments/methods/{paymentMethodId}`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - Success message

### d. Set Default Payment Method
- **POST** `/api/payments/methods/{paymentMethodId}/default`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - Updated payment method object

### e. Get Payment History
- **GET** `/api/payments/history/{userId}`
- **Headers:**
  - `Authorization: Bearer <JWT>`
- **Response:**
  - Array of payment history objects

---

## General Notes

- **Authentication:** All endpoints require a valid JWT Bearer token in the `Authorization` header.
- **Routing:** All requests must go through the API Gateway (`https://api-gw-production.up.railway.app`).
- **CORS:** The gateway must allow requests from the frontend origin (e.g., `http://localhost:5173` for local dev).
- **No deviation:** Backend endpoints, request/response structure, and authentication must match this document exactly for seamless frontend integration.

---

**For questions or updates, coordinate with the frontend team to avoid breaking changes.** 