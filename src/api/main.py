"""
FastAPI main application.

Production-grade REST API for the Nestle Agentic Document Processing System.
"""

# Load .env before any module that reads environment variables
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv
_load_dotenv(_Path(__file__).parent.parent.parent / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import base64
import json
import os
import time
import logging
from datetime import datetime, timezone
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
        redirect_slashes=False,
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
        """Health check: database connectivity + Bedrock token status."""
        checks: dict = {
            "version": settings.API_VERSION,
            "environment": settings.ENVIRONMENT,
        }

        # 1. Database
        db_ok = False
        try:
            from src.database.connection import get_engine
            from sqlalchemy import text
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            db_ok = True
            checks["db"] = "ok"
        except Exception as exc:
            checks["db"] = f"error: {exc}"

        # 2. Bedrock bearer token — decode expiry without making a live API call.
        #    The token is base64-encoded and contains a JSON or structured payload
        #    that may include an expiry timestamp. We attempt a best-effort decode;
        #    if the token is opaque we skip expiry checking.
        bedrock_status = "ok"
        bedrock_warning: str | None = None
        token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
        if not token:
            bedrock_status = "missing"
        else:
            try:
                # The token format is "ABSK<base64-payload>".
                # Strip the leading "ABSK" prefix if present, then decode.
                raw = token[4:] if token.startswith("ABSK") else token
                # Add padding if needed
                padding = 4 - len(raw) % 4
                if padding != 4:
                    raw += "=" * padding
                decoded = base64.b64decode(raw).decode("utf-8", errors="ignore")
                # The decoded payload contains "BedrockAPIKey-<id>:<expiry-epoch>:<secret>"
                # or similar structured content. Try to find a Unix timestamp.
                parts = decoded.replace("BedrockAPIKey-", "").split(":")
                for part in parts:
                    # Look for a 10-digit unix timestamp embedded in the key ID segment
                    # e.g. "l5p4-at-1718253256" — the epoch is after "-at-"
                    if "-at-" in part:
                        epoch_str = part.split("-at-")[-1].split("-")[0]
                        if epoch_str.isdigit() and len(epoch_str) == 10:
                            expiry = datetime.fromtimestamp(int(epoch_str), tz=timezone.utc)
                            now = datetime.now(tz=timezone.utc)
                            days_remaining = (expiry - now).days
                            if days_remaining < 0:
                                bedrock_status = "expired"
                                bedrock_warning = "Bearer token has expired — Bedrock calls will fail."
                            elif days_remaining <= 14:
                                bedrock_status = "expiring_soon"
                                bedrock_warning = f"Bearer token expires in {days_remaining} day(s). Rotate now."
                            checks["bedrock_token_expires_in_days"] = days_remaining
                            break
            except Exception:
                pass  # Token format is opaque — skip expiry check, assume ok

        checks["bedrock"] = bedrock_status
        if bedrock_warning:
            checks["bedrock_warning"] = bedrock_warning

        # Overall status
        if not db_ok or bedrock_status == "expired":
            overall = "degraded"
        elif bedrock_status == "expiring_soon":
            overall = "warning"
        else:
            overall = "ok"

        checks["status"] = overall
        return checks

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
        """Validate all dependencies and configs before serving traffic."""
        logger.info("Starting %s v%s", settings.API_TITLE, settings.API_VERSION)
        logger.info("Environment: %s | Debug: %s", settings.ENVIRONMENT, settings.DEBUG)

        if settings.ENVIRONMENT == "production" and settings.DEBUG:
            logger.critical(
                "DEBUG=True is set in a production environment — full stack traces will "
                "be included in error responses. Set API_DEBUG=False immediately."
            )

        # 1. Eagerly validate all use-case YAML configs — fail fast if malformed.
        try:
            from modules.validation_engine.core.config_loader import get_config_loader
            get_config_loader().validate_all_at_startup()
            logger.info("Startup check: all use-case configs valid")
        except RuntimeError as exc:
            logger.critical("Startup aborted — invalid use-case config: %s", exc)
            raise
        except Exception as exc:
            logger.critical("Startup aborted — config loader unavailable: %s", exc)
            raise RuntimeError(f"Config loader failed at startup: {exc}") from exc

        # 2. Database connectivity check.
        try:
            from src.database.connection import get_engine
            from sqlalchemy import text
            engine = get_engine()
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Startup check: database reachable")
        except Exception as exc:
            logger.critical("Startup aborted — database unreachable: %s", exc)
            raise RuntimeError(f"Database connectivity check failed: {exc}") from exc

        logger.info("%s is ready to serve traffic", settings.API_TITLE)

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
