"""TOML Config Adapter — Task 12.

Implements IConfigProvider using tomllib (stdlib, Python 3.11+).
Loads base.toml and optionally merges a profile override.
"""
from __future__ import annotations

import copy
import hashlib
import logging
import tomllib
from pathlib import Path
from typing import Any

from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.adapters.config.config_schema import NexusConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge *override* into *base*. Override wins on conflicts."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_toml(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def _dict_hash(d: dict) -> str:
    """Stable hash of a dict for change detection."""
    import json
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def _navigate(data: dict, key: str) -> Any:
    """Navigate a dot-separated key path through nested dicts."""
    parts = key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


class _MISSING:
    """Sentinel for missing keys (distinct from None)."""


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class TomlConfigAdapter(IConfigProvider):
    """Reads strategy config from base.toml + optional profile TOML."""

    def __init__(self, config_dir: str | Path, profile: str | None = None) -> None:
        self._config_dir = Path(config_dir)
        self._profile = profile
        self._callbacks: list[Any] = []
        self._overrides: dict[str, Any] = {}

        self._data: dict = {}
        self._data_hash: str = ""
        self._load()

    # ------------------------------------------------------------------
    # Internal loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        base_path = self._config_dir / "base.toml"
        if not base_path.exists():
            raise FileNotFoundError(f"base.toml not found in {self._config_dir}")

        data = _load_toml(base_path)

        # Merge profile if requested
        if self._profile:
            profile_path = self._config_dir / "profiles" / f"{self._profile}.toml"
            if profile_path.exists():
                profile_data = _load_toml(profile_path)
                data = _deep_merge(data, profile_data)

        self._data = data
        self._data_hash = _dict_hash(data)

    # ------------------------------------------------------------------
    # IConfigProvider
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        # Runtime overrides have highest priority
        if key in self._overrides:
            return self._overrides[key]
        result = _navigate(self._data, key)
        if result is _MISSING:
            return default
        return result

    def get_profile(self) -> str:
        if self._profile:
            return self._profile
        # Fall back to what is stored in general.profile
        return self.get("general.profile", "balanced")

    def get_strategy_config(self, strategy_name: str) -> dict[str, Any]:
        strategies = self._data.get("strategies", {})
        return dict(strategies.get(strategy_name, {}))

    def get_regime_weights(self, regime_name: str) -> dict[str, float]:
        regime_weights = self._data.get("regime_weights", {})
        return dict(regime_weights.get(regime_name, {}))

    def on_config_change(self, callback: Any) -> None:
        self._callbacks.append(callback)

    def override(self, key: str, value: Any) -> None:
        """Set a runtime override (highest priority, dot-separated key)."""
        self._overrides[key] = value

    def get_validated_config(self) -> NexusConfig:
        """Return a validated NexusConfig built from current merged data.

        Runtime overrides for dot-paths like 'general.max_open_trades' are
        applied on top of the merged TOML data before validation.
        """
        # Start with the merged TOML data (excluding non-schema sections)
        schema_sections = {
            "general", "risk", "regime", "strategy_weights",
            "dca", "exit", "sentinel", "learning", "analytics",
        }
        raw = {k: copy.deepcopy(v) for k, v in self._data.items() if k in schema_sections}

        # Apply dot-notation overrides into the raw dict
        for dot_key, value in self._overrides.items():
            parts = dot_key.split(".", 1)
            if len(parts) == 2:
                section, sub_key = parts
                if section in schema_sections:
                    raw.setdefault(section, {})[sub_key] = value

        return NexusConfig(**raw)

    def reload(self) -> None:
        """Reload config from disk; fire callbacks only if data changed."""
        old_hash = self._data_hash
        self._load()
        if self._data_hash != old_hash:
            for cb in self._callbacks:
                cb()
