# Frontend Integration Guide

## Key Backend Details Needed

### Work Experience Endpoints

#### Adding a Job Role
- **Endpoint:** `/api/arc/work_experience`
- **Method:** `POST`
- **Request Format:**
  ```json
  {
    "company": "string",
    "title": "string",
    "start_date": "string",
    "end_date": "string",
    "description": "string"
  }
  ```
- **Response Format:**
  ```json
  {
    "id": "string",
    "company": "string",
    "title": "string",
    "start_date": "string",
    "end_date": "string",
    "description": "string"
  }
  ```

#### Updating a Job Role
- **Endpoint:** `/api/arc/work_experience/{id}`
- **Method:** `PATCH`
- **Request Format:**
  ```json
  {
    "company": "string",
    "title": "string",
    "start_date": "string",
    "end_date": "string",
    "description": "string"
  }
  ```
- **Response Format:**
  ```json
  {
    "id": "string",
    "company": "string",
    "title": "string",
    "start_date": "string",
    "end_date": "string",
    "description": "string"
  }
  ```

#### Deleting a Job Role
- **Endpoint:** `/api/arc/work_experience/{id}`
- **Method:** `DELETE`
- **Response Format:**
  ```json
  {
    "success": true
  }
  ```

### Deduplication Handling

- **How the Backend Signals a Deduplication Event:**  
  The backend logs a message when a duplicate job role is detected. It does not return a special field or error code. Instead, it logs the duplicate and keeps the first occurrence.

- **Response When a Duplicate is Detected:**  
  The response will not indicate a duplicate. The frontend should rely on logs to detect duplicates.

- **Endpoint/Action for Confirming or Rejecting a Deduplication Merge:**  
  Currently, there is no specific endpoint for confirming or rejecting a deduplication merge. The frontend should handle this logic based on user interaction.

### Logs Endpoint

- **Endpoint:** `/api/arc/logs`
- **Method:** `GET`
- **Response Format:**
  ```json
  {
    "message": "Logs are not yet implemented. This endpoint will return logs for debugging purposes."
  }
  ```

### Skills, Projects, Certifications

- **Structure in `/api/arc/data` Response:**
  - **Skills:** Array of strings.
  - **Projects:** Array of objects with fields like `name`, `description`, and `dates`.
  - **Certifications:** Array of objects with fields like `name`, `issuer`, and `year`.

- **Endpoints for Editing/Adding/Deleting:**
  - Currently, there are no specific endpoints for editing, adding, or deleting skills, projects, or certifications. These can be managed through the `/api/arc/data` endpoint.

### Error Response Format

- **Typical Error Response:**
  ```json
  {
    "detail": "Error message"
  }
  ```
- **Specific Error Codes/Messages:**
  - No specific error codes for deduplication or validation are currently implemented. Errors are logged and returned with a generic message.

### Authentication/Authorization Changes

- **Authentication Method:**
  - The frontend should authenticate using JWT tokens, which are passed in the `Authorization` header.

## How You Can Help

- If you have a backend API documentation (Swagger/OpenAPI, Postman collection, or a simple Markdown), sharing that would be ideal for further integration details. 