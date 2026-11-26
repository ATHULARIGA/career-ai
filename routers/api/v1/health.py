"""Versioned health and service metadata endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health", response_class=JSONResponse)
def api_v1_health() -> JSONResponse:
    """Returns API v1 health status and environment mode."""
    return JSONResponse({
        "status": "ok",
        "version": "v1",
        "environment": settings.app_env,
    })
