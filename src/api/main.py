"""
FastAPI main application.

Production-grade REST API for the Nestle Agentic Document Processing System.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import time
import logging
from typing import Callable

from src.api.v1.router import api_router
from src.api.v2.router import api_v2_router
from src.api.config import get_api_settings

# Use standard Python logging instead of app logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_api_settings()


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title=settings.API_TITLE,
        description=settings.API_DESCRIPTION,
        version=settings.API_VERSION,
        docs_url="/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/redoc" if settings.ENABLE_DOCS else None,
        openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
    )

    # Configure CORS
    if settings.ENABLE_CORS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=settings.CORS_METHODS,
            allow_headers=settings.CORS_HEADERS,
        )

    # Add GZip compression for responses
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Add request timing middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next: Callable):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # Include API routers
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(api_v2_router)  # v2 already has /api/v2 prefix in router

    # Mount static files for frontend UI
    static_dir = Path(__file__).parent.parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info(f"Static files mounted from: {static_dir}")
    else:
        logger.warning(f"Static files directory not found: {static_dir}")

    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        """
        Health check endpoint.

        Returns:
            Health status of the API
        """
        return {
            "status": "healthy",
            "version": settings.API_VERSION,
            "environment": settings.ENVIRONMENT
        }

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root():
        """
        Root endpoint with API information.

        Returns:
            API information and available endpoints
        """
        return {
            "name": settings.API_TITLE,
            "version": settings.API_VERSION,
            "docs": f"{settings.API_V1_PREFIX}/docs" if settings.ENABLE_DOCS else "disabled",
            "health": "/health",
            "api_v1": settings.API_V1_PREFIX,
            "api_v2": "/api/v2"
        }

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(_request: Request, exc: Exception):
        """
        Global exception handler for unhandled errors.

        Args:
            _request: FastAPI request
            exc: Exception raised

        Returns:
            JSON error response
        """
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An internal server error occurred",
                "detail": str(exc) if settings.DEBUG else None
            }
        )

    # Startup event
    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup."""
        logger.info(f"Starting {settings.API_TITLE} v{settings.API_VERSION}")
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"Debug mode: {settings.DEBUG}")

    # Shutdown event
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info(f"Shutting down {settings.API_TITLE}")

    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
