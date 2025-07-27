# Arc Service Profile Refactor Plan

## Overview
This document outlines the steps to refactor the arc service so that it uses the user profile from the user service (users table) as the single source of truth, eliminating the need for a local `cv_profiles` table in the arc service.

---

## Step 1: Identify All Profile Usages in Arc Service
- The arc service currently uses its own `cv_profiles` table and `CVProfile` model.
- Many tables (e.g., `work_experience`, `skills`, `projects`, etc.) reference `cv_profile_id` as a foreign key.

---

## Step 2: Refactor to Use User Service Profile

### A. Remove/Bypass Local Profile Table
- Stop using or referencing the `cv_profiles` table for user profile data.
- If other tables (e.g., `work_experience`, `projects`) reference `cv_profiles`, update them to reference `user_id` directly.

#### Example: Fetch Profile from User Service
```python
import httpx

async def get_user_profile(user_id: str, token: str) -> dict:
    url = f"https://api-gw-production.up.railway.app/api/user/profile/{user_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
```
- Use this function in endpoints that need profile data.

### B. Update Foreign Keys in Other Tables
- Change all references from `cv_profile_id` to `user_id` in:
  - `work_experience`
  - `skills`
  - `projects`
  - `education`
  - `certifications`
  - `training`
- Update the SQLAlchemy models and Alembic migrations accordingly.

#### Example: Model Change
```python
# Before
cv_profile_id = Column(UUID(as_uuid=True), ForeignKey("cv_profiles.id", ondelete="CASCADE"), nullable=False, index=True)

# After
user_id = Column(String, nullable=False, index=True)
```

### C. Update All Queries and Logic
- Replace all queries that use `cv_profile_id` with `user_id`.
- When creating new records (e.g., work experience), use the current user's `user_id` instead of a profile ID.

### D. Remove Profile Endpoints in Arc Service
- Remove or refactor endpoints like:
  - `/profiles`
  - `/profiles/me`
  - `/profiles/{user_id}`
  - `/profiles/{profile_id}/cv`
- Instead, always fetch the profile from the user service.

### E. (Optional) Drop the `cv_profiles` Table
- Once all code is refactored and tested, drop the `cv_profiles` table from the arc service database.

---

## Step 3: Migration Plan
1. Update models and migrations to use `user_id` instead of `cv_profile_id`.
2. Refactor all endpoints and business logic to fetch profile data from the user service.
3. Test all flows (registration, CV upload, data fetch, etc.).
4. Drop the `cv_profiles` table and remove related code.

---

## Step 4: Test the New Flow
- Register a new user.
- Upload a CV (now using `user_id` for all related data).
- Fetch and display parsed data, confirming it uses the user service profile.

---

## Summary Table

| Step                | Old (cv_profiles)         | New (user service profile)         |
|---------------------|--------------------------|------------------------------------|
| Profile source      | Arc service DB           | User service DB (via API)          |
| Foreign key         | `cv_profile_id`          | `user_id`                          |
| Profile endpoints   | `/profiles/*` (arc)      | `/api/user/profile*` (user service)|
| Data consistency    | Risk of drift            | Single source of truth             |

---

## Notes
- This refactor will simplify your architecture, eliminate data drift, and make onboarding and profile management more robust.
- If you need a sample Alembic migration or endpoint refactor, let the backend team know! 