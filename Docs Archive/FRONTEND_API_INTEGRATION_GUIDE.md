# Frontend API Integration Guide: Cover Letters, Mega CV, and Applications

All endpoints require a valid JWT Bearer token in the `Authorization` header. All IDs are UUIDs. All endpoints return JSON.

---

## 1. Cover Letters

### List all cover letters
- **GET** `/cover-letters`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
[
  { "id": "uuid", "name": "string", "created": "datetime", "job": "string", "status": "string" }
]
```

### Create a new cover letter
- **POST** `/cover-letters`
- **Headers:** `Authorization: Bearer <token>`
- **Body:**
```json
{
  "jobDescription": "string",
  "style": "string",
  "intro": "string",
  "experience": "string",
  "interest": "string",
  "closing": "string"
}
```
- **Response:**
```json
{ "id": "uuid", ... }
```

### Get a specific cover letter
- **GET** `/cover-letters/{id}`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
{ "id": "uuid", "jobDescription": "string", ... }
```

### Update a cover letter
- **PUT** `/cover-letters/{id}`
- **Headers:** `Authorization: Bearer <token>`
- **Body:** (same as create)
- **Response:**
```json
{ "id": "uuid", ... }
```

### Delete a cover letter
- **DELETE** `/cover-letters/{id}`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
{ "success": true }
```

---

## 2. Mega CV

### List previous CVs
- **GET** `/mega-cv/previous-cvs`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
[
  { "id": "uuid", "name": "string", "sections": [ { "id": "uuid", "label": "string" } ] }
]
```

### Create/save a Mega CV
- **POST** `/mega-cv`
- **Headers:** `Authorization: Bearer <token>`
- **Body:**
```json
{
  "jobDescription": "string",
  "selectedSections": [ "uuid", ... ]
}
```
- **Response:**
```json
{ "id": "uuid", ... }
```

### Get a specific Mega CV
- **GET** `/mega-cv/{id}`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
{ "id": "uuid", "jobDescription": "string", ... }
```

### Delete a Mega CV
- **DELETE** `/mega-cv/{id}`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
{ "success": true }
```

---

## 3. Applications

### List all applications
- **GET** `/applications`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
[
  { "id": "uuid", "job": "string", "company": "string", "date": "datetime", "status": "string" }
]
```

### Create a new application
- **POST** `/applications`
- **Headers:** `Authorization: Bearer <token>`
- **Body:**
```json
{
  "job": "string",
  "company": "string",
  "date": "datetime",
  "status": "string"
}
```
- **Response:**
```json
{ "id": "uuid", ... }
```

### Get a specific application
- **GET** `/applications/{id}`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
{ "id": "uuid", "job": "string", ... }
```

### Update an application
- **PUT** `/applications/{id}`
- **Headers:** `Authorization: Bearer <token>`
- **Body:** (same as create)
- **Response:**
```json
{ "id": "uuid", ... }
```

### Delete an application
- **DELETE** `/applications/{id}`
- **Headers:** `Authorization: Bearer <token>`
- **Response:**
```json
{ "success": true }
```

---

## General Notes
- All endpoints require a valid JWT Bearer token in the `Authorization` header.
- All user-specific data is inferred from the JWT (no userId in the URL or body).
- All responses use standard HTTP status codes and return JSON.
- All IDs are UUIDs.

---

**If you need example fetch/axios code, or want to see a sample request/response for a specific endpoint, let me know!** 