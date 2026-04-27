"""
Redis client for distributed caching and rate limiting.

Provides async Redis connection management for multi-worker deployments.
"""

import redis.asyncio as redis
from typing import Optional

from shared.utils.config import settings
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)

# Global Redis client singleton
_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """
    Get or create Redis client singleton.

    Returns:
        Redis client instance

    Example:
        redis_client = await get_redis_client()
        await redis_client.set("key", "value")
        value = await redis_client.get("key")
    """
    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.redis_connection_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50,  # Connection pool size
                socket_keepalive=True,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )

            # Test connection
            await _redis_client.ping()
            logger.info(f"Redis client connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ConnectionError(f"Redis connection failed: {e}")

    return _redis_client


async def close_redis():
    """
    Close Redis connection.

    Should be called on application shutdown.
    """
    global _redis_client

    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
        finally:
            _redis_client = None


async def check_redis_connection() -> bool:
    """
    Check if Redis connection is working.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        client = await get_redis_client()
        await client.ping()
        logger.info("Redis connection check: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Redis connection check: FAILED - {e}")
        return False
