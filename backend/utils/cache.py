"""
Simple in-memory TTL cache.

Wraps ``cachetools.TTLCache`` with a dict-of-caches pattern so each
data source gets its own namespace and TTL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from cachetools import TTLCache

logger = logging.getLogger(__name__)


class DataCache:
    """Per-source TTL cache that also keeps the last known-good value."""

    def __init__(self, ttl: int, maxsize: int = 32):
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._fallback: dict[str, Any] = {}   # last-known-good per key
        self._timestamps: dict[str, str] = {}  # ISO timestamp of last successful fetch

    # ── public API ───────────────────────────────────────────

    def get(self, key: str = "default") -> tuple[Any | None, bool]:
        """Return ``(data, is_stale)``.

        If the TTL has expired we fall back to the last good payload and
        flag it as stale.
        """
        val = self._cache.get(key)
        if val is not None:
            return val, False

        fallback = self._fallback.get(key)
        if fallback is not None:
            logger.info("Cache miss for %s — serving stale fallback", key)
            return fallback, True

        return None, False

    def set(self, value: Any, key: str = "default") -> None:
        """Store a fresh value in both the TTL cache and the fallback."""
        self._cache[key] = value
        self._fallback[key] = value
        self._timestamps[key] = datetime.now(timezone.utc).isoformat()

    def fetched_at(self, key: str = "default") -> str | None:
        """Return the ISO timestamp of the last successful fetch."""
        return self._timestamps.get(key)
