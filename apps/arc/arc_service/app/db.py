import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from databases import Database

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/arc_db")

# SQLAlchemy ORM setup
Base = declarative_base()
engine = create_engine(DATABASE_URL.replace('+asyncpg', ''), echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async database instance for use with FastAPI
async_db = Database(DATABASE_URL) 