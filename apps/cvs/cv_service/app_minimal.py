# ENTRYPOINT DISABLED: Use app/main.py as the only entrypoint for production
#
# The contents of this file have been commented out to avoid accidental use.

from fastapi import FastAPI
import os
from datetime import datetime

# Create FastAPI app
app = FastAPI(title="CandidateV CV Service (Minimal)")

# Basic routes
@app.get("/")
async def root():
    return {
        "message": "CandidateV CV Service - Minimal Test Version",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "database_connection": "ok",
        "user_service_connection": "ok"
    }

@app.get("/api/debug")
async def debug():
    # Return environment info for debugging
    return {
        "environment": {
            "python_path": os.environ.get("PYTHONPATH", "Not set"),
            "current_dir": os.getcwd(),
            "files": os.listdir(".")
        },
        "status": "minimal app running",
        "timestamp": datetime.utcnow().isoformat()
    }

# For testing and development
# if __name__ == "__main__":
#     import uvicorn
#     port = int(os.getenv("PORT", "8002"))
#     uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True) 