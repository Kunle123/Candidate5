from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import time
import logging
from logging.config import dictConfig
from app.routers.health import router as health_router
from app.routers.subscriptions import router as subscriptions_router
from app.routers.payments import router as payments_router
from app.routers.webhooks import router as webhooks_router
from app.config import LogConfig

# Setup logging
dictConfig(LogConfig())
logger = logging.getLogger("payment_service")

# Initialize FastAPI app
app = FastAPI(
    title="CandidateV Payment Service",
    description="API for managing payments and subscriptions for the CandidateV platform",
    version="1.0.0"
)

# CORS Configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,https://candidatev.vercel.app,https://candidate5.co.uk,https://www.candidate5.co.uk").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID middleware for tracking
@app.middleware("http")
async def add_request_id_and_log(request: Request, call_next):
    logger.info(f"Request started: {request.method} {request.url.path} (print fallback)")
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

# Stripe API key check
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
if not STRIPE_API_KEY:
    logger.warning("STRIPE_API_KEY environment variable is not set. Payment features will not work correctly.")
if not STRIPE_WEBHOOK_SECRET:
    logger.warning("STRIPE_WEBHOOK_SECRET environment variable is not set. Stripe webhooks will not work correctly.")

# Register routers
app.include_router(health_router)
app.include_router(subscriptions_router)
app.include_router(payments_router)
app.include_router(webhooks_router)

@app.on_event("startup")
async def startup():
    logger.info("Starting up Payment Service")
    logger.info(f"ALL ENV VARS AT STARTUP: {dict(os.environ)}")
    logger.info(f"CWD: {os.getcwd()}")
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".env"):
                logger.info(f"Found .env file: {os.path.join(root, file)}")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down Payment Service")

@app.get("/")
async def root():
    return {"message": "CandidateV Payment Service"}

@app.get("/health")
def health():
    return {"status": "ok"}

# Run debug server if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8005"))) 