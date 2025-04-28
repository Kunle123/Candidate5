# Application API & Service Specification

## Overview

This document outlines the backend service architecture and API endpoints for the CV/Job Application platform. The system is split into five main services:

1. **Auth Service** – User authentication and session management
2. **User Service** – User profile and preferences
3. **CV Service** – CV upload, storage, analysis, and management
4. **AI Service** – AI-powered CV/cover letter optimization and keyword extraction
5. **Payments Service** – Subscription and billing management

---

## Service & Endpoint Specification

### 1. Auth Service

Handles user registration, login, logout, and password management.

| Endpoint                | Method | Request Body / Params                | Response                        | Description                  |
|-------------------------|--------|--------------------------------------|----------------------------------|------------------------------|
| `/auth/register`        | POST   | `{ email, password, name }`          | `{ userId, email, token }`       | Register a new user          |
| `/auth/login`           | POST   | `{ email, password }`                | `{ userId, email, token }`       | User login                   |
| `/auth/logout`          | POST   | `{}`                                 | `{ success: true }`              | User logout                  |
| `/auth/refresh-token`   | POST   | `{ refreshToken }`                   | `{ token, refreshToken }`        | Refresh JWT                  |
| `/auth/me`              | GET    | (JWT in header)                      | `{ userId, email, name }`        | Get current user info        |
| `/auth/forgot-password` | POST   | `{ email }`                          | `{ success: true }`              | Request password reset       |
| `/auth/reset-password`  | POST   | `{ token, newPassword }`             | `{ success: true }`              | Reset password               |

---

### 2. User Service

Manages user profile and preferences.

| Endpoint                | Method | Request Body / Params                | Response                        | Description                  |
|-------------------------|--------|--------------------------------------|----------------------------------|------------------------------|
| `/users/{userId}`       | GET    | (JWT in header)                      | `{ userId, email, name, ... }`   | Get user profile             |
| `/users/{userId}`       | PUT    | `{ name, ... }`                      | `{ userId, email, name, ... }`   | Update user profile          |
| `/users/{userId}`       | DELETE | (JWT in header)                      | `{ success: true }`              | Delete user account          |
| `/users/preferences`    | GET    | (JWT in header)                      | `{ ... }`                        | Get user preferences         |
| `/users/preferences`    | PUT    | `{ ... }`                            | `{ ... }`                        | Update preferences           |

---

### 3. CV Service

Handles all CV-related operations.

| Endpoint                        | Method | Request Body / Params                | Response                        | Description                  |
|----------------------------------|--------|--------------------------------------|----------------------------------|------------------------------|
| `/cvs`                          | GET    | (JWT in header)                      | `[ { cvId, name, createdAt } ]`  | List user's CVs              |
| `/cvs`                          | POST   | `multipart/form-data` (file upload)  | `{ cvId, name, ... }`            | Upload new CV                |
| `/cvs/{cvId}`                   | GET    | (JWT in header)                      | `{ cvId, name, content, ... }`   | Get CV details/content       |
| `/cvs/{cvId}`                   | PUT    | `{ name, content }`                  | `{ cvId, name, content }`        | Update CV                    |
| `/cvs/{cvId}`                   | DELETE | (JWT in header)                      | `{ success: true }`              | Delete CV                    |
| `/cvs/{cvId}/analyze`           | POST   | `{ jobDescription }`                 | `{ missingKeywords: [ ... ] }`   | Analyze CV for keywords      |
| `/cvs/{cvId}/download`          | GET    | (JWT in header)                      | (file download)                  | Download CV as file          |

---

### 4. AI Service

Provides AI-powered document optimization and keyword extraction.

| Endpoint                        | Method | Request Body / Params                | Response                        | Description                  |
|----------------------------------|--------|--------------------------------------|----------------------------------|------------------------------|
| `/ai/optimize-cv`               | POST   | `{ cvContent, jobDescription }`      | `{ optimizedCV }`                | Returns optimized CV         |
| `/ai/generate-cover-letter`      | POST   | `{ cvContent, jobDescription }`      | `{ coverLetter }`                | Returns generated cover letter|
| `/ai/keywords`                  | POST   | `{ text }`                           | `{ keywords: [ ... ] }`          | Extracts keywords            |

---

### 5. Payments Service

Handles subscriptions and billing.

| Endpoint                        | Method | Request Body / Params                | Response                        | Description                  |
|----------------------------------|--------|--------------------------------------|----------------------------------|------------------------------|
| `/payments/subscribe`           | POST   | `{ planId, paymentMethod }`          | `{ subscriptionId, status }`     | Start new subscription       |
| `/payments/webhook`             | POST   | (provider webhook payload)           | `{ success: true }`              | Handle payment events        |
| `/payments/status`              | GET    | (JWT in header)                      | `{ active, plan, ... }`          | Get current subscription     |
| `/payments/cancel`              | POST   | `{}`                                 | `{ success: true }`              | Cancel subscription          |
| `/payments/history`             | GET    | (JWT in header)                      | `[ { invoiceId, amount, ... } ]` | List payment history         |

---

## General Implementation Notes

- **Authentication:** All endpoints requiring authentication expect a JWT in the `Authorization` header:  
  `Authorization: Bearer <token>`
- **File Uploads:** Use `multipart/form-data` for CV uploads.
- **Status Codes:** Use standard HTTP status codes (200, 201, 400, 401, 404, 500, etc.).
- **AI Endpoints:** Consider rate limiting and usage tracking per user.

---

## Services Already Provided

- **CV Service (Frontend Only):**  
  - The current frontend implements mock CV upload, keyword analysis, and AI optimization logic.  
  - No backend endpoints are implemented yet; all logic is in-memory and simulated.

- **Other Services:**  
  - **Auth, User, AI, and Payments services** are not yet implemented in the backend or frontend.  
  - Endpoints above are proposed for development.

---

## Next Steps

- Implement backend services and endpoints as described above.
- Integrate frontend with backend endpoints for real data persistence and AI-powered features.
- Set up authentication and payments as per the spec.

---

**For questions, clarifications, or to request OpenAPI/Swagger documentation, please contact the product owner or tech lead.** 