from __future__ import annotations

import time

import pytest

from nexus_strategy.utils.cache import TimedCache


class TestTimedCacheBasic:
    def test_set_and_get(self):
        cache = TimedCache()
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_missing_key_returns_default(self):
        cache = TimedCache()
        assert cache.get("missing") is None
        assert cache.get("missing", 42) == 42

    def test_overwrite_key(self):
        cache = TimedCache()
        cache.set("key", "first")
        cache.set("key", "second")
        assert cache.get("key") == "second"


class TestTimedCacheTTL:
    def test_ttl_expiry(self):
        cache = TimedCache(ttl_seconds=0.1)
        cache.set("key", "value")
        assert cache.get("key") == "value"
        time.sleep(0.15)
        assert cache.get("key") is None

    def test_non_expired_still_accessible(self):
        cache = TimedCache(ttl_seconds=60.0)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_expired_not_in_contains(self):
        cache = TimedCache(ttl_seconds=0.1)
        cache.set("key", "value")
        time.sleep(0.15)
        assert "key" not in cache


class TestTimedCacheLRU:
    def test_lru_eviction(self):
        """When full, the least-recently-used entry is evicted."""
        cache = TimedCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Adding a 4th entry should evict "a" (oldest)
        cache.set("d", 4)
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_access_refreshes_lru_order(self):
        """Accessing an entry moves it to most-recently-used position."""
        cache = TimedCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Access "a" to make it recently used
        cache.get("a")
        # Adding a 4th entry should evict "b" (now the LRU)
        cache.set("d", 4)
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("d") == 4


class TestTimedCacheMeta:
    def test_clear(self):
        cache = TimedCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None

    def test_len(self):
        cache = TimedCache()
        assert len(cache) == 0
        cache.set("x", 10)
        assert len(cache) == 1
        cache.set("y", 20)
        assert len(cache) == 2

    def test_contains_present(self):
        cache = TimedCache()
        cache.set("key", "val")
        assert "key" in cache

    def test_contains_absent(self):
        cache = TimedCache()
        assert "missing" not in cache

    def test_len_after_eviction(self):
        cache = TimedCache(max_size=2)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # evicts "a"
        assert len(cache) == 2
