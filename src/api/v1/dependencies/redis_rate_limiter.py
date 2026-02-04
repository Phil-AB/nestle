"""
Redis-backed distributed rate limiter.

Replaces in-memory rate limiter for multi-worker scalability.
Uses sliding window algorithm for accurate rate limiting across workers.
"""

import time
from typing import Optional
from fastapi import HTTPException, status, Request

from shared.utils.redis_client import get_redis_client
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class RedisRateLimiter:
    """
    Distributed rate limiter using Redis sliding window.

    Works across multiple workers and instances.
    Uses sorted sets for precise sliding window rate limiting.
    """

    def __init__(
        self,
        requests_per_window: int = 60,
        window_seconds: int = 60,
        identifier_prefix: str = "rate_limit"
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_window: Maximum requests allowed per window
            window_seconds: Time window in seconds
            identifier_prefix: Redis key prefix for this rate limiter
        """
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.identifier_prefix = identifier_prefix

    async def check_rate_limit(self, identifier: str) -> bool:
        """
        Check if request is within rate limit.

        Args:
            identifier: Unique identifier (API key, IP, user ID)

        Returns:
            True if allowed, False if rate limit exceeded
        """
        try:
            redis = await get_redis_client()
            key = f"{self.identifier_prefix}:{identifier}"
            now = time.time()
            window_start = now - self.window_seconds

            # Use Redis pipeline for atomic operations
            async with redis.pipeline() as pipe:
                # Remove old entries outside current window
                pipe.zremrangebyscore(key, 0, window_start)

                # Count requests in current window
                pipe.zcard(key)

                # Add current request with timestamp as score
                pipe.zadd(key, {str(now): now})

                # Set expiry on the key (cleanup)
                pipe.expire(key, self.window_seconds + 10)

                results = await pipe.execute()

            # Check request count (before adding current request)
            request_count = results[1]

            if request_count >= self.requests_per_window:
                logger.warning(
                    f"Rate limit exceeded for {identifier}: "
                    f"{request_count}/{self.requests_per_window} requests in {self.window_seconds}s"
                )
                return False

            logger.debug(f"Rate limit OK for {identifier}: {request_count + 1}/{self.requests_per_window}")
            return True

        except Exception as e:
            logger.error(f"Rate limiter error: {e}. Allowing request (fail-open).")
            # Fail-open: allow request if Redis is down
            return True

    async def __call__(self, request: Request):
        """
        FastAPI dependency function.

        Extracts identifier from request and checks rate limit.

        Args:
            request: FastAPI request object

        Raises:
            HTTPException: If rate limit exceeded
        """
        # Extract identifier (API key or IP address)
        identifier = None

        # Try to get API key from headers
        api_key = request.headers.get("X-API-Key")
        if api_key:
            identifier = api_key
        else:
            # Fallback to IP address
            client_ip = request.client.host if request.client else "unknown"
            identifier = f"ip:{client_ip}"

        if not identifier:
            # If no identifier, allow request
            logger.warning("No identifier found for rate limiting, allowing request")
            return

        allowed = await self.check_rate_limit(identifier)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.requests_per_window} requests per {self.window_seconds} seconds. Please try again later.",
                headers={"Retry-After": str(self.window_seconds)}
            )


# Create rate limiter instances for different endpoints
upload_rate_limiter = RedisRateLimiter(
    requests_per_window=20,
    window_seconds=60,
    identifier_prefix="upload_rate_limit"
)

api_rate_limiter = RedisRateLimiter(
    requests_per_window=100,
    window_seconds=60,
    identifier_prefix="api_rate_limit"
)
