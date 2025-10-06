from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Get database URL from environment (supports both DATABASE_URL and USER_DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("USER_DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL or USER_DATABASE_URL environment variable is not set")

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

