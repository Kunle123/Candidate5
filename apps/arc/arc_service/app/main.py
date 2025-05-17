# Minimal FastAPI app for endpoint registration debugging
from fastapi import FastAPI, APIRouter, Request
from fastapi.security import OAuth2PasswordBearer

app = FastAPI(title="Minimal Arc Service Debug")
router = APIRouter(prefix="/api/arc")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.post("/chunk-test")
async def chunk_test(request: Request):
    body = await request.json()
    text = body.get("text")
    return {"message": "chunk-test endpoint works!", "received_text": text}

app.include_router(router) 