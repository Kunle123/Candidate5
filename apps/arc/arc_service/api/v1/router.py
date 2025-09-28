from fastapi import APIRouter
from api.v1.endpoints import work_experience
from api.v1.endpoints import education
from api.v1.endpoints import skills

api_router = APIRouter()

api_router.include_router(
    work_experience.router,
    tags=["work-experience"]
)

api_router.include_router(
    education.router,
    tags=["education"]
)

api_router.include_router(
    skills.router,
    tags=["skills"]
)
