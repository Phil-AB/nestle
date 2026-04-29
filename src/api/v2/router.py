"""
API v2 Router - Generation and Population Modules

Includes all v2 endpoints.
"""

from fastapi import APIRouter
from src.api.v2.endpoints import (
    profiles,
    integration,
    automation,
    validation,
    validation_pipeline,
    validation_reporting,
    validation_versions,
    notifications,
    bundle_pipeline,
)

api_v2_router = APIRouter()

api_v2_router.include_router(profiles.router, prefix="/api/v2")
api_v2_router.include_router(integration.router, prefix="/api/v2")
api_v2_router.include_router(automation.router, prefix="/api/v2")

# Validation engine — split across four modules sharing the /validation prefix
api_v2_router.include_router(validation.router, prefix="/api/v2")
api_v2_router.include_router(validation_pipeline.router, prefix="/api/v2")
api_v2_router.include_router(validation_reporting.router, prefix="/api/v2")
api_v2_router.include_router(validation_versions.router, prefix="/api/v2")

# Notifications
api_v2_router.include_router(notifications.router, prefix="/api/v2")

# Bundle PDF validation (additive — separate-file upload unchanged)
api_v2_router.include_router(bundle_pipeline.router, prefix="/api/v2")
