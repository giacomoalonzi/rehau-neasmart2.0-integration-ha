"""Caching system for Rehau Neasmart 2.0 integration."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, Optional, TypeVar

_CACHE_TTL = 10  # Cache time-to-live in seconds
T = TypeVar("T")


class CacheEntry:
    """Cache entry with value and expiration time."""

    def __init__(self, value: Any, ttl: int = _CACHE_TTL) -> None:
        """Initialize cache entry."""
        self.value = value
        self.expires_at = time.time() + ttl

    @property
    def is_valid(self) -> bool:
        """Check if cache entry is still valid."""
        return time.time() < self.expires_at


class DataCache:
    """Simple data cache with TTL support."""

    def __init__(self) -> None:
        """Initialize cache."""
        self._cache: Dict[str, CacheEntry] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create lock for a key."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable[[], T],
        ttl: int = _CACHE_TTL
    ) -> T:
        """Get value from cache or fetch if not available/expired."""
        async with self._get_lock(key):
            # Check if we have a valid cache entry
            if key in self._cache and self._cache[key].is_valid:
                return self._cache[key].value
            
            # Fetch new value
            value = await fetch_func()
            
            # Store in cache
            self._cache[key] = CacheEntry(value, ttl)
            
            return value

    def invalidate(self, key: Optional[str] = None) -> None:
        """Invalidate cache entries."""
        if key is None:
            # Clear entire cache
            self._cache.clear()
        elif key in self._cache:
            # Clear specific key
            del self._cache[key]

    def cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if current_time >= entry.expires_at
        ]
        for key in expired_keys:
            del self._cache[key] 