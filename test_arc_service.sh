#!/bin/bash

# API Gateway Base URL for Arc endpoints
API_GW_URL="https://api-gw-production.up.railway.app"
ARC_PATH="/api/arc"
EMAIL="testuser$(date +%s)@example.com"
PASSWORD="TestPassword123"

# Register user and extract token
echo "Registering user..."
REGISTER_RESPONSE=$(curl -s -X POST "$API_GW_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "'$EMAIL'", "password": "'$PASSWORD'"}')
echo "Register response: $REGISTER_RESPONSE"
TOKEN=$(echo $REGISTER_RESPONSE | grep -o '"token":"[^"]*"' | cut -d '"' -f4)

if [ -z "$TOKEN" ]; then
  echo "No token found in register response. Exiting."
  exit 1
fi

echo "Token: $TOKEN"

# Test /health
echo -e "\nTesting /health..."
curl -s "$API_GW_URL$ARC_PATH/health" | jq

# Test /cv upload (simulate with this script file as dummy)
echo -e "\nTesting /cv upload..."
UPLOAD_RESPONSE=$(curl -s -X POST "$API_GW_URL$ARC_PATH/cv" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$0")
echo "Upload response: $UPLOAD_RESPONSE"
TASK_ID=$(echo $UPLOAD_RESPONSE | jq -r '.taskId')

# Poll /cv/status/{taskId}
echo -e "\nPolling /cv/status/$TASK_ID..."
curl -s "$API_GW_URL$ARC_PATH/cv/status/$TASK_ID" -H "Authorization: Bearer $TOKEN" | jq

# Test /data (GET)
echo -e "\nTesting /data (GET)..."
curl -s "$API_GW_URL$ARC_PATH/data" -H "Authorization: Bearer $TOKEN" | jq

# Test /data (PUT)
echo -e "\nTesting /data (PUT)..."
UPDATE_DATA='{"work_experience":[{"company":"Acme","role":"Engineer","dates":"2020-2022"}],"skills":["Python","Project Management"]}'
curl -s -X PUT "$API_GW_URL$ARC_PATH/data" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATE_DATA" | jq

# Test /generate
echo -e "\nTesting /generate..."
GEN_REQ='{"jobAdvert":"Looking for a Python developer...","arcData":{"skills":["Python","Project Management"]}}'
curl -s -X POST "$API_GW_URL$ARC_PATH/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$GEN_REQ" | jq

# List tasks
echo -e "\nTesting /cv/tasks..."
curl -s "$API_GW_URL$ARC_PATH/cv/tasks" -H "Authorization: Bearer $TOKEN" | jq

# Download processed CV
echo -e "\nTesting /cv/download/$TASK_ID..."
curl -s "$API_GW_URL$ARC_PATH/cv/download/$TASK_ID" -H "Authorization: Bearer $TOKEN" --output processed_cv.txt
ls -l processed_cv.txt

# Delete task
echo -e "\nTesting /cv/$TASK_ID (DELETE)..."
curl -s -X DELETE "$API_GW_URL$ARC_PATH/cv/$TASK_ID" -H "Authorization: Bearer $TOKEN" | jq 