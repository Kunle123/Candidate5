#!/bin/bash

# Set environment variables
export AI_SERVICE_URL="http://${ai_service.RAILWAY_PRIVATE_DOMAIN}:8080"
export ARC_SERVICE_URL="http://${Ark_Service.RAILWAY_PRIVATE_DOMAIN}:8080"
export AUTH_SERVICE_URL="https://candidatev-auth-production.up.railway.app"
export CV_SERVICE_URL="http://${cv_service.RAILWAY_PRIVATE_DOMAIN}:8080"
export JWT_ALGORITHM="HS256"
export JWT_EXPIRATION="30m"
export JWT_SECRET="cee809392216c387fff9792252f071005d1413fcc627bb1944bacc2338e4dc23"
export PAYMENT_SERVICE_URL="http://${payments_service.RAILWAY_PRIVATE_DOMAIN}:8080"
export USER_SERVICE_URL="http://${C5_user_servce.RAILWAY_PRIVATE_DOMAIN}:8080"

# Check if admin token and user ID are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: ./run_purge.sh <admin_token> <user_id>"
    exit 1
fi

# Run the purge script
python3 purge_user_data.py "$1" "$2" 