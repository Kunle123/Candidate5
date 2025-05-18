#!/bin/bash

# Check if admin token and user ID are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <admin_token> <admin_user_id>"
    exit 1
fi

ADMIN_TOKEN=$1
ADMIN_USER_ID=$2

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the purge script
python3 purge_all_users.py "$ADMIN_TOKEN" "$ADMIN_USER_ID" 