"""
Script to create the first super admin user
Run this once after deploying the admin service
Usage: python create_super_admin.py
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Admin
from app.auth import get_password_hash

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set")
    sys.exit(1)

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_super_admin(email: str, name: str, password: str):
    """Create a super admin user"""
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing = db.query(Admin).filter(Admin.email == email).first()
        if existing:
            print(f"Admin with email {email} already exists!")
            return
        
        # Create super admin
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
        
        print(f"✅ Super admin created successfully!")
        print(f"Email: {email}")
        print(f"Name: {name}")
        print(f"Role: super_admin")
        print(f"ID: {super_admin.id}")
        print(f"\n⚠️  IMPORTANT: Save these credentials securely!")
        
    except Exception as e:
        print(f"❌ Error creating super admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("CREATE SUPER ADMIN")
    print("=" * 60)
    
    # Get credentials from user input
    email = input("Enter super admin email: ").strip()
    name = input("Enter super admin name: ").strip()
    password = input("Enter super admin password: ").strip()
    confirm_password = input("Confirm password: ").strip()
    
    if password != confirm_password:
        print("❌ Passwords do not match!")
        sys.exit(1)
    
    if len(password) < 8:
        print("❌ Password must be at least 8 characters long!")
        sys.exit(1)
    
    # Confirm creation
    print(f"\nYou are about to create a super admin with:")
    print(f"  Email: {email}")
    print(f"  Name: {name}")
    confirm = input("Continue? (yes/no): ").strip().lower()
    
    if confirm != "yes":
        print("❌ Aborted.")
        sys.exit(0)
    
    # Create tables if they don't exist
    print("\n📦 Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready")
    
    # Create super admin
    print("\n👤 Creating super admin...")
    create_super_admin(email, name, password)

