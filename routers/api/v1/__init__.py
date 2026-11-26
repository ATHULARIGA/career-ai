"""API v1 router registry."""

from fastapi import APIRouter

from routers.api.v1 import health, interview

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(interview.router)

__all__ = ["api_v1_router"]
