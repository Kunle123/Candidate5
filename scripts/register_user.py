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

async def register_user(email: str, password: str, name: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        register_data = {
            "email": email,
            "password": password,
            "name": name
        }
        try:
            response = await client.post(
                f"{API_GATEWAY_URL}/api/auth/register",
                json=register_data
            )
            response.raise_for_status()
            result = response.json()
            print(f"Registration successful: {result}")
        except Exception as e:
            logger.error(f"Failed to register user: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            sys.exit(1)

async def main():
    if len(sys.argv) != 4:
        print("Usage: python register_user.py <email> <password> <name>")
        sys.exit(1)
    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3]
    await register_user(email, password, name)

if __name__ == "__main__":
    asyncio.run(main()) 