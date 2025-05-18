#!/usr/bin/env python3
import os
import sys
import logging
import httpx
import asyncio
from typing import Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Service URLs
AUTH_SERVICE_URL = "https://candidatev-auth-production.up.railway.app"
API_GATEWAY_URL = "https://api-gw-production.up.railway.app"

async def create_admin_user(email: str, password: str, name: str) -> Dict[str, Any]:
    """Create an admin user and get the token."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Register the user
        register_data = {
            "email": email,
            "password": password,
            "name": name
        }
        
        try:
            # Register through API gateway
            response = await client.post(
                f"{API_GATEWAY_URL}/api/auth/register",
                json=register_data
            )
            response.raise_for_status()
            register_result = response.json()
            logger.info("User registered successfully")
            
            # Login to get token
            login_data = {
                "email": email,
                "password": password
            }
            response = await client.post(
                f"{API_GATEWAY_URL}/api/auth/login",
                json=login_data
            )
            response.raise_for_status()
            login_result = response.json()
            
            return {
                "user_id": register_result["user"]["id"],
                "token": login_result["token"],
                "email": email
            }
            
        except Exception as e:
            logger.error(f"Error creating admin user: {str(e)}")
            raise

async def main():
    if len(sys.argv) != 4:
        print("Usage: python create_admin.py <email> <password> <name>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3]

    try:
        result = await create_admin_user(email, password, name)
        logger.info("\nAdmin user created successfully!")
        logger.info(f"User ID: {result['user_id']}")
        logger.info(f"Email: {result['email']}")
        logger.info(f"Token: {result['token']}")
        logger.info("\nYou can now use this token with the purge script:")
        logger.info(f"./run_purge.sh '{result['token']}' <user_id_to_purge>")
    except Exception as e:
        logger.error(f"Failed to create admin user: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 