import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_gw")

# Clean up CORS origins from environment variable
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("API Gateway starting up...")
    logger.info(f"CORS origins: {origins}")
    logger.info(f"Environment: {dict(os.environ)}")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# ... existing code ... 