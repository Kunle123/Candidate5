#!/bin/bash

API_URL="https://api-gw-production.up.railway.app"
EMAIL="testuser$(date +%s)@example.com"
PASSWORD="TestPassword123"

# Register user
echo "Registering user..."
REGISTER_RESPONSE=$(curl -s -X POST "$API_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "'$EMAIL'", "password": "'$PASSWORD'"}')
echo "Register response: $REGISTER_RESPONSE"

# Extract token from register response
TOKEN=$(echo $REGISTER_RESPONSE | grep -o '"token":"[^"]*"' | cut -d '"' -f4)

# Extract user id from register response
USER_ID=$(echo $REGISTER_RESPONSE | grep -o '"id":"[^"]*"' | cut -d '"' -f4)

if [ -z "$TOKEN" ]; then
  echo "No token found in register response. Exiting."
  exit 1
fi

if [ -z "$USER_ID" ]; then
  echo "No user id found in register response. Exiting."
  exit 1
fi

echo "Token: $TOKEN"

# Test /users/me
echo -e "\nTesting /users/me..."
curl -s -X GET "$API_URL/users/me" -H "Authorization: Bearer $TOKEN" | jq

# Test /cvs
echo -e "\nTesting /cvs..."
curl -s -X GET "$API_URL/cvs" -H "Authorization: Bearer $TOKEN" | jq

# Test /api/ai
echo -e "\nTesting /api/ai..."
curl -s -X GET "$API_URL/api/ai" -H "Authorization: Bearer $TOKEN" | jq

# Test /api/ai/keywords (POST)
echo -e "\nTesting /api/ai/keywords..."
curl -s -X POST "$API_URL/api/ai/keywords" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Python developer with cloud experience and leadership skills."}' | jq

# Test /api/payments/methods/{user_id} (GET)
echo -e "\nTesting /api/payments/methods/{user_id}..."
curl -s -X GET "$API_URL/api/payments/methods/$USER_ID" \
  -H "Authorization: Bearer $TOKEN" | jq 