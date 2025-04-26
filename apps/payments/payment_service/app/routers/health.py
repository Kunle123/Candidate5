from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime
import os
import logging
import stripe
from typing import Dict, Any, Optional

# Configure logger
logger = logging.getLogger("payment_service")

# Initialize router
router = APIRouter(prefix="/api/health")

# Stripe API key from environment
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    stripe_connection: str
    stripe_details: Optional[Dict[str, Any]] = None

@router.get("", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint that verifies the service is running
    and checks connections to required services like Stripe.
    """
    # Check Stripe connection
    stripe_status = "unhealthy"
    stripe_details = {}
    
    try:
        if STRIPE_API_KEY:
            # Initialize Stripe with the API key
            stripe.api_key = STRIPE_API_KEY
            
            # Perform a simple operation to check connectivity
            start_time = datetime.now()
            stripe.Balance.retrieve()
            end_time = datetime.now()
            
            # Calculate response time
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            stripe_status = "ok"
            stripe_details = {
                "response_time_ms": round(response_time_ms, 2),
                "api_version": stripe.api_version
            }
        else:
            stripe_status = "not_configured"
            stripe_details = {
                "error": "Stripe API key not set"
            }
    except Exception as e:
        logger.error(f"Error connecting to Stripe: {str(e)}")
        stripe_status = "error"
        stripe_details = {
            "error": str(e)
        }
    
    # Overall status depends on dependencies
    overall_status = "healthy" if stripe_status in ["ok", "not_configured"] else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        stripe_connection=stripe_status,
        stripe_details=stripe_details
    ) 