# Career Ark API Endpoints (Latest)

This document lists all expected endpoints for the Career Ark (CV management) feature, based on the current normalized API and frontend usage. All endpoints require a Bearer token in the `Authorization` header unless otherwise noted.

**Base URL:** `/api/career-ark`

---

## 1. Profile & Section Endpoints

### Get Current User Profile
- **GET** `/api/career-ark/profiles/me`
- **Description:** Fetch the current user's Career Ark profile (returns profile object with `id`).

### Get All Sections for a Profile
- **GET** `/api/career-ark/profiles/{profileId}/all_sections`
- **Description:** Fetch all sections (work experience, education, skills, projects, certifications, training) for a given profile.

### Work Experience
- **GET** `/api/career-ark/profiles/{profileId}/work_experience` — List all work experience entries
- **POST** `/api/career-ark/profiles/{profileId}/work_experience` — Add a new work experience entry
- **PUT** `/api/career-ark/work_experience/{id}` — Update a work experience entry
- **DELETE** `/api/career-ark/work_experience/{id}` — Delete a work experience entry
- **PATCH** `/api/career-ark/work_experience/{id}/reorder` — Reorder a work experience entry

### Education
- **GET** `/api/career-ark/profiles/{profileId}/education` — List all education entries
- **POST** `/api/career-ark/profiles/{profileId}/education` — Add a new education entry
- **PUT** `/api/career-ark/education/{id}` — Update an education entry
- **DELETE** `/api/career-ark/education/{id}` — Delete an education entry

### Training
- **GET** `/api/career-ark/profiles/{profileId}/training` — List all training entries
- **POST** `/api/career-ark/profiles/{profileId}/training` — Add a new training entry
- **PUT** `/api/career-ark/training/{id}` — Update a training entry
- **DELETE** `/api/career-ark/training/{id}` — Delete a training entry

### Skills
- **GET** `/api/career-ark/profiles/{profileId}/skills` — List all skills
- **POST** `/api/career-ark/profiles/{profileId}/skills` — Add a new skill
- **PUT** `/api/career-ark/skills/{id}` — Update a skill
- **DELETE** `/api/career-ark/skills/{id}` — Delete a skill

### Projects
- **GET** `/api/career-ark/profiles/{profileId}/projects` — List all projects
- **POST** `/api/career-ark/profiles/{profileId}/projects` — Add a new project
- **PUT** `/api/career-ark/projects/{id}` — Update a project
- **DELETE** `/api/career-ark/projects/{id}` — Delete a project

### Certifications
- **GET** `/api/career-ark/profiles/{profileId}/certifications` — List all certifications
- **POST** `/api/career-ark/profiles/{profileId}/certifications` — Add a new certification
- **PUT** `/api/career-ark/certifications/{id}` — Update a certification
- **DELETE** `/api/career-ark/certifications/{id}` — Delete a certification

---

## 2. CV Upload & Processing

### Upload CV
- **POST** `/api/career-ark/profiles/{profileId}/cv`
- **Description:** Upload a CV file for processing and extraction. (If not available, fallback: `/api/career-ark/cv`)

### Poll CV Processing Status
- **GET** `/api/career-ark/cv/status/{taskId}`
- **Description:** Get the status of a CV processing task.

### Delete a CV Task
- **DELETE** `/api/career-ark/cv/{taskId}`
- **Description:** Delete a CV processing task.

### List All CV Tasks
- **GET** `/api/career-ark/cv/tasks`
- **Description:** List all CV processing tasks for the user.

### Download Processed CV
- **GET** `/api/career-ark/cv/download/{taskId}`
- **Description:** Download the processed CV file.

---

## 3. Application Material Generation

### Generate Application Materials
- **POST** `/api/career-ark/generate`
- **Description:** Generate a tailored CV and cover letter from Ark data and a job advert.
- **Body:** `{ jobAdvert: string, arcData: object }`

---

## 4. Notes
- All endpoints require authentication (Bearer token).
- Replace `{profileId}` and `{id}` with the actual profile or entry ID.
- For section CRUD, always use the normalized endpoints above.
- If you need to fetch all sections at once, use `/profiles/{profileId}/all_sections`. 