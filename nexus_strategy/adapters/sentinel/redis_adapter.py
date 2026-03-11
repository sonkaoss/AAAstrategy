"""Redis Sentinel Adapter — primary ISentinelProvider.

Reads sentinel data from a Redis key.  Falls back to a secondary
ISentinelProvider (e.g. JsonSentinelAdapter) when Redis is unavailable.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider


class RedisSentinelAdapter(ISentinelProvider):
    """Primary sentinel adapter backed by Redis.

    On any Redis error the adapter transparently delegates to *fallback*.
    If no fallback is provided the last successfully fetched data is used;
    if no data has ever been fetched, defaults are returned.
    """

    REDIS_KEY = "nexus:sentinel:command_channel"

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        fallback: ISentinelProvider | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._fallback = fallback
        self._client = None
        self._last_data: dict[str, Any] = {}
        self._last_fetch_time: float = 0
        self._logger = logging.getLogger("nexus.sentinel.redis")
        self._connect()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Attempt to connect to Redis; swallow all errors."""
        try:
            import redis  # optional dependency
            self._client = redis.from_url(self._redis_url, decode_responses=True)
            self._client.ping()
            self._logger.info("Connected to Redis at %s", self._redis_url)
        except Exception as exc:
            self._logger.warning(
                "Redis connection failed: %s, using fallback", exc
            )
            self._client = None

    def _fetch(self) -> dict[str, Any]:
        """Fetch sentinel data from Redis; fall back on any error."""
        if self._client is not None:
            try:
                raw = self._client.get(self.REDIS_KEY)
                if raw:
                    self._last_data = json.loads(raw)
                    self._last_fetch_time = time.time()
                    return self._last_data
            except Exception as exc:
                self._logger.warning("Redis fetch failed: %s", exc)

        # Delegate to fallback adapter if available
        if self._fallback is not None:
            return self._fallback.get_sentinel_data()

        # Last resort: cached data (may be empty dict)
        return self._last_data

    # ------------------------------------------------------------------
    # ISentinelProvider
    # ------------------------------------------------------------------

    def get_sentinel_data(self) -> dict[str, Any]:
        return self._fetch()

    def is_connected(self) -> bool:
        if self._client is not None:
            try:
                return self._client.ping()
            except Exception:
                pass
        if self._fallback is not None:
            return self._fallback.is_connected()
        return False

    def get_risk_score(self) -> int:
        data = self._fetch()
        return int(data.get("risk_score", 50))

    def get_strategy_mode(self) -> str:
        data = self._fetch()
        return str(data.get("strategy_mode", "NORMAL"))

    def get_data_age_seconds(self) -> int:
        if self._last_fetch_time > 0:
            return int(time.time() - self._last_fetch_time)
        if self._fallback is not None:
            return self._fallback.get_data_age_seconds()
        return 9999
