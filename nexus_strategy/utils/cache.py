from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class TimedCache:
    """LRU cache with per-entry TTL expiry.

    Parameters
    ----------
    max_size:
        Maximum number of entries before LRU eviction occurs.
    ttl_seconds:
        Time-to-live in seconds for each entry (measured via time.monotonic).
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300.0) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        # Maps key → (value, expiry_timestamp)
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_expired(self, key: str) -> bool:
        """Return True if the key exists but its TTL has elapsed."""
        if key not in self._store:
            return False
        _, expiry = self._store[key]
        return time.monotonic() >= expiry

    def _evict_expired(self, key: str) -> None:
        """Remove a specific key if it has expired."""
        if self._is_expired(key):
            del self._store[key]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the cached value or *default* if missing / expired."""
        self._evict_expired(key)
        if key not in self._store:
            return default
        # Move to end (most recently used)
        self._store.move_to_end(key)
        value, _ = self._store[key]
        return value

    def set(self, key: str, value: Any) -> None:
        """Cache *value* under *key*, evicting LRU entry if at capacity."""
        # If the key already exists, remove it first so we can re-insert at end
        if key in self._store:
            del self._store[key]
        elif len(self._store) >= self._max_size:
            # Evict the least-recently-used (first) entry
            self._store.popitem(last=False)
        expiry = time.monotonic() + self._ttl
        self._store[key] = (value, expiry)

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        """Return True only if the key is present and not expired."""
        self._evict_expired(key)
        return key in self._store
