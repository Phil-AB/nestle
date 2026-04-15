"""
API v2 Router - Generation and Population Modules

Includes all v2 endpoints.
"""

from fastapi import APIRouter
from src.api.v2.endpoints import profiles, integration, automation, validation

api_v2_router = APIRouter()

# Include document profile management endpoints
api_v2_router.include_router(
    profiles.router,
    prefix="/api/v2"
)

# Include pre-loan integration endpoints
api_v2_router.include_router(
    integration.router,
    prefix="/api/v2"
)

# Include automation endpoints
api_v2_router.include_router(
    automation.router,
    prefix="/api/v2"
)

# Include validation engine endpoints (Step 2 & Step 6 pipeline)
api_v2_router.include_router(
    validation.router,
    prefix="/api/v2"
)
