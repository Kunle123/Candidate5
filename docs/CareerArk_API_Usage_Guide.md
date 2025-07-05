# Career Ark API Usage Guide

This document explains all available endpoints for the Career Ark (CV management) API, how to use them, and best practices for frontend integration.

**Base URL:** `/api/career-ark`

---

## Authentication
All endpoints require a Bearer token in the `Authorization` header:
```
Authorization: Bearer <your_jwt_token>
```

---

## 1. Profile Endpoints

### Get Current User Profile
- **GET** `/profiles/me`
- **Description:** Fetch the current user's Career Ark profile.
- **Response:**
```json
{
  "id": "<profile_id>",
  "user_id": "<user_id>",
  "name": "<name>",
  "email": "<email>"
}
```

### Create a Profile
- **POST** `/profiles`
- **Body:**
```json
{
  "user_id": "<user_id>",
  "name": "<name>",
  "email": "<email>"
}
```
- **Response:** Profile object

---

## 2. Section Endpoints (Work Experience, Education, Training, Skills, Projects, Certifications)

All section endpoints follow this pattern:
- **List:** `GET /profiles/{profileId}/{section}`
- **Add:** `POST /profiles/{profileId}/{section}`
- **Update:** `PUT /{section}/{id}`
- **Delete:** `DELETE /{section}/{id}`
- **Reorder:** `PATCH /{section}/{id}/reorder` (where supported)

### Example: Work Experience
- **GET** `/profiles/{profileId}/work_experience` — List all
- **POST** `/profiles/{profileId}/work_experience` — Add new
- **PUT** `/work_experience/{id}` — Update
- **DELETE** `/work_experience/{id}` — Delete
- **PATCH** `/work_experience/{id}/reorder` — Reorder

**Request/Response bodies** follow the section's schema (see OpenAPI docs or backend models).

## Section Update/CRUD Endpoints
- **PUT** `/section/{id}` — Full update (all fields required)
- **PATCH** `/section/{id}` — Partial update (only changed fields required)
- **PATCH** `/section/{id}/reorder` — Reorder operation

### Example: Partial Update (PATCH)
- **PATCH** `/work_experience/{id}`
- **Body:**
```json
{
  "title": "New Title"
}
```
- Only the `title` field will be updated; all other fields remain unchanged.

---

## 3. Skills
- **PUT** `/skills/{id}` — Update a skill
- **DELETE** `/skills/{id}` — Delete a skill

---

## 4. Training
- **GET** `/profiles/{profileId}/training` — List all
- **POST** `/profiles/{profileId}/training` — Add new
- **PUT** `/training/{id}` — Update
- **DELETE** `/training/{id}` — Delete

---

## 5. Projects & Certifications
- Same pattern as above (replace section name accordingly).

---

## 6. Fetch All Sections
- **GET** `/profiles/{profileId}/all_sections`
- **Description:** Fetch all sections (work experience, education, skills, projects, certifications, training) for a given profile.
- **Response:**
```json
{
  "work_experience": [...],
  "education": [...],
  "skills": [...],
  "projects": [...],
  "certifications": [...],
  "training": [...]
}
```

---

## 7. CV Upload & Processing

### Upload CV (per profile)
- **POST** `/profiles/{profileId}/cv`
- **Body:** Multipart form with file field `file`
- **Response:**
```json
{
  "message": "Received CV for profile <profileId>",
  "filename": "cv.pdf"
}
```

### CV Processing Tasks
- **GET** `/cv/tasks` — List all tasks
- **GET** `/cv/status/{taskId}` — Get status
- **DELETE** `/cv/{taskId}` — Delete task
- **GET** `/cv/download/{taskId}` — Download processed CV

---

## 8. Application Material Generation

### Generate Application Materials
- **POST** `/generate`
- **Body:**
```json
{
  "jobAdvert": "<job advert text>",
  "arcData": { /* all sections data */ }
}
```
- **Response:**
```json
{
  "cv": "Generated CV content...",
  "cover_letter": "Generated cover letter content..."
}
```

---

## 9. Best Practices for Frontend Integration
- Always fetch the current user's profile with `/profiles/me` to get the `profileId`.
- Use the `profileId` for all section CRUD operations.
- Use `/profiles/{profileId}/all_sections` for bulk fetches.
- Always include the Bearer token in requests.
- Handle 404s gracefully (e.g., if a section is empty).
- For file uploads, use `multipart/form-data` with the field name `file`.

---

## 10. Error Handling
- All endpoints return standard HTTP status codes.
- On error, the response will include a `detail` field with an error message.

---

## Deployment Checklist & Troubleshooting for New Endpoints

If you add a new endpoint (e.g., `/generate-assistant`) and it is not recognized in production (404 Not Found), follow this checklist:

### Deployment Checklist
- [ ] Confirm the endpoint is defined in the correct router (e.g., `@router.post("/new-endpoint")`).
- [ ] Confirm the router is included in the FastAPI app (e.g., `app.include_router(...)`).
- [ ] Push all changes to the correct branch (usually `main`).
- [ ] Trigger a redeploy (push a dummy change if needed).
- [ ] Add or check a `/version` endpoint to confirm the deployed code is the latest.
- [ ] Test the new endpoint after deployment.
- [ ] Update this documentation to include the new endpoint.

### Troubleshooting
- If you get `{"detail":"Not Found"}` for a new endpoint:
  - Check the `/version` endpoint to confirm the deployed code is up to date.
  - Review backend logs for startup and route registration.
  - Ensure the API gateway is forwarding requests to the correct backend service.
  - If using CI/CD, check that the pipeline completed successfully and deployed the latest code.
  - If the problem persists, try restarting the backend service manually.

---

For persistent issues, contact the backend team or check the deployment logs for errors.

For detailed schemas and additional options, refer to the backend OpenAPI docs or contact the backend team. 