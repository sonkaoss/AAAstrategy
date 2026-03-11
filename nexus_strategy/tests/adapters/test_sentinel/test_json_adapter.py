"""Tests for JsonSentinelAdapter — JSON fallback ISentinelProvider."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from nexus_strategy.adapters.sentinel.json_adapter import JsonSentinelAdapter
from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data))


# ---------------------------------------------------------------------------
# get_sentinel_data
# ---------------------------------------------------------------------------

class TestGetSentinelData:
    def test_get_sentinel_data_valid(self, tmp_path):
        sentinel_file = tmp_path / "sentinel.json"
        payload = {"risk_score": 42, "strategy_mode": "AGGRESSIVE"}
        _write_json(sentinel_file, payload)

        adapter = JsonSentinelAdapter(sentinel_file)
        assert adapter.get_sentinel_data() == payload

    def test_get_sentinel_data_missing_file(self, tmp_path):
        adapter = JsonSentinelAdapter(tmp_path / "nonexistent.json")
        assert adapter.get_sentinel_data() == {}

    def test_get_sentinel_data_corrupt_json(self, tmp_path):
        sentinel_file = tmp_path / "sentinel.json"
        sentinel_file.write_text("{ not valid json !!!")

        adapter = JsonSentinelAdapter(sentinel_file)
        assert adapter.get_sentinel_data() == {}


# ---------------------------------------------------------------------------
# is_connected
# ---------------------------------------------------------------------------

class TestIsConnected:
    def test_is_connected_recent_file(self, tmp_path):
        sentinel_file = tmp_path / "sentinel.json"
        _write_json(sentinel_file, {})

        adapter = JsonSentinelAdapter(sentinel_file)
        assert adapter.is_connected() is True

    def test_is_connected_missing_file(self, tmp_path):
        adapter = JsonSentinelAdapter(tmp_path / "missing.json")
        assert adapter.is_connected() is False


# ---------------------------------------------------------------------------
# get_risk_score
# ---------------------------------------------------------------------------

class TestGetRiskScore:
    def test_get_risk_score_from_data(self, tmp_path):
        sentinel_file = tmp_path / "sentinel.json"
        _write_json(sentinel_file, {"risk_score": 75})

        adapter = JsonSentinelAdapter(sentinel_file)
        assert adapter.get_risk_score() == 75

    def test_get_risk_score_default(self, tmp_path):
        sentinel_file = tmp_path / "sentinel.json"
        _write_json(sentinel_file, {})  # no risk_score key

        adapter = JsonSentinelAdapter(sentinel_file)
        assert adapter.get_risk_score() == 50

    def test_get_risk_score_default_missing_file(self, tmp_path):
        adapter = JsonSentinelAdapter(tmp_path / "missing.json")
        assert adapter.get_risk_score() == 50


# ---------------------------------------------------------------------------
# get_strategy_mode
# ---------------------------------------------------------------------------

class TestGetStrategyMode:
    def test_get_strategy_mode_from_data(self, tmp_path):
        sentinel_file = tmp_path / "sentinel.json"
        _write_json(sentinel_file, {"strategy_mode": "DEFENSIVE"})

        adapter = JsonSentinelAdapter(sentinel_file)
        assert adapter.get_strategy_mode() == "DEFENSIVE"

    def test_get_strategy_mode_default(self, tmp_path):
        sentinel_file = tmp_path / "sentinel.json"
        _write_json(sentinel_file, {})  # no strategy_mode key

        adapter = JsonSentinelAdapter(sentinel_file)
        assert adapter.get_strategy_mode() == "NORMAL"

    def test_get_strategy_mode_default_missing_file(self, tmp_path):
        adapter = JsonSentinelAdapter(tmp_path / "missing.json")
        assert adapter.get_strategy_mode() == "NORMAL"


# ---------------------------------------------------------------------------
# get_data_age_seconds
# ---------------------------------------------------------------------------

class TestGetDataAge:
    def test_get_data_age_fresh_file(self, tmp_path):
        sentinel_file = tmp_path / "sentinel.json"
        _write_json(sentinel_file, {})

        adapter = JsonSentinelAdapter(sentinel_file)
        age = adapter.get_data_age_seconds()
        assert age < 5  # file was just created

    def test_get_data_age_missing(self, tmp_path):
        adapter = JsonSentinelAdapter(tmp_path / "missing.json")
        assert adapter.get_data_age_seconds() == 9999


# ---------------------------------------------------------------------------
# Interface compliance
# ---------------------------------------------------------------------------

class TestImplementsPort:
    def test_implements_isentinel_provider(self, tmp_path):
        adapter = JsonSentinelAdapter(tmp_path / "any.json")
        assert isinstance(adapter, ISentinelProvider)
