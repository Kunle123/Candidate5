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

# CORS Configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173,http://localhost:5174,http://localhost:5175,https://c5-frontend-pied.vercel.app").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

auth_service_url = os.environ.get("AUTH_SERVICE_URL")
security = HTTPBearer()

cv_service_url = os.environ.get("CV_SERVICE_URL")
ai_service_url = os.environ.get("AI_SERVICE_URL")
payment_service_url = os.environ.get("PAYMENT_SERVICE_URL")
arc_service_url = os.environ.get("ARC_SERVICE_URL")

# Register the user service for proxying /api/user/* endpoints
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL")
print(f"[DEBUG] USER_SERVICE_URL at startup: {USER_SERVICE_URL}")

# Generic proxy function
async def proxy(request: StarletteRequest, base_url: str, path: str):
    url = f"{base_url}{path}"
    method = request.method
    headers = dict(request.headers)
    headers.pop("host", None)
    data = await request.body()
    print(f"Proxying request: {method} {url}")
    print(f"Headers: {headers}")
    print(f"Query params: {request.query_params}")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                method,
                url,
                headers=headers,
                content=data,
                params=request.query_params,
                timeout=60.0
            )
            print(f"Response status: {resp.status_code}")
            print(f"Response headers: {dict(resp.headers)}")
            # Log response body for debugging
            body = resp.content
            print(f"Response body: {body.decode()}")
            
            # Create response with original headers
            response = Response(
                content=body,
                status_code=resp.status_code,
                headers=dict(resp.headers)
            )
            
            # Ensure CORS headers are set
            origin = request.headers.get("origin")
            if origin in cors_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            
            return response
        except Exception as e:
            print(f"Error proxying request: {str(e)}")
            # Create error response with CORS headers
            error_response = Response(
                content=str(e).encode(),
                status_code=500,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": request.headers.get("origin", cors_origins[0]),
                    "Access-Control-Allow-Credentials": "true",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With"
                }
            )
            return error_response

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
    print(f"Received payment request: {request.method} {request.url.path}")
    print(f"Full path: {full_path}")
    # Remove any double slashes and ensure path starts with /
    path = f"/api/payments{full_path}" if full_path else "/api/payments"
    path = re.sub(r'/+', '/', path)
    print(f"Proxying payment request to: {payment_service_url}{path}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Query params: {request.query_params}")
    return await proxy(request, payment_service_url, path)

# Proxy /api/subscriptions and subpaths to Payments service
@app.api_route("/api/subscriptions{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_subscriptions(request: StarletteRequest, full_path: str):
    print(f"Received subscription request: {request.method} {request.url.path}")
    print(f"Full path: {full_path}")
    # Remove any double slashes and ensure path starts with /
    path = f"/api/subscriptions{full_path}" if full_path else "/api/subscriptions"
    path = re.sub(r'/+', '/', path)
    print(f"Proxying subscription request to: {payment_service_url}{path}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Query params: {request.query_params}")
    
    try:
        response = await proxy(request, payment_service_url, path)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        # Log response body for debugging
        body = response.body
        print(f"Response body: {body.decode()}")
        return response
    except Exception as e:
        print(f"Error in subscription proxy: {str(e)}")
        raise

@app.api_route("/api/arc{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_arc(request: StarletteRequest, full_path: str):
    path = f"/api/arc{full_path}"
    return await proxy(request, arc_service_url, path)

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
        resp = await client.get(f"{os.environ.get('USER_SERVICE_URL')}/api/user/profile", headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()

@app.api_route("/api/auth/register", methods=["POST", "OPTIONS"])
async def register_alias(request: Request):
    if request.method == "OPTIONS":
        return Response(status_code=200)
    return await register(request)

@app.api_route("/api/auth/login", methods=["POST", "OPTIONS"])
async def login_alias(request: Request):
    if request.method == "OPTIONS":
        return Response(status_code=200)
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

@app.api_route("/api/users/profile", methods=["PATCH"])
async def update_user_profile(request: Request):
    data = await request.json()
    headers = dict(request.headers)
    headers.pop("host", None)
    async with httpx.AsyncClient() as client:
        resp = await client.patch(f"{os.environ.get('USER_SERVICE_URL')}/user/profile", json=data, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()

@app.api_route("/api/auth/send-verification", methods=["POST"])
async def send_verification(request: Request):
    headers = dict(request.headers)
    headers.pop("host", None)
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{os.environ.get('USER_SERVICE_URL')}/user/send-verification", headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()

@app.api_route("/api/auth/change-password", methods=["POST"])
async def change_password(request: Request):
    data = await request.json()
    headers = dict(request.headers)
    headers.pop("host", None)
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{os.environ.get('USER_SERVICE_URL')}/user/change-password", json=data, headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()

@app.options("/{full_path:path}")
async def preflight_handler(request: Request, full_path: str):
    origin = request.headers.get("origin")
    headers = {
        "Access-Control-Allow-Origin": origin if origin in cors_origins else cors_origins[0],
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
        "Access-Control-Max-Age": "600"
    }
    return Response(status_code=200, headers=headers)

@app.api_route("/api/webhooks{full_path:path}", methods=["POST", "OPTIONS"])
async def proxy_webhooks(request: StarletteRequest, full_path: str):
    path = f"/api/webhooks{full_path}"
    return await proxy(request, payment_service_url, path)

@app.api_route("/api/user{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_user(request: StarletteRequest, full_path: str):
    """
    Proxy all /api/user/* requests to the user service.
    Make sure USER_SERVICE_URL is set to the user service base URL.
    """
    path = f"/api/user{full_path}"
    return await proxy(request, USER_SERVICE_URL, path)
