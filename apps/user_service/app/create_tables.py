from sqlalchemy import create_engine
from models import Base

DATABASE_URL = "postgresql://postgres:jvTSAaPPRetcBWADiXAJmtKILCTUuNuZ@nozomi.proxy.rlwy.net:34043/railway"

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(bind=engine)
print("Tables created!") 