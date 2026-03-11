"""Tests for RedisSentinelAdapter — primary ISentinelProvider.

All tests use unittest.mock; no live Redis connection is made.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_adapter(redis_url="redis://localhost:6379/0", fallback=None, *, mock_client=None):
    """Import and instantiate RedisSentinelAdapter with _connect patched out.

    If *mock_client* is provided it is assigned to adapter._client directly.
    """
    from nexus_strategy.adapters.sentinel.redis_adapter import RedisSentinelAdapter

    with patch.object(RedisSentinelAdapter, "_connect", return_value=None):
        adapter = RedisSentinelAdapter(redis_url=redis_url, fallback=fallback)

    adapter._client = mock_client
    return adapter


# ---------------------------------------------------------------------------
# Fallback behaviour when Redis is unavailable
# ---------------------------------------------------------------------------

class TestFallbackWhenRedisUnavailable:
    def test_fallback_when_redis_unavailable(self):
        """If redis import / connection fails, _client stays None and fallback is used."""
        mock_fallback = MagicMock(spec=ISentinelProvider)
        mock_fallback.get_sentinel_data.return_value = {"risk_score": 30}

        # Simulate redis module being completely unavailable
        with patch.dict("sys.modules", {"redis": None}):
            from nexus_strategy.adapters.sentinel.redis_adapter import RedisSentinelAdapter
            adapter = RedisSentinelAdapter(fallback=mock_fallback)

        assert adapter._client is None
        data = adapter.get_sentinel_data()
        mock_fallback.get_sentinel_data.assert_called_once()
        assert data == {"risk_score": 30}

    def test_get_sentinel_data_uses_fallback(self):
        """When _client is None, get_sentinel_data delegates to fallback."""
        mock_fallback = MagicMock(spec=ISentinelProvider)
        mock_fallback.get_sentinel_data.return_value = {"strategy_mode": "SAFE"}

        adapter = _make_adapter(fallback=mock_fallback, mock_client=None)
        result = adapter.get_sentinel_data()

        mock_fallback.get_sentinel_data.assert_called_once()
        assert result == {"strategy_mode": "SAFE"}


# ---------------------------------------------------------------------------
# is_connected
# ---------------------------------------------------------------------------

class TestIsConnected:
    def test_is_connected_returns_fallback_when_no_redis(self):
        """With no Redis client, is_connected returns fallback.is_connected()."""
        mock_fallback = MagicMock(spec=ISentinelProvider)
        mock_fallback.is_connected.return_value = True

        adapter = _make_adapter(fallback=mock_fallback, mock_client=None)
        assert adapter.is_connected() is True
        mock_fallback.is_connected.assert_called_once()

    def test_is_connected_returns_false_no_fallback(self):
        """With no client and no fallback, is_connected returns False."""
        adapter = _make_adapter(mock_client=None)
        assert adapter.is_connected() is False

    def test_is_connected_uses_redis_ping(self):
        """With a live-looking client, is_connected returns ping() result."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        adapter = _make_adapter(mock_client=mock_client)
        assert adapter.is_connected() is True
        mock_client.ping.assert_called_once()


# ---------------------------------------------------------------------------
# get_risk_score
# ---------------------------------------------------------------------------

class TestGetRiskScore:
    def test_get_risk_score_default(self):
        """When no data is available, risk_score defaults to 50."""
        adapter = _make_adapter(mock_client=None)
        assert adapter.get_risk_score() == 50

    def test_get_risk_score_from_redis(self):
        """When Redis has data, risk_score is read from it."""
        mock_client = MagicMock()
        mock_client.get.return_value = json.dumps({"risk_score": 88})

        adapter = _make_adapter(mock_client=mock_client)
        assert adapter.get_risk_score() == 88


# ---------------------------------------------------------------------------
# get_strategy_mode
# ---------------------------------------------------------------------------

class TestGetStrategyMode:
    def test_get_strategy_mode_default(self):
        """When no data is available, strategy_mode defaults to 'NORMAL'."""
        adapter = _make_adapter(mock_client=None)
        assert adapter.get_strategy_mode() == "NORMAL"

    def test_get_strategy_mode_from_redis(self):
        """When Redis has data, strategy_mode is read from it."""
        mock_client = MagicMock()
        mock_client.get.return_value = json.dumps({"strategy_mode": "DEFENSIVE"})

        adapter = _make_adapter(mock_client=mock_client)
        assert adapter.get_strategy_mode() == "DEFENSIVE"


# ---------------------------------------------------------------------------
# get_data_age_seconds
# ---------------------------------------------------------------------------

class TestGetDataAge:
    def test_get_data_age_no_fetch(self):
        """When nothing has been fetched and no fallback, returns 9999."""
        adapter = _make_adapter(mock_client=None)
        assert adapter.get_data_age_seconds() == 9999

    def test_get_data_age_uses_fallback_when_no_fetch(self):
        """When nothing fetched, falls back to fallback.get_data_age_seconds()."""
        mock_fallback = MagicMock(spec=ISentinelProvider)
        mock_fallback.get_data_age_seconds.return_value = 42

        adapter = _make_adapter(fallback=mock_fallback, mock_client=None)
        assert adapter.get_data_age_seconds() == 42

    def test_get_data_age_after_fetch(self):
        """After a successful Redis fetch, age is measured from fetch time."""
        mock_client = MagicMock()
        mock_client.get.return_value = json.dumps({"risk_score": 10})

        adapter = _make_adapter(mock_client=mock_client)
        adapter.get_sentinel_data()  # triggers _fetch and sets _last_fetch_time
        age = adapter.get_data_age_seconds()
        assert 0 <= age < 5  # freshly fetched


# ---------------------------------------------------------------------------
# Interface compliance & constants
# ---------------------------------------------------------------------------

class TestImplementsPort:
    def test_implements_isentinel_provider(self):
        adapter = _make_adapter(mock_client=None)
        assert isinstance(adapter, ISentinelProvider)

    def test_redis_key_constant(self):
        from nexus_strategy.adapters.sentinel.redis_adapter import RedisSentinelAdapter
        assert RedisSentinelAdapter.REDIS_KEY == "nexus:sentinel:command_channel"
