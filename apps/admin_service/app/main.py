from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .routers import admin_auth, users, analytics
from .database import engine
from .models import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Admin Dashboard API",
    description="Admin panel for managing users, credits, and viewing analytics",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://candidate5.co.uk",
        "https://www.candidate5.co.uk",
        "https://c5-frontend-pied.vercel.app",
        "http://localhost:3000",  # For local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
@app.on_event("startup")
def startup():
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

# Include routers
app.include_router(admin_auth.router)
app.include_router(users.router)
app.include_router(analytics.router)

@app.get("/")
def read_root():
    return {
        "message": "Admin Dashboard API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "admin"}

