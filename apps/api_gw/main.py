import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("api_gw")

print("DEBUG: This is the deployed API Gateway main.py")
import os
from fastapi import FastAPI, Request, HTTPException, Depends, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import StreamingResponse, JSONResponse
from routers.cover_letters import router as cover_letters_router
from routers.mega_cv import router as mega_cv_router
from routers.applications import router as applications_router
import re
from fastapi.exception_handlers import http_exception_handler

app = FastAPI()

allowed_origins = [
    "https://c5-frontend-pied.vercel.app",
    "https://candidate5.co.uk",
    "https://www.candidate5.co.uk"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/docs", include_in_schema=False)
async def proxy_docs(request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{arc_service_url}/docs")
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))

@app.get("/openapi.json", include_in_schema=False)
async def proxy_openapi(request: Request):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{arc_service_url}/openapi.json")
        return Response(content=resp.content, status_code=resp.status_code, media_type=resp.headers.get("content-type"))

auth_service_url = os.environ.get("AUTH_SERVICE_URL")
security = HTTPBearer()

cv_service_url = os.environ.get("CV_SERVICE_URL")
ai_service_url = os.environ.get("AI_SERVICE_URL")
payment_service_url = os.environ.get("PAYMENT_SERVICE_URL")
arc_service_url = os.environ.get("ARC_SERVICE_URL")
job_agent_service_url = os.environ.get("JOB_AGENT_SERVICE_URL")

# Register the user service for proxying /api/user/* endpoints
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL")
print(f"[DEBUG] USER_SERVICE_URL at startup: {USER_SERVICE_URL}")

# Generic proxy function
async def proxy(request: StarletteRequest, base_url: str, path: str):
    url = f"{base_url}{path}"
    method = request.method
    headers = dict(request.headers)
    headers.pop("host", None)
    # Inject Authorization header for user service
    if base_url == USER_SERVICE_URL:
        headers["Authorization"] = f"Bearer {os.environ['INTER_SERVICE_SECRET']}"
    data = await request.body()
    logger.debug(f"Proxying request: {method} {url}")
    logger.debug(f"Headers: {headers}")
    logger.debug(f"Query params: {request.query_params}")
    if method in ["POST", "PUT"]:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type or "text" in content_type:
            try:
                logger.debug(f"Body: {data.decode('utf-8')}")
            except UnicodeDecodeError:
                logger.debug("Body: [unreadable text data]")
        else:
            logger.debug("Body: [binary or multipart data not logged]")
    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.request(
                method,
                url,
                headers=headers,
                content=data,
                params=request.query_params,
                timeout=180.0
            )
            logger.debug(f"Response status: {resp.status_code}")
            logger.debug(f"Response headers: {dict(resp.headers)}")
            body = resp.content
            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type or "text" in content_type:
                try:
                    logger.debug(f"Response body: {body.decode('utf-8')}")
                except UnicodeDecodeError:
                    logger.debug("Body: [unreadable text data]")
            else:
                logger.debug("Body: [binary or multipart data not logged]")
            response = Response(
                content=body,
                status_code=resp.status_code,
                headers=dict(resp.headers)
            )
            # Always add CORS headers
            origin = request.headers.get("origin")
            if origin in allowed_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
            else:
                response.headers["Access-Control-Allow-Origin"] = allowed_origins[0]
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            return response
        except Exception as e:
            logger.error(f"Error proxying request: {str(e)}")
            error_response = Response(
                content=str(e).encode(),
                status_code=500,
                headers={
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": request.headers.get("origin", allowed_origins[0]),
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
    # Keep the /api/arc prefix when forwarding
    path = f"/api/arc{full_path}"
    return await proxy(request, arc_service_url, path)

@app.api_route("/api/career-ark{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_career_ark(request: StarletteRequest, full_path: str):
    path = f"/api/career-ark{full_path}"
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
async def options_handler(full_path: str):
    response = JSONResponse(content={})
    response.headers["Access-Control-Allow-Origin"] = "https://c5-frontend-pied.vercel.app"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    return response

@app.api_route("/api/webhooks{full_path:path}", methods=["POST", "OPTIONS"])
async def proxy_webhooks(request: StarletteRequest, full_path: str):
    path = f"/api/webhooks{full_path}"
    return await proxy(request, payment_service_url, path)

@app.api_route("/api/user/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_user(request: StarletteRequest, full_path: str):
    logger.info(f"[DEBUG] proxy_user called with full_path: {full_path}")
    path = f"/api/user/{full_path}"
    return await proxy(request, USER_SERVICE_URL, path)

@app.api_route("/search_jobs", methods=["POST"])
async def proxy_search_jobs(request: StarletteRequest):
    return await proxy(request, job_agent_service_url, "/search_jobs")

@app.api_route("/api/cvs{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_api_cvs(request: StarletteRequest, full_path: str):
    # Forward /api/cvs to /api/cv in the backend
    path = "/api/cv" + (full_path or "")
    path = re.sub(r'/+', '/', path)
    print(f"Proxying /api/cvs to CV service path: {path}")
    return await proxy(request, cv_service_url, path)

@app.api_route("/api/cv{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_api_cv(request: StarletteRequest, full_path: str):
    path = "/api/cv" + (full_path or "")
    path = re.sub(r'/+', '/', path)
    print(f"Proxying to CV service path: {path}")
    return await proxy(request, cv_service_url, path)

@app.api_route("/api/cover-letter{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_cover_letter(request: StarletteRequest, full_path: str):
    path = f"/api/cover-letter{full_path}"
    return await proxy(request, cv_service_url, path)

@app.api_route("/auth/google", methods=["GET"])
async def proxy_auth_google(request: Request):
    return await proxy(request, USER_SERVICE_URL, "/auth/google")

@app.api_route("/auth/google/callback", methods=["GET"])
async def proxy_auth_google_callback(request: Request):
    return await proxy(request, USER_SERVICE_URL, "/auth/google/callback")

@app.api_route("/auth/linkedin", methods=["GET"])
async def proxy_auth_linkedin(request: Request):
    return await proxy(request, USER_SERVICE_URL, "/auth/linkedin")

@app.api_route("/auth/linkedin/callback", methods=["GET"])
async def proxy_auth_linkedin_callback(request: Request):
    return await proxy(request, USER_SERVICE_URL, "/auth/linkedin/callback")

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(request: StarletteRequest, full_path: str):
    logger.info(f"[DEBUG] catch_all called with full_path: {full_path}")
    return Response(content="Catch-all route hit", status_code=200)

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    response = await http_exception_handler(request, exc)
    response.headers["Access-Control-Allow-Origin"] = "https://c5-frontend-pied.vercel.app"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    return response

# Add a global exception handler for all unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    response = JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )
    response.headers["Access-Control-Allow-Origin"] = "https://c5-frontend-pied.vercel.app"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    return response

# Update all CORS headers to use the correct allowed origin
ALLOWED_ORIGIN = "https://c5-frontend-pied.vercel.app"

@app.api_route("/api/applications{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_applications(request: StarletteRequest, full_path: str):
    path = f"/api/applications{full_path}"
    return await proxy(request, cv_service_url, path)
