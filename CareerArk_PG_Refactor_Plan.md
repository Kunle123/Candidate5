# Career Ark PostgreSQL Refactor Planning Document

## Goals
- Move from JSONB blob storage to a fully normalized PostgreSQL schema for CV data.
- Implement per-entity REST endpoints for all CV sections (profile, work experience, education, skills, projects, certifications).
- Preserve order of all ordered entities using `order_index`.
- Ensure all entries have unique `id` fields (serial primary keys).
- No legacy data migration required; start with a clean slate.
- No admin import/export SQL functions, versioning, or duplicate detection/merge API in this phase.

---

## Key Decisions
- **Frontend will use granular endpoints for all CRUD and reordering.**
- **Backend will use SQLAlchemy ORM for all business logic and order management.**
- **No bulk import/export, versioning, or admin merge endpoints for now.**

---

## Implementation Steps

### 1. Database Migration
- [x] Create new tables: `cv_profiles`, `work_experiences`, `education`, `skills`, `projects`, `certifications` (with `order_index` where needed).
- [x] Add necessary indexes and constraints.
- [ ] Drop/archive old JSON-based tables if not needed.

### 2. Backend (Python/SQLAlchemy)
- [x] Create SQLAlchemy models for each table.
- [ ] Implement per-entity CRUD endpoints:
    - [ ] `/profiles` (create, get, update, delete)
    - [ ] `/work_experience` (CRUD, reorder)
    - [ ] `/education` (CRUD, reorder)
    - [ ] `/skills` (CRUD)
    - [ ] `/projects` (CRUD, reorder)
    - [ ] `/certifications` (CRUD, reorder)
- [ ] Implement order management for all ordered entities.
- [ ] Ensure all entries have unique `id` fields and preserve order.

### 3. Frontend Changes
- [ ] Update API calls to use granular endpoints.
- [ ] Use `id` fields for editing/deleting entries.
- [ ] Send new order to backend when reordering items.
- [ ] Display items in the order returned by the backend.

### 4. Testing & Validation
- [ ] Test all CRUD and reordering operations end-to-end.
- [ ] Validate that order and data integrity are preserved.

---

## API Endpoint Signatures & Frontend Contract

### Profile
- `POST /profiles` — Create a new profile
- `GET /profiles/{user_id}` — Get a profile by user ID
- `PUT /profiles/{user_id}` — Update profile details
- `DELETE /profiles/{user_id}` — Delete a profile

### Work Experience
- `POST /profiles/{profile_id}/work_experience` — Add a work experience entry
- `GET /profiles/{profile_id}/work_experience` — List all work experiences (ordered)
- `GET /work_experience/{id}` — Get a single work experience entry
- `PUT /work_experience/{id}` — Update a work experience entry
- `DELETE /work_experience/{id}` — Delete a work experience entry
- `PATCH /work_experience/{id}/reorder` — Change the order of a work experience entry

### Education, Projects, Certifications
- Same as work experience, replacing the entity name as appropriate.

### Skills
- `POST /profiles/{profile_id}/skills` — Add a skill
- `GET /profiles/{profile_id}/skills` — List all skills
- `DELETE /skills/{id}` — Delete a skill

### Frontend Contract Example (Work Experience)
- Add:
```json
POST /profiles/123/work_experience
{
  "company": "Acme Corp",
  "title": "Engineer",
  "start_date": "Jan 2020",
  "end_date": "Dec 2021",
  "description": "Did stuff",
  "order_index": 0
}
```
- Reorder:
```json
PATCH /work_experience/1/reorder
{
  "new_order_index": 2
}
```
- List:
```json
GET /profiles/123/work_experience
[
  { "id": 1, "company": "...", "order_index": 0, ... },
  { "id": 2, "company": "...", "order_index": 1, ... }
]
```

---

## Progress Log
- **[DATE]** Planning document created. User confirmed requirements and decisions.
- **[DATE]** Database schema and SQLAlchemy models drafted. API endpoint signatures and frontend contract outlined.

---

## Next Steps
- Implement backend CRUD and reorder endpoints for each entity.
- Update frontend to use new endpoints and handle order management.
- Test and validate end-to-end.
- Update this document as progress is made and decisions are finalized. 