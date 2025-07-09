#!/bin/bash

curl -X POST "https://api-gw-production.up.railway.app/api/career-ark/generate-assistant" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjdkZWMxOTM3LTUxY2UtNDYxNS1iOTRhLTFhY2ExOGJmNWMxZCIsImVtYWlsIjoia3VubGUyMDAwQGdtYWlsLmNvbSIsImlhdCI6MTc1MTcxMjI5NiwiZXhwIjoxNzUxNzE0MDk2fQ.p2IeiUgFQfHvjIcTYydPXL1UOzNKWIMyeyISHFP8c9w" \
  -H "Content-Type: application/json" \
  -d '{
    "jobAdvert": "Project Manager - Leap Transformation Project (Maternity Cover)",
    "arcData": {"work_experience": [{"company": "Test Company", "title": "Test Title", "start_date": "2020", "end_date": "2021", "description": "Did important things."}]},
    "cvOptions": {"num_pages": 2, "include_keywords": true, "include_relevant_experience": true}
  }' 