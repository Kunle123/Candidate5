from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:jvTSAaPPRetcBWADiXAJmtKILCTUuNuZ@nozomi.proxy.rlwy.net:34043/railway"
TABLE_NAME = "users"

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text(f"DELETE FROM {TABLE_NAME}"))
    print(f"Deleted {result.rowcount} rows from {TABLE_NAME}.") 