#!/usr/bin/env python3
import os
import sys
import logging
import httpx
import asyncio
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
CV_SERVICE_URL = os.getenv("CV_SERVICE_URL", "http://localhost:8002")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8003")
ARC_SERVICE_URL = os.getenv("ARC_SERVICE_URL", "http://localhost:8004")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8005")

# JWT settings
JWT_SECRET = "cee809392216c387fff9792252f071005d1413fcc627bb1944bacc2338e4dc23"
JWT_ALGORITHM = "HS256"

class UserDataPurger:
    def __init__(self, admin_token: str):
        self.admin_token = admin_token
        self.headers = {"Authorization": f"Bearer {admin_token}"}
        self.client = httpx.AsyncClient(timeout=30.0)

    async def purge_user_data(self, user_id: str) -> Dict[str, Any]:
        """Purge all data for a specific user from all services."""
        results = {
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {}
        }

        # Purge from each service
        services = [
            ("auth", self.purge_auth_data),
            ("user", self.purge_user_service_data),
            ("cv", self.purge_cv_data),
            ("payment", self.purge_payment_data),
            ("arc", self.purge_arc_data),
            ("ai", self.purge_ai_data)
        ]

        for service_name, purge_func in services:
            try:
                service_result = await purge_func(user_id)
                results["services"][service_name] = {
                    "status": "success",
                    "details": service_result
                }
            except Exception as e:
                logger.error(f"Error purging {service_name} data: {str(e)}")
                results["services"][service_name] = {
                    "status": "error",
                    "error": str(e)
                }

        return results

    async def purge_auth_data(self, user_id: str) -> Dict[str, Any]:
        """Purge user data from auth service."""
        try:
            response = await self.client.delete(
                f"{AUTH_SERVICE_URL}/api/auth/user/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return {"message": "Auth data purged successfully"}
        except Exception as e:
            raise Exception(f"Failed to purge auth data: {str(e)}")

    async def purge_user_service_data(self, user_id: str) -> Dict[str, Any]:
        """Purge user data from user service."""
        try:
            response = await self.client.delete(
                f"{USER_SERVICE_URL}/api/user/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return {"message": "User service data purged successfully"}
        except Exception as e:
            raise Exception(f"Failed to purge user service data: {str(e)}")

    async def purge_cv_data(self, user_id: str) -> Dict[str, Any]:
        """Purge user data from CV service."""
        try:
            response = await self.client.delete(
                f"{CV_SERVICE_URL}/api/cv/user/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return {"message": "CV data purged successfully"}
        except Exception as e:
            raise Exception(f"Failed to purge CV data: {str(e)}")

    async def purge_payment_data(self, user_id: str) -> Dict[str, Any]:
        """Purge user data from payment service."""
        try:
            response = await self.client.delete(
                f"{PAYMENT_SERVICE_URL}/api/payments/user/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return {"message": "Payment data purged successfully"}
        except Exception as e:
            raise Exception(f"Failed to purge payment data: {str(e)}")

    async def purge_arc_data(self, user_id: str) -> Dict[str, Any]:
        """Purge user data from ARC service."""
        try:
            response = await self.client.delete(
                f"{ARC_SERVICE_URL}/api/arc/user/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return {"message": "ARC data purged successfully"}
        except Exception as e:
            raise Exception(f"Failed to purge ARC data: {str(e)}")

    async def purge_ai_data(self, user_id: str) -> Dict[str, Any]:
        """Purge user data from AI service."""
        try:
            response = await self.client.delete(
                f"{AI_SERVICE_URL}/api/ai/user/{user_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return {"message": "AI data purged successfully"}
        except Exception as e:
            raise Exception(f"Failed to purge AI data: {str(e)}")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

async def main():
    if len(sys.argv) != 3:
        print("Usage: python purge_user_data.py <admin_token> <user_id>")
        sys.exit(1)

    admin_token = sys.argv[1]
    user_id = sys.argv[2]

    # Log the configuration
    logger.info("Starting user data purge with configuration:")
    logger.info(f"AUTH_SERVICE_URL: {AUTH_SERVICE_URL}")
    logger.info(f"USER_SERVICE_URL: {USER_SERVICE_URL}")
    logger.info(f"CV_SERVICE_URL: {CV_SERVICE_URL}")
    logger.info(f"PAYMENT_SERVICE_URL: {PAYMENT_SERVICE_URL}")
    logger.info(f"ARC_SERVICE_URL: {ARC_SERVICE_URL}")
    logger.info(f"AI_SERVICE_URL: {AI_SERVICE_URL}")

    purger = UserDataPurger(admin_token)
    try:
        results = await purger.purge_user_data(user_id)
        logger.info("Purge results:")
        for service, result in results["services"].items():
            status = "✅" if result["status"] == "success" else "❌"
            logger.info(f"{status} {service}: {result.get('message', result.get('error', 'Unknown status'))}")
    finally:
        await purger.close()

if __name__ == "__main__":
    asyncio.run(main()) 