import logging
logging.basicConfig(level=logging.DEBUG)
from fastapi import FastAPI
import os
from api.v1.router import api_router
from api.v1.endpoints.session_endpoints import session_router
from api.v1.endpoints.ai import router as ai_router
from profile_session_manager import initialize_profile_session_manager
from openai import OpenAI
import openai


def print_prompt_file_info():
    prompt_path = "/app/prompts/cv_preview.txt"
    if os.path.exists(prompt_path):
        size = os.path.getsize(prompt_path)
        with open(prompt_path, "r", encoding="utf-8") as f:
            first_200 = f.read(200)
        print(f"[DEBUG] cv_preview.txt exists, size: {size} bytes, first 200 chars: {first_200}")
        else:
        print("[DEBUG] cv_preview.txt does NOT exist in /app/prompts/")

print("=== [ARC MAIN.PY ENTRYPOINT TEST] If you see this, /app/main.py is running as the entrypoint! ===")
print_prompt_file_info()
print("[DEBUG] OpenAI version at runtime:", openai.__version__)
print("[DEBUG] Has beta:", hasattr(openai, 'beta'))
print("[DEBUG] Has vector_stores:", hasattr(openai.beta, 'vector_stores') if hasattr(openai, 'beta') else 'no beta')
# assert hasattr(openai.beta, 'vector_stores'), "OpenAI beta.vector_stores not available at runtime!"

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
