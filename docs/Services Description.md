# Services Description

## CV Service (`apps/cvs/cv_service/`)

- **Stores and manages CVs and cover letters** in the database (including DOCX files and metadata).
- **CRUD operations** for CVs and cover letters (create, read, update, delete).
- **File upload and download** for CVs and cover letters (legacy and current endpoints).
- **Lists all CVs/cover letters** for a user.
- **Manages application records** (linking CVs, cover letters, and thread IDs).
- **Legacy/compatibility endpoints** for older frontend versions.
- **Does NOT generate CVs/cover letters using AI** or interact with OpenAI.

---

## Ark Service (`apps/arc/arc_service/`)

- **Orchestrates the AI-powered apply flow** using the OpenAI Assistants API.
- **Manages OpenAI threads** for context-aware, multi-step conversations.
- **Generates tailored CVs and cover letters** using user profile and job description.
- **Supports thread-aware follow-up actions** (e.g., update, refine, extract keywords).
- **Extracts important keywords** from user profile and job description using AI.
- **Aggregates and serves structured user profile data** (work experience, education, skills, etc.).
- **Exposes `/generate-assistant` and related endpoints** for the frontend to drive the apply flow.
- **Does NOT persist DOCX files** or handle file storage.

---

## AI Service (`apps/ai/ai_service/`)

- **Provides AI-powered analysis and optimization** of CVs/resumes.
- **Optimizes CV sections** using OpenAI (e.g., improves content, incorporates keywords, tailors to job/industry).
- **Analyzes CVs** for feedback, strengths, weaknesses, and ATS keyword fit.
- **Exposes endpoints for keyword extraction, CV analysis, and optimization**.
- **Fetches CV data from the CV service** for analysis/optimization.
- **Does NOT store or serve CV files**; acts as a stateless AI utility.

---

## User Service (`apps/user_service/`)

- **Manages user profiles and settings** (CRUD for user data, including address, LinkedIn, etc.).
- **Handles authentication and authorization** (JWT-based).
- **Manages job applications and job history** for users.
- **Provides endpoints for user feedback, password changes, and verification**.
- **Interacts with the Ark service** to create CV profiles when a new user is registered.
- **Does NOT generate or store CVs/cover letters**; focuses on user/account data.

---

## Payments Service (`apps/payments/`)

- **Integrates with Stripe to manage payments and subscriptions.**
- **Provides endpoints to add, list, and delete payment methods** (cards) for users.
- **Supports setting a default payment method** for each user.
- **Handles payment history retrieval** (shows past payments, receipts, invoices).
- **Creates Stripe SetupIntents and Checkout Sessions** for secure card setup and payments.
- **Handles Stripe webhooks** for payment and subscription events.
- **Requires authentication (Bearer token) for all user-specific endpoints.**
- **Does NOT store card details directly**; all sensitive data is managed by Stripe.
