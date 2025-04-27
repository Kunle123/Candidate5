import os
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx

app = FastAPI()

auth_service_url = os.environ.get("AUTH_SERVICE_URL", "http://auth-service:8000")
security = HTTPBearer()

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI"}

@app.post("/auth/login")
async def login(request: Request):
    data = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{auth_service_url}/auth/login", json=data)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()

@app.post("/auth/register")
async def register(request: Request):
    data = await request.json()
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{auth_service_url}/auth/register", json=data)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()

@app.get("/users/me")
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    headers = {"Authorization": f"Bearer {credentials.credentials}"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{auth_service_url}/auth/me", headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()

@app.post("/api/auth/register")
async def register_alias(request: Request):
    return await register(request)

@app.post("/api/auth/login")
async def login_alias(request: Request):
    return await login(request)
