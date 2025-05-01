# ENTRYPOINT DISABLED: Use app/main.py as the only entrypoint for production
#
# The contents of this file have been commented out to avoid accidental use.

from fastapi import FastAPI
from datetime import datetime

# Create a minimal FastAPI app just for health checks
app = FastAPI(title="CandidateV CV Service Health Check")

@app.get("/")
async def root():
    return {
        "message": "CandidateV CV Service Health Check",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

# For testing
if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run("healthcheck:app", host="0.0.0.0", port=port) 