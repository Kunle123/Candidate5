"""
Create super admin via command line arguments
Usage: python create_super_admin_cli.py <email> <name> <password>
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Admin
from app.auth import get_password_hash

def create_super_admin(email: str, name: str, password: str):
    """Create a super admin user"""
    # Get database URL from environment
    DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("USER_DATABASE_URL")
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL or USER_DATABASE_URL environment variable is not set")
        sys.exit(1)
    
    # Create engine and session
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables if they don't exist
    print("📦 Ensuring database tables exist...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready")
    
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing = db.query(Admin).filter(Admin.email == email).first()
        if existing:
            print(f"⚠️  Admin with email {email} already exists!")
            print(f"   ID: {existing.id}")
            print(f"   Name: {existing.name}")
            print(f"   Role: {existing.role}")
            print(f"   Active: {existing.is_active}")
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
        
        print("=" * 60)
        print("✅ SUPER ADMIN CREATED SUCCESSFULLY!")
        print("=" * 60)
        print(f"Email: {email}")
        print(f"Name: {name}")
        print(f"Role: super_admin")
        print(f"ID: {super_admin.id}")
        print(f"Active: {super_admin.is_active}")
        print("=" * 60)
        print("⚠️  IMPORTANT: Save these credentials securely!")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error creating super admin: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python create_super_admin_cli.py <email> <name> <password>")
        print("Example: python create_super_admin_cli.py admin@candidate5.co.uk 'Admin User' 'SecurePassword123'")
        sys.exit(1)
    
    email = sys.argv[1]
    name = sys.argv[2]
    password = sys.argv[3]
    
    # Basic validation
    if len(password) < 8:
        print("❌ Password must be at least 8 characters long!")
        sys.exit(1)
    
    if "@" not in email:
        print("❌ Invalid email address!")
        sys.exit(1)
    
    print("=" * 60)
    print("CREATING SUPER ADMIN")
    print("=" * 60)
    print(f"Email: {email}")
    print(f"Name: {name}")
    print("=" * 60)
    
    create_super_admin(email, name, password)

