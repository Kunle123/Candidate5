# Career Ark (Arc) API Endpoints Reference

This document describes the backend API endpoints for the Career Ark (Arc) feature. It is intended for backend developers and integrators.

---

## Authentication
All endpoints require a valid Bearer token in the `Authorization` header:
```
Authorization: Bearer <token>
```

---

## Endpoints

### 1. Upload CV
- **URL:** `/api/arc/cv`
- **Method:** `POST`
- **Description:** Upload a CV file for processing and extraction.
- **Headers:**
  - `Authorization: Bearer <token>`
  - `Content-Type: multipart/form-data`
- **Request Body:**
  - `file`: CV file (PDF, DOC, DOCX)
- **Response:**
```json
{
  "taskId": "string" // Unique ID for processing task
}
```
- **Notes:**
  - Returns a `taskId` for polling status.

---

### 2. Poll CV Processing Status
- **URL:** `/api/arc/cv/status/:taskId`
- **Method:** `GET`
- **Description:** Get the status of a CV processing task.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
```json
{
  "status": "pending" | "completed" | "failed",
  "extractedDataSummary"?: {
    "workExperienceCount": number,
    "skillsFound": number
  },
  "error"?: "string"
}
```
- **Notes:**
  - When `status` is `completed`, `extractedDataSummary` is present.
  - When `status` is `failed`, `error` may be present.

---

### 3. (Planned) Arc Data Management
- **URL:** `/api/arc/data`
- **Method:** `GET`, `PUT`, `POST`
- **Description:**
  - `GET`: Retrieve user's Arc profile data (skills, experience, etc.)
  - `PUT`/`POST`: Update or add to Arc profile data
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request/Response:**
  - To be defined as feature is implemented

---

### 4. (Planned) Generate Application Materials
- **URL:** `/api/arc/generate`
- **Method:** `POST`
- **Description:** Generate tailored CV and cover letter from Arc data and job advert
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:**
```json
{
  "jobAdvert": "string",
  "arcData": { /* user's Arc profile data */ }
}
```
- **Response:**
```json
{
  "cv": "string", // generated CV (text or file link)
  "coverLetter": "string" // generated cover letter
}
```
- **Notes:**
  - Details may change as feature is implemented

---

## Integration Notes
- All endpoints are under `/api/arc` and require authentication.
- CV upload is asynchronous; use `taskId` to poll for status.
- Future endpoints will support Arc data management and application generation.
- Error responses should use standard HTTP status codes and include a JSON body with an `error` field.

---

## Example Error Response
```json
{
  "error": "Invalid file format. Only PDF, DOC, DOCX allowed."
}
```

---

## Contact
For questions or updates, contact the backend/API lead or check the latest API documentation. 