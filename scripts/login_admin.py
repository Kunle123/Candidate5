#!/usr/bin/env python3
import sys
import logging
import httpx
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

API_GATEWAY_URL = "https://api-gw-production.up.railway.app"

async def login_admin(email: str, password: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        login_data = {
            "email": email,
            "password": password
        }
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/api/auth/login",
                json=login_data
            )
            response.raise_for_status()
            login_result = response.json()
            user_id = login_result.get("user", {}).get("id")
            token = login_result.get("token")
            if not user_id or not token:
                logger.error("Login response missing user ID or token.")
                sys.exit(1)
            print(f"USER_ID={user_id}")
            print(f"TOKEN={token}")
        except Exception as e:
            logger.error(f"Failed to log in as admin: {str(e)}")
            sys.exit(1)

async def main():
    if len(sys.argv) != 3:
        print("Usage: python login_admin.py <email> <password>")
        sys.exit(1)
    email = sys.argv[1]
    password = sys.argv[2]
    await login_admin(email, password)

if __name__ == "__main__":
    asyncio.run(main()) 