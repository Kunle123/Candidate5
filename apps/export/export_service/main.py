import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
import uuid
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("export_service")

# Import app from app.py
from app import app as export_app

# Add request ID and logging middleware
@export_app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    start_time = time.time()
    logger.info(f"Request started: {request.method} {request.url.path} (ID: {request_id})")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(f"Request completed: {request.method} {request.url.path} "
                f"(ID: {request_id}) - Status: {response.status_code} - Time: {process_time:.3f}s")
    
    response.headers["X-Request-ID"] = request_id
    return response

@export_app.on_event("startup")
async def startup():
    logger.info("Starting up Export Service")
    
    # Create exports directory if it doesn't exist
    export_dir = os.getenv("EXPORT_DIR", "./exports")
    os.makedirs(export_dir, exist_ok=True)
    logger.info(f"Export directory set to: {export_dir}")
    
    # Log configuration
    cv_service_url = os.getenv("CV_SERVICE_URL")
    logger.info(f"CV Service URL: {cv_service_url}")
    
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:3000").split(",")
    logger.info(f"CORS Origins: {cors_origins}")

@export_app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down Export Service")

# Run using Uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8006"))
    uvicorn.run(export_app, host="0.0.0.0", port=port) 