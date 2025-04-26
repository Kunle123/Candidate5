from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import os

# Import routers and modules
from app.health import router as health_router
from app.routes import router as export_router
from app.export_manager import ExportManager

# Environment variables
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost,http://localhost:3000,https://candidatev.vercel.app").split(",")

# Create FastAPI app
app = FastAPI(title="CandidateV Export Service")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(export_router)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "CandidateV Export Service"}

# Schedule cleanup of old exports at startup
@app.on_event("startup")
async def startup_event(background_tasks: BackgroundTasks):
    # Schedule periodic cleanup
    await ExportManager.schedule_cleanup(background_tasks)
    
    # Run initial cleanup
    await ExportManager.cleanup_old_exports()

# For testing and development
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8003"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True) 