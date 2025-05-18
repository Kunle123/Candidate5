# CV API Frontend Integration Guide

This guide explains how to use the new `/cvs` endpoints via the API Gateway for all CV-related operations. All requests must be made to the gateway (e.g., `<GATEWAY_URL>/cvs`).

---

## Base URL
- **Gateway Base URL:** `https://api-gw-production.up.railway.app`
- **Use this placeholder in examples:** `<GATEWAY_URL>`

---

## Authentication
All endpoints require a JWT in the `Authorization` header:
```
Authorization: Bearer <token>
```

---

## Endpoints & Example Usage

### 1. List User's CVs
- **Endpoint:** `GET <GATEWAY_URL>/cvs`
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
```json
[
  {
    "id": "cv_id",
    "metadata": { ... },
    "content": { ... },
    ...
  }
]
```

### 2. Upload New CV
- **Endpoint:** `POST <GATEWAY_URL>/cvs`
- **Headers:**
  - `Authorization: Bearer <token>`
  - `Content-Type: multipart/form-data`
- **Body:**
  - `file`: The CV file to upload (PDF, DOCX, etc.)
- **Response:**
  - `201 Created` with the new CV object (TBD: parsing logic not yet implemented)

### 3. Get CV Details
- **Endpoint:** `GET <GATEWAY_URL>/cvs/{cvId}`
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
```json
{
  "id": "cv_id",
  "metadata": { ... },
  "content": { ... },
  ...
}
```

### 4. Update CV Content
- **Endpoint:** `PUT <GATEWAY_URL>/cvs/{cvId}`
- **Headers:**
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
- **Body:**
```json
{
  "template_id": "modern",
  "style_options": { ... },
  "personal_info": { ... },
  "summary": "...",
  "custom_sections": { ... }
}
```
- **Response:**
  - Updated CV object

### 5. Delete CV
- **Endpoint:** `DELETE <GATEWAY_URL>/cvs/{cvId}`
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
```json
{ "message": "CV deleted successfully" }
```

### 6. Analyze CV for Keywords
- **Endpoint:** `POST <GATEWAY_URL>/cvs/{cvId}/analyze`
- **Headers:**
  - `Authorization: Bearer <token>`
  - `Content-Type: application/json`
- **Body:**
```json
{ "jobDescription": "Paste job description here" }
```
- **Response (placeholder):**
```json
{ "missingKeywords": ["Python", "Leadership", "Teamwork"] }
```

### 7. Download CV as File
- **Endpoint:** `GET <GATEWAY_URL>/cvs/{cvId}/download`
- **Headers:**
  - `Authorization: Bearer <token>`
- **Response:**
  - File download (currently returns JSON; will be PDF/DOCX in future)

---

## Notes
- All requests must include the JWT token.
- For file upload, use `multipart/form-data` and a `file` field.
- The analyze and download endpoints currently return placeholder/mock data.
- The `/api/cv` endpoints are still available for backward compatibility but will be deprecated.

---

## Example: Fetch All CVs (JavaScript)
```js
fetch('https://api-gw-production.up.railway.app/cvs', {
  headers: { 'Authorization': 'Bearer ' + token }
})
  .then(res => res.json())
  .then(data => console.log(data));
```

## Example: Upload CV (JavaScript)
```js
const formData = new FormData();
formData.append('file', fileInput.files[0]);
fetch('https://api-gw-production.up.railway.app/cvs', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer ' + token },
  body: formData
})
  .then(res => res.json())
  .then(data => console.log(data));
```

---

For questions or issues, contact the backend team. 