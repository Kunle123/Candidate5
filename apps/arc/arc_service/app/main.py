from fastapi import FastAPI
print("[DEBUG] Executing main.py from:", __file__)
from api.v1.router import api_router

app = FastAPI(title="CV Generator API", openapi_url="/api/v1/openapi.json")

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"message": "CV Generator API"}
