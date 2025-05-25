# Career Ark: Single-Profile Merge & Deduplication Implementation Plan

## Objective
Implement a robust system where users can upload multiple CVs, but all data is deduplicated and merged into a single "Career Ark" profile per user. Ensure reliability, transparency, and maintainability throughout the process.

---

## Checklist

- [ ] **1. Data Model Refactor**
    - [ ] Update or create `ArkData` table for single merged profile per user
    - [ ] Ensure `CVTask` table logs uploads but does not represent multiple user-facing CVs
    - [ ] Add fields for tracking changes and deduplication status

- [ ] **2. CV Upload & Extraction**
    - [ ] Accept CV uploads as before
    - [ ] Extract and parse data using AI
    - [ ] Store raw text and AI output for debugging

- [ ] **3. Deduplication & Merging Logic**
    - [ ] Implement hashing or comparison to detect duplicate uploads
    - [ ] Develop merging logic to combine new data into Ark, section-by-section
    - [ ] Handle conflicts (e.g., most recent, most complete, or prompt user)
    - [ ] Log changes and update Ark only if new info is added

- [ ] **4. API Endpoints**
    - [ ] Update `/api/arc/upload` to trigger deduplication/merge
    - [ ] Ensure `/api/arc/data` always returns the merged Ark
    - [ ] Add feedback in API responses for duplicate or updated uploads
    - [ ] (Optional) Add endpoint for upload/change history

- [ ] **5. User Experience**
    - [ ] Inform users when uploads add, update, or duplicate info
    - [ ] Allow manual editing of Ark to resolve conflicts

- [ ] **6. Testing & Checkpoints**
    - [ ] Write unit tests for merging and deduplication logic
    - [ ] Add integration tests for upload, merge, and retrieval endpoints
    - [ ] Checkpoint: After each major step, verify all endpoints and data integrity
    - [ ] Regression test to ensure no existing functionality is broken

- [ ] **7. Documentation & Tracking**
    - [ ] Update API docs to reflect new logic
    - [ ] Track progress in this checklist (check off as we proceed)
    - [ ] Record issues, blockers, and resolutions

---

## Checkpoints

1. **Data Model Refactor Complete**
    - [ ] All migrations applied, no data loss, old endpoints still work
2. **Deduplication/Merge Logic Implemented**
    - [ ] Uploads merge as expected, no duplicate data in Ark
3. **API Endpoints Updated**
    - [ ] All endpoints return correct, merged data
4. **Testing Passed**
    - [ ] All tests green, manual checks pass
5. **Deployment/Production Check**
    - [ ] No errors in logs, user feedback positive

---

## Progress Log

- _Use this section to record work as it happens, issues found, and resolutions._

---

**Next Step:**
- Review and update data models for single-Ark logic. 