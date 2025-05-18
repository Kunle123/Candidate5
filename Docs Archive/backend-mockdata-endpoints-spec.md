# Backend API Interface Spec for Replacing Frontend Mock Data

This document describes the backend endpoints required to make all mock-data-driven pages in the frontend fully operational.

---

## 1. Cover Letters

| Endpoint                | Method | Request Body / Params                                 | Response                                              | Description                        |
|------------------------|--------|------------------------------------------------------|-------------------------------------------------------|------------------------------------|
| `/cover-letters`       | GET    | (JWT in header)                                      | `[ { id, name, created, job, status } ]`              | List all cover letters for user    |
| `/cover-letters`       | POST   | `{ jobDescription, style, intro, experience, interest, closing }` | `{ id, ... }`                      | Create a new cover letter          |
| `/cover-letters/{id}`  | GET    | (JWT in header)                                      | `{ id, jobDescription, style, intro, experience, interest, closing, created, status }` | Get a specific cover letter        |
| `/cover-letters/{id}`  | PUT    | `{ jobDescription, style, intro, experience, interest, closing }` | `{ id, ... }`                      | Update a cover letter              |
| `/cover-letters/{id}`  | DELETE | (JWT in header)                                      | `{ success: true }`                                   | Delete a cover letter              |

---

## 2. Mega CV

| Endpoint                        | Method | Request Body / Params                                 | Response                                              | Description                        |
|----------------------------------|--------|------------------------------------------------------|-------------------------------------------------------|------------------------------------|
| `/mega-cv/previous-cvs`         | GET    | (JWT in header)                                      | `[ { id, name, sections: [ { id, label } ] } ]`       | List all previous CVs and sections  |
| `/mega-cv`                      | POST   | `{ jobDescription, selectedSections }`                | `{ id, ... }`                                         | Create/save a Mega CV              |
| `/mega-cv/{id}`                 | GET    | (JWT in header)                                      | `{ id, jobDescription, selectedSections, created, ... }` | Get a specific Mega CV             |
| `/mega-cv/{id}`                 | DELETE | (JWT in header)                                      | `{ success: true }`                                   | Delete a Mega CV                   |

---

## 3. Applications

| Endpoint                | Method | Request Body / Params                                 | Response                                              | Description                        |
|------------------------|--------|------------------------------------------------------|-------------------------------------------------------|------------------------------------|
| `/applications`        | GET    | (JWT in header)                                      | `[ { id, job, company, date, status } ]`              | List all job applications for user  |
| `/applications`        | POST   | `{ job, company, date, status }`                      | `{ id, ... }`                                         | Create a new application           |
| `/applications/{id}`   | GET    | (JWT in header)                                      | `{ id, job, company, date, status, ... }`             | Get a specific application         |
| `/applications/{id}`   | PUT    | `{ job, company, date, status }`                      | `{ id, ... }`                                         | Update an application              |
| `/applications/{id}`   | DELETE | (JWT in header)                                      | `{ success: true }`                                   | Delete an application              |

---

## General Notes

- **All endpoints require JWT authentication** in the `Authorization` header.
- **All user-specific data is inferred from the JWT** (no userId in the URL or body).
- **All responses should use standard HTTP status codes** and return JSON.
- **IDs should be UUIDs** (as per system standard).

---

**Share this document with backend developers to guide implementation of the required endpoints.** 