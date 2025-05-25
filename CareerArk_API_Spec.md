# Career Ark API Spec & Frontend Integration Guide

## Base URL
`/api/career-ark`

---

## 1. Work Experience Endpoints

### Get All Work Experience for a Profile
**Endpoint:**
```
GET /api/career-ark/profiles/{profile_id}/work_experience
```
**Response:**
```json
[
  {
    "id": "string",           // UUID
    "company": "string",
    "title": "string",
    "start_date": "string",   // "MMM YYYY" or "YYYY"
    "end_date": "string",     // "MMM YYYY", "YYYY", or "Present"
    "description": "string",
    "order_index": 0
  },
  ...
]
```
**Frontend Instructions:**
- Fetch this endpoint to get all work experience entries for a profile.
- **Sort the array in the frontend by `end_date` (descending) to display in reverse chronological order.**
  - Treat `"Present"` as the most recent.
  - For date parsing, use a library like `date-fns` or `moment.js` for robust sorting.

**Example (JS):**
```js
const workExp = await fetch(`/api/career-ark/profiles/${profileId}/work_experience`).then(r => r.json());
const sorted = workExp.sort((a, b) => {
  if (a.end_date === "Present") return -1;
  if (b.end_date === "Present") return 1;
  // Parse dates, fallback to 0 if invalid
  const parse = d => Date.parse(d + '-01') || 0;
  return parse(b.end_date) - parse(a.end_date);
});
```

---

### Add, Update, Delete, and Reorder Work Experience
- **Add:**  
  `POST /api/career-ark/profiles/{profile_id}/work_experience`  
  Body: `{ company, title, start_date, end_date, description, order_index (optional) }`

- **Update:**  
  `PUT /api/career-ark/work_experience/{id}`  
  Body: `{ company?, title?, start_date?, end_date?, description? }`

- **Delete:**  
  `DELETE /api/career-ark/work_experience/{id}`

- **Reorder:**  
  `PATCH /api/career-ark/work_experience/{id}/reorder`  
  Body: `{ "new_order_index": int }`

---

## 2. Other Section Endpoints

- **Education:**  
  `GET /api/career-ark/profiles/{profile_id}/education`
- **Skills:**  
  `GET /api/career-ark/profiles/{profile_id}/skills`
- **Projects:**  
  `GET /api/career-ark/profiles/{profile_id}/projects`
- **Certifications:**  
  `GET /api/career-ark/profiles/{profile_id}/certifications`

Each returns a list of objects with fields matching the normalized table.

---

## 3. How to Get `profile_id`
- After a CV upload, a new profile is created.
- You can fetch all profiles for a user (if endpoint exists) or get the latest profile after upload.

---

## 4. Example Workflow
1. **Upload CV** → Get/refresh `profile_id`.
2. **Fetch work experience:**  
   `GET /api/career-ark/profiles/{profile_id}/work_experience`
3. **Sort by `end_date` descending** for display.
4. **CRUD operations** use the endpoints above.

---

## 5. Notes
- All endpoints require authentication (token).
- All dates should be displayed in a user-friendly format.
- If you need to fetch all sections at once, make parallel requests to each endpoint.

---

## 6. Quick Reference for Frontend Team
> - Use `/api/career-ark/profiles/{profile_id}/work_experience` to fetch work experience.
> - Always sort by `end_date` descending (treat `"Present"` as most recent).
> - Use the provided endpoints for CRUD and reordering.
> - Repeat for education, skills, projects, certifications.
> - See API spec for request/response formats.
> - Contact backend if you need a bulk endpoint or have questions about date parsing. 