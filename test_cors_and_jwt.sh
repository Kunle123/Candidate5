#!/bin/bash

# Set these variables as needed
API_URL="https://api-gw-production.up.railway.app"
FRONTEND_ORIGIN="https://c5-frontend-pied.vercel.app"
USER_ID="748142f2-e8b8-4e96-a9c2-defdf3c99b3e"
JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6Ijc0ODE0MmYyLWU4YjgtNGU5Ni1hOWMyLWRlZmRmM2M5OWIzZSIsImVtYWlsIjoia3VubGUyMDAwQG1zbi5jb20iLCJpYXQiOjE3NDY0NTU5NzgsImV4cCI6MTc0NjQ1Nzc3OH0.fxkVE2PWsm05Y9KTF-FjVsxvQs1eAt0OSm8eIPTAKps"

# Test CORS preflight (OPTIONS)
echo "Testing CORS preflight (OPTIONS) for /api/subscriptions/user/$USER_ID"
curl -i -X OPTIONS "$API_URL/api/subscriptions/user/$USER_ID" \
  -H "Origin: $FRONTEND_ORIGIN" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization"
echo

# Test GET with JWT
echo "Testing GET with JWT for /api/subscriptions/user/$USER_ID"
curl -i -X GET "$API_URL/api/subscriptions/user/$USER_ID" \
  -H "Origin: $FRONTEND_ORIGIN" \
  -H "Authorization: Bearer $JWT_TOKEN"
echo 