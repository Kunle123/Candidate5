import os
import logging
import httpx
from datetime import datetime
from fastapi import APIRouter

# Set up logging
logger = logging.getLogger("export_service.health")

# Define environment variables
CV_SERVICE_URL = os.getenv("CV_SERVICE_URL", "http://localhost:8002")
EXPORT_DIR = os.getenv("EXPORT_DIR", "./exports")

# Create router
router = APIRouter()

@router.get("/api/health")
async def health_check():
    """
    Health check endpoint.
    Returns the status of the service and its dependencies.
    """
    # Check if export directory exists and is writable
    export_dir_status = "ok"
    export_dir_details = {}
    
    try:
        if not os.path.exists(EXPORT_DIR):
            os.makedirs(EXPORT_DIR, exist_ok=True)
            
        # Check if directory is writable
        test_file = os.path.join(EXPORT_DIR, "health_check_test.txt")
        with open(test_file, "w") as f:
            f.write("Health check test")
        os.remove(test_file)
            
        export_dir_details["path"] = EXPORT_DIR
        export_dir_details["writable"] = True
    except Exception as e:
        export_dir_status = "error"
        export_dir_details["error"] = str(e)
        logger.error(f"Export directory health check failed: {str(e)}")
    
    # Check CV service connection
    cv_service_status = "ok"
    cv_service_details = {}
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start_time = datetime.utcnow()
            response = await client.get(f"{CV_SERVICE_URL}/api/health")
            end_time = datetime.utcnow()
            
            # Calculate response time in milliseconds
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            cv_service_details["response_time_ms"] = round(response_time_ms, 2)
            
            if response.status_code != 200:
                cv_service_status = "error"
                cv_service_details["status_code"] = response.status_code
                logger.error(f"CV service health check failed: {response.status_code}")
    except Exception as e:
        cv_service_status = "error"
        cv_service_details["error"] = str(e)
        logger.error(f"CV service health check failed: {str(e)}")
    
    # Overall service status
    status = "healthy" if export_dir_status == "ok" and cv_service_status == "ok" else "unhealthy"
    
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "export_directory": {
            "status": export_dir_status,
            "details": export_dir_details
        },
        "cv_service": {
            "status": cv_service_status,
            "details": cv_service_details
        }
    } 