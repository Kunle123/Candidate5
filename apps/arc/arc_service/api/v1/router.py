from fastapi import APIRouter
from api.v1.endpoints import work_experience
from api.v1.endpoints import education
from api.v1.endpoints import skills
from api.v1.endpoints import projects
from api.v1.endpoints import certifications
from api.v1.endpoints import training
from api.v1.endpoints import profile

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

api_router.include_router(
    projects.router,
    tags=["projects"]
)

api_router.include_router(
    certifications.router,
    tags=["certifications"]
)

api_router.include_router(
    training.router,
    tags=["training"]
)

api_router.include_router(
    profile.router,
    tags=["profile"]
)
