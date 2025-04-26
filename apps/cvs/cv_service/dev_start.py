"""
Development starter script for CV Management Service
This script:
1. Sets up environment variables
2. Creates the SQLite database if it doesn't exist
3. Runs the CV Management Service
"""
import os
import sys
import logging
import sqlite3
import json
import uvicorn
from datetime import datetime

# Add parent directory to Python path to allow importing from app package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import the SQLAlchemy models and Base
try:
    from backend.cv_service.app.models import Base, Template, CV
    from backend.cv_service.app.database import engine
except ImportError:
    try:
        from app.models import Base, Template, CV
        from app.database import engine
    except ImportError:
        print("Could not import database models. Make sure you're in the correct directory.")
        sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dev_start")

# Database constants
DB_FILE = "cv_service.db"
DATABASE_URL = f"sqlite:///./{DB_FILE}"

def set_environment_variables():
    """Set all required environment variables."""
    os.environ["DATABASE_URL"] = DATABASE_URL
    logger.info(f"Set DATABASE_URL = {DATABASE_URL}")
    
    # Core settings
    os.environ["PORT"] = "8002"
    os.environ["JWT_SECRET"] = "your-secret-key-here-for-development-only"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
    os.environ["BASE_URL"] = f"http://localhost:{os.environ['PORT']}"
    
    # CORS settings
    os.environ["CORS_ORIGINS"] = "http://localhost:3000,http://localhost:5173,https://candidatev.vercel.app,https://candidate-v-frontend.vercel.app"
    
    # Storage settings
    os.environ["USE_LOCAL_STORAGE"] = "true"
    os.environ["LOCAL_STORAGE_PATH"] = "./uploads"

def setup_database():
    """Create the SQLite database if it doesn't exist."""
    if os.path.exists(DB_FILE):
        logger.info(f"Database file already exists: {DB_FILE}")
        return
    
    logger.info(f"Creating new database: {DB_FILE}")
    
    # Create tables
    Base.metadata.create_all(engine)
    logger.info("Database tables created")
    
    # Seed some data
    seed_database()
    
    # Verify with direct SQLite access
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    logger.info("Tables created:")
    for table in tables:
        logger.info(f"- {table[0]}")
    
    conn.close()

def seed_database():
    """Seed the database with initial data."""
    # Import the session maker
    from app.database import SessionLocal
    db = SessionLocal()
    
    try:
        # Create default CV templates
        templates = [
            {
                "id": "default",
                "name": "Professional",
                "preview_image_url": "https://example.com/templates/professional.jpg",
                "description": "A clean and professional CV template.",
                "category": "Professional",
                "is_premium": False,
                "style_options": json.dumps({
                    "color_scheme": "blue",
                    "font_family": "Roboto",
                    "layout": "standard"
                })
            },
            {
                "id": "modern",
                "name": "Modern",
                "preview_image_url": "https://example.com/templates/modern.jpg",
                "description": "A modern and creative CV template.",
                "category": "Creative",
                "is_premium": False,
                "style_options": json.dumps({
                    "color_scheme": "teal",
                    "font_family": "Montserrat",
                    "layout": "sidebar"
                })
            },
            {
                "id": "minimalist",
                "name": "Minimalist",
                "preview_image_url": "https://example.com/templates/minimalist.jpg",
                "description": "A simple and minimalist CV template.",
                "category": "Simple",
                "is_premium": False,
                "style_options": json.dumps({
                    "color_scheme": "grayscale",
                    "font_family": "Open Sans",
                    "layout": "compact"
                })
            }
        ]
        
        # Add templates to database
        for template_data in templates:
            template = Template(**template_data)
            db.add(template)
        
        db.commit()
        logger.info(f"Added {len(templates)} default templates")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {str(e)}")
    finally:
        db.close()

def setup_directories():
    """Create necessary directories."""
    # Create uploads directory
    uploads_dir = os.environ.get("LOCAL_STORAGE_PATH", "./uploads")
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
        logger.info(f"Created uploads directory: {uploads_dir}")

def run_service():
    """Run the CV Management Service."""
    port = int(os.environ.get("PORT", 8002))
    logger.info(f"Starting CV Management Service on port {port}")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    try:
        logger.info("Starting development environment for CV Management Service")
        
        # Set environment variables
        set_environment_variables()
        
        # Setup directories
        setup_directories()
        
        # Setup database
        setup_database()
        
        # Run the service
        run_service()
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        sys.exit(1) 