"""API routers."""

from fastapi import APIRouter

from app.api import analysis, auth, discovery, employers, preferences, profile

api_router = APIRouter()
api_router.include_router(analysis.router)
api_router.include_router(auth.router)
api_router.include_router(discovery.router)
api_router.include_router(employers.router)
api_router.include_router(profile.router)
api_router.include_router(preferences.router)
