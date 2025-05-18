# Career Ark API Endpoints Specification

This document describes the required API endpoints for full add/edit functionality on the Career Ark page. These endpoints should support fetching, creating, and updating entries for Career History (work experience), Education, and Training. All endpoints require authentication (Bearer token).

---

## 1. Fetch All Career Ark Data
- **Endpoint:** `GET /api/arc`
- **Description:** Fetch all career data for the logged-in user (work experience, education, training, etc.).
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
```json
{
  "work_experience": [ ... ],
  "education": [ ... ],
  "training": [ ... ]
}
```

---

## 2. Add New Entry
### a. Add Work Experience
- **Endpoint:** `POST /api/arc/work_experience`
- **Description:** Add a new work experience entry.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:**
```json
{
  "title": "string",
  "company": "string",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD or null",
  "details": ["string", ...]
}
```
- **Response:**
```json
{
  "id": "string",
  "title": "string",
  ...
}
```

### b. Add Education
- **Endpoint:** `POST /api/arc/education`
- **Description:** Add a new education entry.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:**
```json
{
  "institution": "string",
  "degree": "string",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD or null",
  "details": ["string", ...]
}
```
- **Response:**
```json
{
  "id": "string",
  "institution": "string",
  ...
}
```

### c. Add Training
- **Endpoint:** `POST /api/arc/training`
- **Description:** Add a new training entry.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:**
```json
{
  "name": "string",
  "provider": "string",
  "date": "YYYY-MM-DD",
  "details": ["string", ...]
}
```
- **Response:**
```json
{
  "id": "string",
  "name": "string",
  ...
}
```

---

## 3. Update Entry
### a. Update Work Experience
- **Endpoint:** `PATCH /api/arc/work_experience/{id}`
- **Description:** Update an existing work experience entry.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:** (any updatable fields)
```json
{
  "title": "string",
  "company": "string",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD or null",
  "details": ["string", ...]
}
```
- **Response:**
```json
{
  "id": "string",
  "title": "string",
  ...
}
```

### b. Update Education
- **Endpoint:** `PATCH /api/arc/education/{id}`
- **Description:** Update an existing education entry.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:**
```json
{
  "institution": "string",
  "degree": "string",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD or null",
  "details": ["string", ...]
}
```
- **Response:**
```json
{
  "id": "string",
  "institution": "string",
  ...
}
```

### c. Update Training
- **Endpoint:** `PATCH /api/arc/training/{id}`
- **Description:** Update an existing training entry.
- **Headers:**
  - `Authorization: Bearer <token>`
- **Request Body:**
```json
{
  "name": "string",
  "provider": "string",
  "date": "YYYY-MM-DD",
  "details": ["string", ...]
}
```
- **Response:**
```json
{
  "id": "string",
  "name": "string",
  ...
}
```

---

## 4. Authentication
- All endpoints require a valid Bearer token in the `Authorization` header.

---

## 5. Notes
- All date fields should be in `YYYY-MM-DD` format.
- The `details` field is an array of strings (e.g., bullet points or descriptions).
- The response should return the full updated/created object.
- For delete functionality, similar endpoints can be added (e.g., `DELETE /api/arc/work_experience/{id}`). 