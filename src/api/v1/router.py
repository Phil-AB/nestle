"""
API v1 router.

Combines all v1 endpoint routers.
"""

from fastapi import APIRouter

from src.api.v1.endpoints import documents, ground_truth

# Create main v1 router
api_router = APIRouter()

# V1 root endpoint
@api_router.get("/", tags=["info"])
async def api_v1_info():
    """
    API v1 information endpoint.

    Returns:
        API version and available endpoints
    """
    return {
        "title": "Nestle Document Processing API",
        "version": "1.0.0",
        "endpoints": {
            "documents": "/api/v1/documents",
            "ground_truth": "/api/v1/ground-truth",
            "health": "/health",
            "docs": "/docs"
        }
    }

# Include endpoint routers
api_router.include_router(documents.router)
api_router.include_router(ground_truth.router, prefix="/ground-truth", tags=["ground-truth"])

# Future routers can be added here:
# api_router.include_router(export.router)
# api_router.include_router(webhooks.router)
