# Job Agent Search Page API Integration Guide

This document provides all the details needed for frontend developers to build a job search page that interacts with the `job_agent` backend service. It covers endpoint usage, request/response formats, and suggestions for displaying results.

---

## 1. API Endpoint Overview

### Search Jobs Endpoint
- **URL:** `/search_jobs`
- **Method:** `POST`
- **Auth:** Bearer token (user must be logged in)
- **Content-Type:** `application/json`

#### Request Body
```json
{
  "search_params": {
    "keywords": "python developer",   // (optional) search keywords
    "location": "London"              // (optional) location
  }
}
```
- Both `keywords` and `location` are optional. If omitted, the backend will use defaults or return general jobs.

#### Headers
```
Authorization: Bearer <user_token>
Content-Type: application/json
```

---

## 2. Example Request (JavaScript/Fetch)
```js
const response = await fetch('https://<your-job-agent-domain>/search_jobs', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    search_params: {
      keywords: 'python developer',
      location: 'London',
    }
  })
});
const data = await response.json();
```

---

## 3. Response Structure

The response will be a JSON object with these keys:
- `ark_data`: The user's Ark profile data (object)
- `user_id`: The user's ID (string)
- `user_email`: The user's email (string)
- `matches`: Array of matched jobs (see below)

### Example Response
```json
{
  "ark_data": { /* ...user profile... */ },
  "user_id": "abc123",
  "user_email": "kunle2000@gmail.com",
  "matches": [
    {
      "job": {
        "title": "Python Developer",
        "company": "TechCorp",
        "location": "London",
        "description": "Exciting Python role...",
        "url": "https://adzuna.com/job/xyz",
        "created": "2024-06-01T12:00:00Z"
      },
      "score": 0.87,
      "explanation": "The user's experience with Python and Django matches the job requirements."
    }
  ]
}
```

---

## 4. Display Suggestions

### Search Form
- Allow users to enter keywords and location (optional).
- Show a loading indicator while searching.

### Results List
For each item in `matches`:
- **Job Title** (link to `job.url`)
- **Company**
- **Location**
- **Match Score** (e.g., as a progress bar or percentage)
- **Explanation** (AI-generated, why this job matches the user)
- **Posted Date**

#### Example Card
```
[Python Developer] (TechCorp, London)
Score: 87%
Why: The user's experience with Python and Django matches the job requirements.
[View Job]
Posted: 2024-06-01
```

### Error Handling
- If the API returns an error (e.g., 401 Unauthorized), prompt the user to log in again.
- If no jobs are found, display a friendly message.

---

## 5. Additional Notes
- The endpoint is cloud-native and expects a valid user token.
- All job data is live from Adzuna and matched using OpenAI.
- You can further filter or sort results on the frontend if desired.

---

For any questions or to request more fields, contact the backend team. 