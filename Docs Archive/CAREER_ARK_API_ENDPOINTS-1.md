# Career Ark (Arc) API Endpoints Reference

This document describes the backend API endpoints for the Career Ark (Arc) feature. It is intended for backend developers and integrators.

---

## Authentication
All endpoints require a valid Bearer token in the `Authorization` header:
```
Authorization: Bearer <token>
```

---

## Data Uniqueness & Deduplication

All Arc data must be unique and consolidated for each user. When new data is extracted from a CV or added manually, the backend must:
- **Detect potential duplicates** using key field matching, fuzzy matching, date overlap, and semantic similarity (AI-assisted if needed).
- **Merge** new details into existing entries if a match is found (e.g., add a new achievement to an existing role, but only if it is not already present semantically).
- **Add** as a new entry only if no match is found.
- **No raw CV file storage**: Only structured data is stored; raw files are deleted after processing.
- **Atomicity**: All deduplication and merging operations for a single CV or user action must be performed in a transaction to ensure data consistency.

### Uniqueness Rules (per entity type)
- **Work Experience**: Same company + similar role title + overlapping dates.
- **Education**: Same institution + same degree + same field + overlapping dates.
- **Skills**: Same skill name (and possibly category).
- **Projects**: Similar project name (and possibly description/tech).
- **Certifications**: Same credential ID or same name + issuing organization.
- **Responsibilities/Achievements**: Semantic similarity within the context of a specific parent Work Experience or Project.

---

## Endpoints

### 1. Upload CV
- **URL:** `/api/arc/cv`
- **Method:** `POST`
- **Description:** Upload a CV file for processing and extraction. Extracted data is deduplicated and merged into the user's Arc according to the rules above.
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
  - Extracted data is not simply appended; it is deduplicated and merged into the Arc as described above.

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
  - `PUT`/`POST`: Update or add to Arc profile data. All updates/additions must use the same deduplication and merging logic as described above to ensure uniqueness.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request/Response:**
  - To be defined as feature is implemented
- **Notes:**
  - All manual additions/edits must also be deduplicated and merged according to the rules above.

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
- All Arc data updates (from CVs or manual edits) must use deduplication and merging logic to ensure uniqueness.
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