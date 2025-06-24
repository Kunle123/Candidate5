# Applications API Contract

This document describes the API for grouping a CV and cover letter for a single role ("Application") in the CandidateV backend. Use these endpoints to create, list, and download grouped documents for each job application.

---

## 1. Create Application (CV + Cover Letter for a Role)

**POST /api/applications**

- **Headers:**
  - `Authorization: Bearer <token>`
- **Payload:**
  ```json
  {
    "role_title": "Project Manager: Microsoft 23/06/25 12:39",
    "job_description": "...full job description...",
    "cv_text": "...CV text...",
    "cover_letter_text": "...cover letter text..."
  }
  ```
- **Response:**
  ```json
  {
    "id": "<application_id>",
    "role_title": "Project Manager: Microsoft 23/06/25 12:39",
    "created_at": "2025-06-24T21:00:00Z"
  }
  ```

---

## 2. List Applications

**GET /api/applications**

- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
  ```json
  [
    {
      "id": "<application_id>",
      "role_title": "Project Manager: Microsoft 23/06/25 12:39",
      "created_at": "2025-06-24T21:00:00Z"
    },
    ...
  ]
  ```

---

## 3. Download CV DOCX for an Application

**GET /api/applications/{id}/cv**

- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
  ```json
  {
    "filename": "cv_<application_id>.docx",
    "filedata": "<base64 string>",
    "application_id": "<application_id>"
  }
  ```

---

## 4. Download Cover Letter DOCX for an Application

**GET /api/applications/{id}/cover-letter**

- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
  ```json
  {
    "filename": "cover_letter_<application_id>.docx",
    "filedata": "<base64 string>",
    "application_id": "<application_id>"
  }
  ```

---

## 5. Notes for Frontend
- Use the `role_title` for display (e.g., as a card title).
- Use the `created_at` field for sorting or display.
- To download, use the returned `application_id` with the appropriate endpoint.
- Decode the `filedata` base64 string and save as a `.docx` file (see previous instructions for code sample).
- All endpoints require authentication.

---

For any questions or further integration help, contact the backend team. 