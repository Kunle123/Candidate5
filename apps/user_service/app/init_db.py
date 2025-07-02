from app.models import Base
from app.db import engine

# Dummy change to trigger redeploy

if __name__ == "__main__":
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("Done.") 