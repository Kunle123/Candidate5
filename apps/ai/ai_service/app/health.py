from fastapi import APIRouter
from datetime import datetime
import os
import logging
import httpx
import asyncio  # Added for sleep

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# OpenAI API URL for health check
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class HealthCheck:
    def __init__(self):
        self.status = "healthy"
        self.timestamp = datetime.utcnow()
        self.version = "1.0.0"
        self.openai_connection = "ok"
        self.openai_details = {}
        self.cv_service_connection = "ok"
        self.cv_service_details = {}

@router.get("/health")
async def health_check():
    """Health check endpoint that verifies OpenAI API and CV Service connectivity."""
    
    health = HealthCheck()
    
    # Check OpenAI API connection
    if OPENAI_API_KEY:
        try:
            # Import here to avoid loading the module if API key isn't set
            from openai import OpenAI
            
            # Create a client and make a minimal API call to check connectivity
            start_time = datetime.utcnow()
            client = OpenAI(api_key=OPENAI_API_KEY)
            # Just call models.list() without any parameters
            models = client.models.list()
            end_time = datetime.utcnow()
            
            # Calculate response time in milliseconds
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            health.openai_details["response_time_ms"] = round(response_time_ms, 2)
            health.openai_details["models_available"] = True
            
        except Exception as e:
            health.openai_connection = "error"
            logger.error(f"OpenAI API health check failed: {str(e)}")
            health.openai_details["error"] = str(e)
    else:
        health.openai_connection = "error"
        health.openai_details["error"] = "OPENAI_API_KEY not set"
    
    # Check CV Service connection
    cv_service_url = os.getenv("CV_SERVICE_URL")
    logger.info(f"Health check attempting to use CV service URL: '{cv_service_url}'")
    
    max_retries = 3
    initial_delay = 0.5  # seconds
    
    for attempt in range(max_retries):
        try:
            # Try to connect to the CV service health endpoint
            async with httpx.AsyncClient(timeout=5.0) as client:
                start_time = datetime.utcnow()
                # Assuming the CV service has a /api/health endpoint
                # If not, adjust this path accordingly or remove the check
                cv_health_url = f"{cv_service_url}/api/health"
                logger.debug(f"Attempt {attempt + 1}/{max_retries}: Connecting to {cv_health_url}")
                response = await client.get(cv_health_url)
                end_time = datetime.utcnow()
                
                response_time_ms = (end_time - start_time).total_seconds() * 1000
                health.cv_service_details["response_time_ms"] = round(response_time_ms, 2)
                
                response.raise_for_status() # Raises exception for 4xx/5xx status codes
                
                # If successful, break the loop
                logger.info(f"CV service health check successful on attempt {attempt + 1}")
                health.cv_service_connection = "ok" # Explicitly set back to ok if retried after failure
                if "error" in health.cv_service_details: del health.cv_service_details["error"]
                if "status_code" in health.cv_service_details: del health.cv_service_details["status_code"]
                break 
                
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
            health.cv_service_connection = "error"
            error_message = f"CV service health check attempt {attempt + 1}/{max_retries} failed: {type(e).__name__} - {str(e)}"
            if isinstance(e, httpx.HTTPStatusError):
                 health.cv_service_details["status_code"] = e.response.status_code
                 error_message += f" (Status Code: {e.response.status_code})"
            
            logger.warning(error_message)
            health.cv_service_details["error"] = error_message
            
            if attempt < max_retries - 1:
                delay = initial_delay * (2 ** attempt)
                logger.info(f"Retrying CV service health check in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
            else:
                 logger.error(f"CV service health check failed after {max_retries} attempts.")
        except Exception as e: # Catch any other unexpected errors
            health.cv_service_connection = "error"
            error_message = f"Unexpected error during CV service health check attempt {attempt + 1}: {str(e)}"
            logger.error(error_message)
            health.cv_service_details["error"] = error_message
            break # Don't retry on unexpected errors
    
    # Set overall status based on connections
    if health.openai_connection == "error" or health.cv_service_connection == "error":
        health.status = "unhealthy"
    
    # Return health data as a dictionary
    return health.__dict__ 