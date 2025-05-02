import os
import logging
from fastapi import FastAPI

# Set up verbose logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv_service")

logger.info("Starting CandidateV CV Service...")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Files in working directory: {os.listdir('.')}")
logger.info(f"Environment variables (sanitized):")
for k, v in os.environ.items():
    if 'SECRET' in k or 'PASSWORD' in k or 'TOKEN' in k:
        logger.info(f"  {k}: [REDACTED]")
    else:
        logger.info(f"  {k}: {v}")

app = FastAPI()

@app.get("/health")
async def health_check_root():
    logger.info("/health endpoint called")
    try:
        cwd = os.getcwd()
        files = os.listdir('.')
        logger.info(f"/health: cwd={cwd}, files={files}")
        return {"status": "ok", "cwd": cwd, "files": files}
    except Exception as e:
        logger.error(f"/health error: {e}")
        return {"status": "error", "error": str(e)}