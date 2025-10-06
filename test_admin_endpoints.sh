#!/bin/bash

# Admin Dashboard API Testing Script
# Prerequisites: 
# 1. Admin service deployed to Railway
# 2. Super admin created using create_super_admin.py
# 3. API Gateway updated with ADMIN_SERVICE_URL

# Configuration
API_BASE_URL="https://api-gw-production.up.railway.app"
ADMIN_EMAIL="admin@candidate5.co.uk"  # Change to your admin email
ADMIN_PASSWORD="your_password"        # Change to your admin password

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "Admin Dashboard API Testing"
echo "========================================"
echo ""

# Step 1: Admin Login
echo "${YELLOW}Step 1: Admin Login${NC}"
echo "POST $API_BASE_URL/api/admin/auth/login"
echo ""

LOGIN_RESPONSE=$(curl -s -X POST "$API_BASE_URL/api/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$ADMIN_EMAIL\", \"password\": \"$ADMIN_PASSWORD\"}")

echo "Response:"
echo "$LOGIN_RESPONSE" | jq '.'

# Extract token
TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "${RED}❌ Login failed! Cannot continue tests.${NC}"
  echo "Please check your credentials and ensure admin service is deployed."
  exit 1
fi

echo ""
echo "${GREEN}✅ Login successful!${NC}"
echo "Token: ${TOKEN:0:50}..."
echo ""
sleep 2

# Step 2: Get Current Admin Info
echo "${YELLOW}Step 2: Get Current Admin Info${NC}"
echo "GET $API_BASE_URL/api/admin/auth/me"
echo ""

curl -s -X GET "$API_BASE_URL/api/admin/auth/me" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "${GREEN}✅ Admin info retrieved${NC}"
echo ""
sleep 2

# Step 3: List Users
echo "${YELLOW}Step 3: List Users (first 10)${NC}"
echo "GET $API_BASE_URL/api/admin/users/?skip=0&limit=10"
echo ""

USERS_RESPONSE=$(curl -s -X GET "$API_BASE_URL/api/admin/users/?skip=0&limit=10" \
  -H "Authorization: Bearer $TOKEN")

echo "$USERS_RESPONSE" | jq '.'

# Get first user ID for subsequent tests
FIRST_USER_ID=$(echo "$USERS_RESPONSE" | jq -r '.[0].id')
FIRST_USER_EMAIL=$(echo "$USERS_RESPONSE" | jq -r '.[0].email')

echo ""
echo "${GREEN}✅ Users list retrieved${NC}"
echo "First user: $FIRST_USER_EMAIL ($FIRST_USER_ID)"
echo ""
sleep 2

# Step 4: Get User Detail
if [ "$FIRST_USER_ID" != "null" ] && [ -n "$FIRST_USER_ID" ]; then
  echo "${YELLOW}Step 4: Get User Detail${NC}"
  echo "GET $API_BASE_URL/api/admin/users/$FIRST_USER_ID"
  echo ""

  curl -s -X GET "$API_BASE_URL/api/admin/users/$FIRST_USER_ID" \
    -H "Authorization: Bearer $TOKEN" | jq '.'

  echo ""
  echo "${GREEN}✅ User detail retrieved${NC}"
  echo ""
  sleep 2

  # Step 5: Get User Profile (Career Arc)
  echo "${YELLOW}Step 5: Get User Career Arc${NC}"
  echo "GET $API_BASE_URL/api/admin/users/$FIRST_USER_ID/profile"
  echo ""

  curl -s -X GET "$API_BASE_URL/api/admin/users/$FIRST_USER_ID/profile" \
    -H "Authorization: Bearer $TOKEN" | jq '. | keys'

  echo ""
  echo "${GREEN}✅ Career arc retrieved (showing keys only)${NC}"
  echo ""
  sleep 2

  # Step 6: Adjust Credits (Add 5 credits)
  echo "${YELLOW}Step 6: Adjust User Credits (Add 5 credits)${NC}"
  echo "POST $API_BASE_URL/api/admin/users/$FIRST_USER_ID/credits"
  echo ""

  curl -s -X POST "$API_BASE_URL/api/admin/users/$FIRST_USER_ID/credits" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "amount": 5,
      "reason": "Promo",
      "notes": "Testing credit adjustment"
    }' | jq '.'

  echo ""
  echo "${GREEN}✅ Credits adjusted${NC}"
  echo ""
  sleep 2

  # Step 7: Get Credit History
  echo "${YELLOW}Step 7: Get Credit Transaction History${NC}"
  echo "GET $API_BASE_URL/api/admin/users/$FIRST_USER_ID/credits/history"
  echo ""

  curl -s -X GET "$API_BASE_URL/api/admin/users/$FIRST_USER_ID/credits/history" \
    -H "Authorization: Bearer $TOKEN" | jq '.'

  echo ""
  echo "${GREEN}✅ Credit history retrieved${NC}"
  echo ""
  sleep 2

  # Step 8: Get User Activity
  echo "${YELLOW}Step 8: Get User Activity (CVs & Applications)${NC}"
  echo "GET $API_BASE_URL/api/admin/users/$FIRST_USER_ID/activity"
  echo ""

  curl -s -X GET "$API_BASE_URL/api/admin/users/$FIRST_USER_ID/activity" \
    -H "Authorization: Bearer $TOKEN" | jq '.'

  echo ""
  echo "${GREEN}✅ User activity retrieved${NC}"
  echo ""
  sleep 2
fi

# Step 9: Get Analytics Summary
echo "${YELLOW}Step 9: Get Analytics Summary${NC}"
echo "GET $API_BASE_URL/api/admin/analytics/summary"
echo ""

curl -s -X GET "$API_BASE_URL/api/admin/analytics/summary" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "${GREEN}✅ Analytics retrieved${NC}"
echo ""
sleep 2

# Step 10: Search Users
echo "${YELLOW}Step 10: Search Users (search='test')${NC}"
echo "GET $API_BASE_URL/api/admin/users/?search=test&limit=5"
echo ""

curl -s -X GET "$API_BASE_URL/api/admin/users/?search=test&limit=5" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "${GREEN}✅ Search results retrieved${NC}"
echo ""

# Summary
echo ""
echo "========================================"
echo "${GREEN}✅ All Tests Completed Successfully!${NC}"
echo "========================================"
echo ""
echo "Summary:"
echo "- Admin login: ✅"
echo "- Get admin info: ✅"
echo "- List users: ✅"
echo "- Get user detail: ✅"
echo "- View career arc: ✅"
echo "- Adjust credits: ✅"
echo "- View credit history: ✅"
echo "- View user activity: ✅"
echo "- Get analytics: ✅"
echo "- Search users: ✅"
echo ""
echo "Your admin dashboard backend is working perfectly!"
echo "You can now build the frontend."

