# Career Ark API Endpoints Specification (For Backend)

This document lists all endpoints required for full Career Ark functionality, including CV import, AI extraction, data management, and debugging. Each endpoint includes the HTTP method, path, description, and expected request/response structure.

---

## 1. CV Upload & Processing

### Upload CV
- **POST** `/api/arc/cv`
- **Description:** Upload a CV file for processing and extraction.
- **Request:** `multipart/form-data` with a `file` field (PDF, DOC, DOCX)
- **Response:**
  ```json
  { "taskId": "string" }
  ```

### Poll CV Processing Status
- **GET** `/api/arc/cv/status/{taskId}`
- **Description:** Get the status of a CV processing task.
- **Response:**
  ```json
  {
    "status": "pending" | "completed" | "failed",
    "extractedDataSummary"?: { "workExperienceCount": number, "skillsFound": number },
    "error"?: "string"
  }
  ```

---

## 2. Debug & Inspection Endpoints (per CV task)

### Get Raw Extracted Text
- **GET** `/api/arc/cv/text/{taskId}`
- **Description:** Returns the raw extracted text from the uploaded CV.

### Get Raw AI Output
- **GET** `/api/arc/cv/ai-raw/{taskId}`
- **Description:** Returns the raw AI JSON output (per chunk, if available).

### Get Combined AI Output
- **GET** `/api/arc/cv/ai-combined/{taskId}`
- **Description:** Returns the merged AI output before filtering.

### Get Filtered AI Output
- **GET** `/api/arc/cv/ai-filtered/{taskId}`
- **Description:** Returns the filtered AI output (after removing empty/blank entries).

### Get Final ArcData
- **GET** `/api/arc/cv/arcdata/{taskId}`
- **Description:** Returns the final ArcData object that is saved to the DB.

---

## 3. Arc Data Management

### Get User Arc Data
- **GET** `/api/arc/data`
- **Description:** Retrieve the user's full Arc profile data (work experience, education, skills, etc.).
- **Response:**
  ```json
  {
    "work_experience": [ ... ],
    "education": [ ... ],
    "training": [ ... ],
    "skills": [ ... ],
    "projects": [ ... ],
    "certifications": [ ... ]
  }
  ```

### Update Arc Data
- **PUT** `/api/arc/data`
- **Description:** Update the user's Arc profile data.
- **Request:** JSON body with updated data.
- **Response:** Updated Arc data object.

---

## 4. Add/Edit/Delete Career Sections

### Add Work Experience
- **POST** `/api/arc/work_experience`
- **Description:** Add a new work experience entry.
- **Request:**
  ```json
  { "title": "string", "company": "string", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD or null", "details": ["string", ...] }
  ```
- **Response:** New work experience object.

### Update Work Experience
- **PATCH** `/api/arc/work_experience/{id}`
- **Description:** Update an existing work experience entry.
- **Request:** JSON body with updated fields.
- **Response:** Updated work experience object.

### Add Education
- **POST** `/api/arc/education`
- **Description:** Add a new education entry.
- **Request:**
  ```json
  { "institution": "string", "degree": "string", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD or null", "details": ["string", ...] }
  ```
- **Response:** New education object.

### Update Education
- **PATCH** `/api/arc/education/{id}`
- **Description:** Update an existing education entry.
- **Request:** JSON body with updated fields.
- **Response:** Updated education object.

### Add Training
- **POST** `/api/arc/training`
- **Description:** Add a new training entry.
- **Request:**
  ```json
  { "name": "string", "provider": "string", "date": "YYYY-MM-DD", "details": ["string", ...] }
  ```
- **Response:** New training object.

### Update Training
- **PATCH** `/api/arc/training/{id}`
- **Description:** Update an existing training entry.
- **Request:** JSON body with updated fields.
- **Response:** Updated training object.

---

## 5. AI Chunk Test Endpoint

### Test AI Extraction on Text Chunk
- **POST** `/api/arc/chunk`
- **Description:** Test AI extraction logic on a chunk of text (for debugging/QA).
- **Request:**
  ```json
  { "text": "string" }
  ```
- **Response:**
  ```json
  {
    "parsed": { ... },
    "raw": { ... },
    ... // any other debug info
  }
  ```

---

## 6. (Optional) Delete CV Task
- **DELETE** `/api/arc/cv/{taskId}`
- **Description:** Delete a CV processing task and all associated data.

---

**All endpoints require authentication via `Authorization: Bearer <token>`.**

If you need further details or want to add more endpoints, let me know! 