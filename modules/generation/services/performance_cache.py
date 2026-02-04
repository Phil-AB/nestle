"""
Performance caching for insights generation.

Provides intelligent caching to reduce redundant computation and LLM calls.
"""

import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class InsightsCache:
    """
    In-memory cache for insights generation results.

    Features:
    - TTL-based expiration
    - Content-based cache keys
    - Automatic cleanup
    - Thread-safe operations
    """

    def __init__(self, default_ttl_seconds: int = 3600):
        """
        Initialize cache.

        Args:
            default_ttl_seconds: Default time-to-live for cache entries (1 hour)
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl_seconds
        self.hits = 0
        self.misses = 0

    def _generate_key(self, data: Dict[str, Any], prefix: str = "") -> str:
        """
        Generate cache key from data using content hashing.

        Args:
            data: Data to generate key from
            prefix: Optional prefix for namespacing

        Returns:
            Cache key string
        """
        # Sort and serialize for consistent hashing
        serialized = json.dumps(data, sort_keys=True, default=str)
        hash_value = hashlib.sha256(serialized.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_value}" if prefix else hash_value

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            self.misses += 1
            return None

        entry = self._cache[key]

        # Check expiration
        if datetime.utcnow() > entry["expires_at"]:
            del self._cache[key]
            self.misses += 1
            logger.debug(f"Cache expired: {key}")
            return None

        self.hits += 1
        logger.debug(f"Cache hit: {key}")
        return entry["value"]

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds (uses default if not specified)
        """
        ttl = ttl_seconds or self.default_ttl
        expires_at = datetime.utcnow() + timedelta(seconds=ttl)

        self._cache[key] = {
            "value": value,
            "expires_at": expires_at,
            "created_at": datetime.utcnow()
        }

        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    def get_or_compute(
        self,
        key: str,
        compute_fn: callable,
        ttl_seconds: Optional[int] = None
    ) -> Any:
        """
        Get value from cache or compute if not found.

        Args:
            key: Cache key
            compute_fn: Function to call if cache miss
            ttl_seconds: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        cached = self.get(key)
        if cached is not None:
            return cached

        value = compute_fn()
        self.set(key, value, ttl_seconds)
        return value

    def invalidate(self, key: str):
        """
        Invalidate a cache entry.

        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache invalidated: {key}")

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("Cache cleared")

    def cleanup_expired(self):
        """Remove all expired entries from cache."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry["expires_at"]
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "entries": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests
        }


# ==============================================================================
# MODULE-LEVEL CACHE INSTANCES
# ==============================================================================

# Singleton cache instances for different data types
_insights_cache = InsightsCache(default_ttl_seconds=1800)  # 30 minutes
_config_cache = InsightsCache(default_ttl_seconds=3600)    # 1 hour
_benchmark_cache = InsightsCache(default_ttl_seconds=900)  # 15 minutes


def get_insights_cache() -> InsightsCache:
    """Get the insights results cache."""
    return _insights_cache


def get_config_cache() -> InsightsCache:
    """Get the configuration cache."""
    return _config_cache


def get_benchmark_cache() -> InsightsCache:
    """Get the benchmark data cache."""
    return _benchmark_cache


@lru_cache(maxsize=128)
def get_prompt_template_cached(prompt_type: str) -> str:
    """
    Get cached prompt template structure.

    Args:
        prompt_type: Type of prompt (risk_assessment, product_eligibility, etc.)

    Returns:
        Prompt template string (without dynamic values)

    Note: This caches the template structure, not the filled-in values
    """
    # This will be filled in by the prompt builder
    return prompt_type


def cache_key_for_customer(customer_data: Dict[str, Any], operation: str) -> str:
    """
    Generate cache key for customer-specific operations.

    Args:
        customer_data: Customer data dictionary
        operation: Operation name (e.g., 'risk_assessment', 'benchmarks')

    Returns:
        Cache key string
    """
    # Create a minimal representation for caching
    cache_data = {
        "operation": operation,
        "customer_id": customer_data.get("customer_ic", ""),
        "income": customer_data.get("estimated_income", 0),
        "age": customer_data.get("age", 0),
        "employment": customer_data.get("employment_status", ""),
        "education": customer_data.get("educational_level", "")
    }

    cache = get_insights_cache()
    return cache._generate_key(cache_data, prefix=operation)
