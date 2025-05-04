print("DEBUG: This is the deployed API Gateway main.py")
import os
from fastapi import FastAPI, Request, HTTPException, Depends, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import StreamingResponse
from routers.cover_letters import router as cover_letters_router
from routers.mega_cv import router as mega_cv_router
from routers.applications import router as applications_router
import re

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "https://api-gw-production.up.railway.app",
        "https://candidatev.vercel.app",
        "https://candidate-v-frontend.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*", "Content-Type", "Authorization"],
)

auth_service_url = os.environ.get("AUTH_SERVICE_URL")
security = HTTPBearer()

cv_service_url = os.environ.get("CV_SERVICE_URL")
ai_service_url = os.environ.get("AI_SERVICE_URL")
payment_service_url = os.environ.get("PAYMENT_SERVICE_URL")

# Generic proxy function
async def proxy(request: StarletteRequest, base_url: str, path: str):
    url = f"{base_url}{path}"
    method = request.method
    headers = dict(request.headers)
    headers.pop("host", None)
    data = await request.body()
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method,
            url,
            headers=headers,
            content=data,
            params=request.query_params,
            timeout=60.0
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers)
        )

# Proxy /cvs and subpaths to CV service
@app.api_route("/cvs{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_cvs(request: StarletteRequest, full_path: str):
    path = "/cvs" + (full_path or "")
    path = re.sub(r'/+', '/', path)
    print(f"full_path: '{full_path}'")
    print(f"Proxying to CV service path: {path}")
    return await proxy(request, cv_service_url, path)

# Proxy /api/ai and subpaths to AI service
@app.api_route("/api/ai{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_ai(request: StarletteRequest, full_path: str):
    path = f"/api/ai{full_path}"
    return await proxy(request, ai_service_url, path)

# Proxy /api/payments and subpaths to Payments service
@app.api_route("/api/payments{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_payments(request: StarletteRequest, full_path: str):
    path = full_path if full_path else "/api/payments"
    return await proxy(request, payment_service_url, path)

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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def list_routes():
    print("Registered routes:")
    for route in app.routes:
        print(route.path)

app.include_router(cover_letters_router)
app.include_router(mega_cv_router)
app.include_router(applications_router)
