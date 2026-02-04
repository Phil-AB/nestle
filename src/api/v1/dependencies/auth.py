"""
Authentication dependencies.

Provides authentication mechanisms for API endpoints.
"""

from fastapi import Security, HTTPException, status, Header
from fastapi.security import APIKeyHeader
from typing import Optional
import secrets
import logging

from src.api.config import get_api_settings

# Use standard Python logging instead of app logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_api_settings()

# Define API key header security scheme
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Verify API key authentication.

    Args:
        api_key: API key from header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    # Skip authentication if disabled
    if not settings.ENABLE_AUTH:
        return "auth_disabled"

    # Check if API key is provided
    if not api_key:
        logger.warning("API request without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Validate API key
    if settings.API_KEYS and api_key not in settings.API_KEYS:
        logger.warning(f"Invalid API key attempt: {api_key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    logger.debug(f"API key validated: {api_key[:10]}...")
    return api_key


async def get_optional_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """
    Get API key without requiring it (for optional auth endpoints).

    Args:
        api_key: API key from header

    Returns:
        API key if provided and valid, None otherwise
    """
    if not settings.ENABLE_AUTH:
        return None

    if api_key and api_key in settings.API_KEYS:
        return api_key

    return None


def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure random API key.

    Args:
        length: Length of the API key

    Returns:
        Generated API key
    """
    return secrets.token_urlsafe(length)


async def verify_admin_access(api_key: str = Security(verify_api_key)) -> str:
    """
    Verify admin-level API access.

    Args:
        api_key: Validated API key

    Returns:
        API key if admin access granted

    Raises:
        HTTPException: If not admin
    """
    # TODO: Implement role-based access control
    # For now, all valid API keys have admin access
    return api_key
