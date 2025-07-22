# Frontend Changes for New CV/Experience Schema

## Overview
The backend now returns and expects arrays for `description` and `skills` fields in work experience, education, and projects. The frontend must be updated to handle these changes for both display and editing.

---

## 1. Data Structure Changes

### Work Experience
- `description`: **Array of strings** (each string is a bullet point)
- `skills`: **Array of strings** (skills for that role)

### Education & Projects
- `description`: **Array of strings** (each string is a bullet point)

---

## 2. Displaying Data

### Work Experience Example (React/JSX):
```jsx
<ul>
  {experience.description.map((bullet, idx) => <li key={idx}>{bullet}</li>)}
</ul>
<div>
  {experience.skills.map((skill, idx) => <span key={idx} className="skill-chip">{skill}</span>)}
</div>
```

### Education/Projects Example:
```jsx
<ul>
  {education.description.map((bullet, idx) => <li key={idx}>{bullet}</li>)}
</ul>
```

---

## 3. Editing/Creating Data
- Use a dynamic list input, textarea split on newlines, or UI for adding/removing bullets for `description`.
- Use a tag input, multi-select, or comma-separated input for `skills`.

---

## 4. Sending Data to Backend
- Send `description` and `skills` as arrays of strings.

**Example payload:**
```json
{
  "company": "Acme Corp",
  "title": "Engineer",
  "description": ["Did X", "Did Y", "Did Z"],
  "skills": ["Python", "AWS"]
}
```

---

## 5. Receiving Data from Backend
- Expect `description` and `skills` as arrays.
- For legacy data (single string), convert to array for display (e.g., split on newlines).

---

## 6. Example Data Structure
```json
{
  "work_experience": [
    {
      "company": "Acme Corp",
      "title": "Senior Engineer",
      "start_date": "Jan 2020",
      "end_date": "Present",
      "description": [
        "Led migration to cloud",
        "Improved CI/CD pipeline",
        "Mentored junior engineers"
      ],
      "skills": ["Python", "AWS", "Docker"]
    }
  ],
  "education": [
    {
      "institution": "MIT",
      "degree": "BSc Computer Science",
      "description": [
        "Graduated with honors",
        "President of Coding Club"
      ]
    }
  ],
  "projects": [
    {
      "name": "AI Chatbot",
      "description": [
        "Built a chatbot using GPT-4",
        "Integrated with Slack"
      ]
    }
  ]
}
```

---

## 7. Summary Table

| Field                        | Old Type | New Type         | Frontend UI Change Needed? |
|------------------------------|----------|------------------|---------------------------|
| work_experience.description  | string   | array of strings | Yes (bullets)             |
| work_experience.skills       | (none)   | array of strings | Yes (tags/list)           |
| education.description        | string   | array of strings | Yes (bullets)             |
| projects.description         | string   | array of strings | Yes (bullets)             |

---

## 8. Migration/Compatibility Note
- If you have existing frontend code that expects a single string, update it to handle arrays.
- For legacy data, you may want to convert a string to an array (e.g., split on newlines).

---

**If you need code snippets for a specific frontend framework, let the backend team know!** 