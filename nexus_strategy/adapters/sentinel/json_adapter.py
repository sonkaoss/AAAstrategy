"""JSON Sentinel Adapter — fallback ISentinelProvider.

Reads sentinel data from a JSON file on disk.  Used when Redis is unavailable.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from nexus_strategy.domain.ports.sentinel_port import ISentinelProvider


class JsonSentinelAdapter(ISentinelProvider):
    """Fallback sentinel adapter that reads from a local JSON file."""

    def __init__(self, json_path: str | Path) -> None:
        self._path = Path(json_path)
        self._logger = logging.getLogger("nexus.sentinel.json")

    # ------------------------------------------------------------------
    # ISentinelProvider
    # ------------------------------------------------------------------

    def get_sentinel_data(self) -> dict[str, Any]:
        """Read and return entire sentinel JSON data.

        Returns an empty dict if the file is missing or contains invalid JSON.
        """
        try:
            with open(self._path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def is_connected(self) -> bool:
        """Return True if the file exists and was modified in the last 600 s."""
        if not self._path.exists():
            return False
        age = time.time() - self._path.stat().st_mtime
        return age < 600

    def get_risk_score(self) -> int:
        """Return risk_score from sentinel data, default 50."""
        data = self.get_sentinel_data()
        return int(data.get("risk_score", 50))

    def get_strategy_mode(self) -> str:
        """Return strategy_mode from sentinel data, default 'NORMAL'."""
        data = self.get_sentinel_data()
        return str(data.get("strategy_mode", "NORMAL"))

    def get_data_age_seconds(self) -> int:
        """Return seconds since the JSON file was last modified.

        Returns 9999 if the file does not exist.
        """
        if not self._path.exists():
            return 9999
        return int(time.time() - self._path.stat().st_mtime)
