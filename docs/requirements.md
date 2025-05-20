# CV Classification & Job Role Management System

## Requirements

### 1. CV Classification & Job Role Extraction
- Correctly classify job roles even if they are described in different sections of the CV.
- Merge non-contiguous mentions of the same role under a single job title.
- Use a combination of job dates and job role/function to identify duplicates.
- Prompt the user to confirm if there is ambiguity in merging job roles.

### 2. Editable Job Roles
- All fields (company, title, start date, end date, description/details) should be editable.
- Provide endpoints to update, delete, and add job roles.

### 3. Multiple CV Imports & Deduplication
- Support importing multiple CVs sequentially.
- Detect and remove duplicate job roles based on job dates and job role/function.
- Prompt the user to confirm if there is ambiguity in merging job roles.

### 4. Testing & Logging
- Log the raw AI output, extracted data, and any errors for debugging.
- Logging should be easily retrievable from the log files.
- Turn logging on to capture all relevant information.
- Prompt the user where there are failures or if merging is needed.

### 5. Job Role Display
- Jobs should be listed in reverse chronological order.

## Progress Tracking

### Current Status
- [ ] Create a restore point for the current state.
- [ ] Enhance AI extraction logic to merge non-contiguous mentions of the same role.
- [ ] Implement deduplication logic based on job dates and job role/function.
- [ ] Add endpoints for editing job roles.
- [ ] Enhance logging and error handling.
- [ ] Test the implementation with multiple CV imports and duplicates.

### Errors Encountered & Resolutions
- No errors encountered yet.

## Next Steps
1. Create a restore point for the current state.
2. Implement the enhanced AI extraction and deduplication logic.
3. Add endpoints for editing job roles.
4. Enhance logging and error handling.
5. Test the implementation thoroughly. 