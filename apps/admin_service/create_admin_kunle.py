"""
Quick script to create super admin for kunle2000@gmail.com
Run this on Railway: railway run python apps/admin_service/create_admin_kunle.py
"""
import os
import sys
import uuid
from datetime import datetime

# Add the app directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.models import Base, Admin
from app.auth import get_password_hash

def create_kunle_admin():
    """Create super admin for kunle2000@gmail.com"""
    # Get database URL from environment
    DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("USER_DATABASE_URL")
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL or USER_DATABASE_URL environment variable is not set")
        print(f"Available env vars: {list(os.environ.keys())}")
        sys.exit(1)
    
    print(f"📊 Connecting to database...")
    
    # Create engine and session
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables if they don't exist
    print("📦 Ensuring database tables exist...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables ready")
    except Exception as e:
        print(f"⚠️  Error creating tables (may already exist): {e}")
    
    db = SessionLocal()
    
    try:
        email = "kunle2000@gmail.com"
        name = "Kunle Odekunle"
        password = "Admin2025!Secure"  # Change this after first login!
        
        # Check if admin already exists
        print(f"\n🔍 Checking if admin exists for {email}...")
        existing = db.query(Admin).filter(Admin.email == email).first()
        
        if existing:
            print(f"⚠️  Admin already exists!")
            print(f"   ID: {existing.id}")
            print(f"   Name: {existing.name}")
            print(f"   Role: {existing.role}")
            print(f"   Active: {existing.is_active}")
            print(f"   Created: {existing.created_at}")
            
            # Update to super_admin if not already
            if existing.role != "super_admin":
                existing.role = "super_admin"
                existing.updated_at = datetime.utcnow()
                db.commit()
                print(f"✅ Updated role to super_admin")
            
            return
        
        # Create super admin
        print(f"\n👤 Creating super admin...")
        super_admin = Admin(
            email=email,
            name=name,
            password_hash=get_password_hash(password),
            role="super_admin",
            is_active=True
        )
        
        db.add(super_admin)
        db.commit()
        db.refresh(super_admin)
        
        print("=" * 70)
        print("✅ SUPER ADMIN CREATED SUCCESSFULLY!")
        print("=" * 70)
        print(f"📧 Email: {email}")
        print(f"👤 Name: {name}")
        print(f"🔑 Role: super_admin")
        print(f"🆔 ID: {super_admin.id}")
        print(f"✅ Active: {super_admin.is_active}")
        print(f"📅 Created: {super_admin.created_at}")
        print("=" * 70)
        print(f"🔐 Temporary Password: {password}")
        print("=" * 70)
        print("⚠️  IMPORTANT: Change this password after first login!")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error creating super admin: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 70)
    print("CREATING SUPER ADMIN FOR kunle2000@gmail.com")
    print("=" * 70)
    create_kunle_admin()

