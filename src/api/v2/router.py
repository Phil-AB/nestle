"""
API v2 Router - Generation and Population Modules

Includes all v2 endpoints.
"""

from fastapi import APIRouter
from src.api.v2.endpoints import generation, population, insights, profiles, analytics, integration, automation

api_v2_router = APIRouter()

# Include generation endpoints
api_v2_router.include_router(
    generation.router,
    prefix="/api/v2"
)

# Include population endpoints
api_v2_router.include_router(
    population.router,
    prefix="/api/v2"
)

# Include banking insights endpoints
api_v2_router.include_router(
    insights.router,
    prefix="/api/v2"
)

# Include document profile management endpoints
api_v2_router.include_router(
    profiles.router,
    prefix="/api/v2"
)

# Include analytics endpoints
api_v2_router.include_router(
    analytics.router,
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
