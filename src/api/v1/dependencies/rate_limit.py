"""
Rate limiting dependency.

Provides rate limiting for API endpoints.
"""

from fastapi import Request, HTTPException, status
from typing import Dict
import time
import logging
from collections import defaultdict, deque

from src.api.config import get_api_settings

# Use standard Python logging instead of app logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_api_settings()


class RateLimiter:
    """
    Simple in-memory rate limiter.

    Uses sliding window algorithm to track requests.
    For production, consider using Redis-based rate limiting.
    """

    def __init__(self):
        """Initialize rate limiter with request tracking."""
        # Dictionary to store request timestamps per client
        # Format: {client_id: deque([timestamp1, timestamp2, ...])}
        self.requests: Dict[str, deque] = defaultdict(lambda: deque())

    def is_allowed(self, client_id: str) -> bool:
        """
        Check if request is allowed under rate limit.

        Args:
            client_id: Client identifier (IP address or API key)

        Returns:
            True if request is allowed, False otherwise
        """
        if not settings.ENABLE_RATE_LIMIT:
            return True

        current_time = time.time()
        window_start = current_time - settings.RATE_LIMIT_WINDOW

        # Get request history for this client
        client_requests = self.requests[client_id]

        # Remove requests outside the current window
        while client_requests and client_requests[0] < window_start:
            client_requests.popleft()

        # Check if limit exceeded
        if len(client_requests) >= settings.RATE_LIMIT_REQUESTS:
            logger.warning(
                f"Rate limit exceeded for {client_id}: "
                f"{len(client_requests)} requests in {settings.RATE_LIMIT_WINDOW}s window"
            )
            return False

        # Add current request
        client_requests.append(current_time)
        return True

    def get_remaining_requests(self, client_id: str) -> int:
        """
        Get remaining requests for client.

        Args:
            client_id: Client identifier

        Returns:
            Number of remaining requests
        """
        if not settings.ENABLE_RATE_LIMIT:
            return settings.RATE_LIMIT_REQUESTS

        current_time = time.time()
        window_start = current_time - settings.RATE_LIMIT_WINDOW

        # Get request history
        client_requests = self.requests[client_id]

        # Clean old requests
        while client_requests and client_requests[0] < window_start:
            client_requests.popleft()

        remaining = settings.RATE_LIMIT_REQUESTS - len(client_requests)
        return max(0, remaining)

    def get_reset_time(self, client_id: str) -> float:
        """
        Get time until rate limit resets.

        Args:
            client_id: Client identifier

        Returns:
            Seconds until reset
        """
        if not settings.ENABLE_RATE_LIMIT:
            return 0

        client_requests = self.requests[client_id]

        if not client_requests:
            return 0

        # Calculate when the oldest request will expire
        oldest_request = client_requests[0]
        reset_time = oldest_request + settings.RATE_LIMIT_WINDOW
        time_until_reset = max(0, reset_time - time.time())

        return time_until_reset


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit(request: Request) -> None:
    """
    Dependency to check rate limit for incoming requests.

    Args:
        request: FastAPI request object

    Raises:
        HTTPException: If rate limit exceeded
    """
    if not settings.ENABLE_RATE_LIMIT:
        return

    # Use client IP as identifier
    # In production, combine with API key for better tracking
    client_id = request.client.host if request.client else "unknown"

    # Check if request is allowed
    if not rate_limiter.is_allowed(client_id):
        reset_time = rate_limiter.get_reset_time(client_id)

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded. Try again in {int(reset_time)} seconds.",
                "retry_after": int(reset_time),
                "limit": settings.RATE_LIMIT_REQUESTS,
                "window": settings.RATE_LIMIT_WINDOW
            },
            headers={
                "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + reset_time)),
                "Retry-After": str(int(reset_time))
            }
        )

    # Add rate limit headers to response
    remaining = rate_limiter.get_remaining_requests(client_id)
    reset_time = rate_limiter.get_reset_time(client_id)

    # Store in request state for middleware to add to response
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = int(time.time() + reset_time)
