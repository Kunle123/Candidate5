import logging
logging.basicConfig(level=logging.INFO)
from fastapi import FastAPI
import os
from api.v1.router import api_router
from api.v1.endpoints.session_endpoints import session_router
from api.v1.endpoints.ai import router as ai_router
from profile_session_manager import initialize_profile_session_manager
from openai import OpenAI

logger = logging.getLogger(__name__)

app = FastAPI(title="CV Generator API", openapi_url="/api/v1/openapi.json")

# Initialize OpenAI client and ProfileSessionManager on startup
def startup():
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")
    openai_client = OpenAI(api_key=openai_api_key)
    initialize_profile_session_manager(openai_client, session_ttl_hours=24)
    logger.info("ProfileSessionManager initialized at startup")

@app.on_event("startup")
def on_startup():
    startup()

# Include all modular and session/AI routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(session_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "CV Generator API"}

@app.get("/health")
def health():
    return {"status": "ok"}
