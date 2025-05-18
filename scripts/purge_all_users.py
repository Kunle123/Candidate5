#!/usr/bin/env python3
import os
import sys
import logging
import httpx
import asyncio
from typing import List, Dict, Any
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

class UserPurger:
    def __init__(self, admin_token: str, admin_user_id: str):
        self.admin_token = admin_token
        self.admin_user_id = admin_user_id
        self.headers = {"Authorization": f"Bearer {admin_token}"}
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from the auth service."""
        try:
            response = await self.client.get(
                f"{AUTH_SERVICE_URL}/api/auth/users",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting users: {str(e)}")
            raise

    async def purge_user(self, user_id: str) -> Dict[str, Any]:
        """Purge a single user's data."""
        try:
            # Purge from auth service
            response = await self.client.delete(
                f"{AUTH_SERVICE_URL}/api/auth/user/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return {"status": "success", "message": f"User {user_id} purged successfully"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to purge user {user_id}: {str(e)}"}

    async def purge_all_users(self):
        """Purge all users except the admin user."""
        try:
            # Get all users
            users = await self.get_all_users()
            logger.info(f"Found {len(users)} users")

            # Filter out admin user
            users_to_purge = [user for user in users if user["id"] != self.admin_user_id]
            logger.info(f"Will purge {len(users_to_purge)} users (excluding admin)")

            # Purge each user
            results = []
            for user in users_to_purge:
                result = await self.purge_user(user["id"])
                results.append({
                    "user_id": user["id"],
                    "email": user.get("email", "unknown"),
                    **result
                })
                logger.info(f"Purged user {user['id']} ({user.get('email', 'unknown')}): {result['status']}")

            return results

        except Exception as e:
            logger.error(f"Error in purge_all_users: {str(e)}")
            raise
        finally:
            await self.client.aclose()

async def main():
    if len(sys.argv) != 3:
        print("Usage: python purge_all_users.py <admin_token> <admin_user_id>")
        sys.exit(1)

    admin_token = sys.argv[1]
    admin_user_id = sys.argv[2]

    purger = UserPurger(admin_token, admin_user_id)
    try:
        results = await purger.purge_all_users()
        
        # Print summary
        logger.info("\nPurge Summary:")
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = len(results) - success_count
        
        logger.info(f"Total users processed: {len(results)}")
        logger.info(f"Successfully purged: {success_count}")
        logger.info(f"Failed to purge: {error_count}")
        
        if error_count > 0:
            logger.info("\nFailed purges:")
            for result in results:
                if result["status"] == "error":
                    logger.info(f"User {result['email']} ({result['user_id']}): {result['message']}")
    
    except Exception as e:
        logger.error(f"Failed to purge users: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 