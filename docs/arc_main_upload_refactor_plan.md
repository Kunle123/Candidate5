# Refactor Plan: Remove cv_profile_id and CVProfile from main.py Upload Logic

## Background
The current upload logic in `main.py` still references the deprecated `CVProfile` model and the `cv_profile_id` foreign key. The database schema and business logic have been refactored to use `user_id` as the single source of truth. This document outlines the steps and provides a code example for updating the upload logic to match the new architecture.

---

## Step-by-Step Refactor Plan

### 1. Remove All Usage of CVProfile
- Delete all code that creates, fetches, or references the `CVProfile` model.
- Do not create or query a profile object for the user.

### 2. Replace cv_profile_id with user_id
- In all queries, deduplication logic, and inserts for:
  - WorkExperience
  - Education
  - Certification
  - Skill
  - Project
- Use `user_id` as the foreign key instead of `cv_profile_id`.

### 3. Update Deduplication and Insertion Logic
- When deduplicating or inserting, use `user_id` to scope all queries and inserts.
- Example: `db.query(WorkExperience).filter_by(user_id=user_id)`

### 4. Update Pass 2/Background Tasks
- If any background tasks or secondary passes use `cv_profile_id`, update them to use `user_id`.

### 5. Remove cv_profile_id from Model Instantiations
- When creating new records, do not set `cv_profile_id`. Set `user_id` instead.

### 6. Test the Endpoint
- After refactoring, test the upload endpoint with a new user and CV to ensure it works end-to-end.

---

## Example: Refactored Upload Logic (Pseudo-code)

```python
@app.post("/api/arc/cv", response_model=CVUploadResponse)
async def upload_cv(file: UploadFile = File(...), user_id: str = Depends(get_current_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    # ... extract text and metadata ...
    # Deduplicate and insert work experience
    existing_work_exps = {
        (norm(wx.company), norm(wx.title), norm(wx.start_date), norm(wx.end_date)): wx
        for wx in db.query(WorkExperience).filter_by(user_id=user_id).all()
    }
    for idx, wx in enumerate(metadata.get("work_experiences", [])):
        # ... deduplication logic ...
        db.add(WorkExperience(
            id=uuid.uuid4(),
            user_id=user_id,
            company=wx.get("company", ""),
            title=wx.get("job_title", wx.get("title", "")),
            start_date=wx.get("start_date", ""),
            end_date=wx.get("end_date", ""),
            description=None,
            order_index=idx
        ))
    # Repeat for Education, Certification, Skill, Project using user_id
    # ...
    db.commit()
    # ... rest of logic ...
```

---

## Checklist
- [ ] All references to `cv_profile_id` removed from main.py
- [ ] All references to `CVProfile` removed from main.py
- [ ] All queries and inserts use `user_id`
- [ ] Endpoint tested and working with new user and CV

---

## Notes
- This refactor brings the upload logic in line with the new single-source-of-truth user profile architecture.
- After this change, the backend will be consistent with the refactored models and database schema. 