from fastapi import APIRouter
from api.v1.endpoints import work_experience
from api.v1.endpoints import education

api_router = APIRouter()

api_router.include_router(
    work_experience.router,
    tags=["work-experience"]
)

api_router.include_router(
    education.router,
    tags=["education"]
)
