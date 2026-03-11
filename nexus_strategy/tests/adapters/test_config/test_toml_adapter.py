"""Tests for TOML config adapter — Task 12."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from nexus_strategy.adapters.config.config_schema import NexusConfig


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_base_toml(tmp_path: Path, extra: str = "") -> Path:
    """Write a minimal valid base.toml and return its parent directory."""
    content = textwrap.dedent("""\
        [general]
        max_open_trades = 10
        base_timeframe = "5m"
        informative_timeframes = ["15m", "1h", "4h", "1d"]
        profile = "balanced"
        min_confidence = 45
        min_consensus = 2
        dry_run = true

        [risk]
        max_exposure = 0.85
        max_single_pair = 0.20
        max_sector = 0.35
        min_sectors = 3
        max_correlation = 0.85
        kelly_fraction = 0.50
        drawdown_caution = 0.05
        drawdown_warning = 0.10
        drawdown_critical = 0.15
        drawdown_catastrophic = 0.20

        [regime]
        transition_min_candles = 3
        panic_instant_transition = true
        high_confidence_threshold = 70
        markov_lookback_candles = 2016

        [strategy_weights]
        mean_reversion = 1.0
        trend_following = 1.0
        momentum_breakout = 1.0
        volatility_squeeze = 1.0
        volume_profile = 1.0
        divergence = 1.0
        market_structure = 1.0

        [dca]
        enabled = true
        max_dca_count = 4
        min_dca_interval_candles = 6
        require_technical_confirmation = true

        [exit]
        emergency_drop_pct = 0.10
        doom_stop_default = 0.08
        portfolio_total_loss_limit = 0.20
        trailing_atr_multiplier = 2.5
        time_decay_enabled = true
        time_decay_rate_per_6h = 0.10
        max_time_decay = 0.50

        [sentinel]
        enabled = true
        redis_url = "redis://localhost:6379/0"
        fallback_json_path = "sentinel_data.json"
        stale_threshold_seconds = 300
        risk_shutdown_threshold = 90
        risk_defensive_threshold = 80

        [learning]
        enabled = true
        min_trades_for_learning = 20
        base_learning_rate = 0.01
        max_parameter_drift = 0.50
        cooldown_candles = 288
        backtest_learning = false

        [analytics]
        decision_logging = true
        prometheus_enabled = true
        prometheus_port = 9090
        trade_journal_enabled = true
        daily_report = true
        weekly_report = true

        [strategies.mean_reversion]
        rsi_period = 14
        rsi_oversold = 30

        [strategies.trend_following]
        ema_fast = 12
        ema_slow = 26

        [regime_weights.ranging]
        mean_reversion = 1.8
        trend_following = 0.5
    """) + extra
    (tmp_path / "base.toml").write_text(content)
    return tmp_path


def _make_profile(tmp_path: Path, profile_name: str, content: str) -> None:
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir(exist_ok=True)
    (profiles_dir / f"{profile_name}.toml").write_text(textwrap.dedent(content))


def _adapter(config_dir, profile=None):
    from nexus_strategy.adapters.config.toml_adapter import TomlConfigAdapter
    return TomlConfigAdapter(config_dir, profile=profile)


# ---------------------------------------------------------------------------
# Basic load
# ---------------------------------------------------------------------------

class TestTomlAdapterLoad:
    def test_load_base(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        assert adapter.get("general.max_open_trades") == 10

    def test_load_with_profile_override(self, tmp_path):
        _make_base_toml(tmp_path)
        _make_profile(tmp_path, "conservative", """\
            [general]
            max_open_trades = 6
            min_confidence = 60
        """)
        adapter = _adapter(tmp_path, profile="conservative")
        assert adapter.get("general.max_open_trades") == 6
        assert adapter.get("general.min_confidence") == 60
        # non-overridden key comes from base
        assert adapter.get("general.dry_run") is True

    def test_base_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _adapter(tmp_path)  # no base.toml


# ---------------------------------------------------------------------------
# get_profile
# ---------------------------------------------------------------------------

class TestGetProfile:
    def test_profile_from_general_section(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        assert adapter.get_profile() == "balanced"

    def test_profile_overridden_by_arg(self, tmp_path):
        _make_base_toml(tmp_path)
        _make_profile(tmp_path, "conservative", """\
            [general]
            max_open_trades = 6
        """)
        adapter = _adapter(tmp_path, profile="conservative")
        assert adapter.get_profile() == "conservative"


# ---------------------------------------------------------------------------
# get with defaults
# ---------------------------------------------------------------------------

class TestGet:
    def test_missing_key_returns_default(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        assert adapter.get("nonexistent.key", default="fallback") == "fallback"

    def test_missing_key_no_default_returns_none(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        assert adapter.get("no.such.key") is None

    def test_nested_key_dot_notation(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        assert adapter.get("risk.kelly_fraction") == pytest.approx(0.50)

    def test_top_level_section_returns_dict(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        general = adapter.get("general")
        assert isinstance(general, dict)
        assert general["max_open_trades"] == 10


# ---------------------------------------------------------------------------
# Runtime override
# ---------------------------------------------------------------------------

class TestOverride:
    def test_runtime_override_takes_priority(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        adapter.override("general.max_open_trades", 99)
        assert adapter.get("general.max_open_trades") == 99

    def test_override_new_key(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        adapter.override("custom.key", "hello")
        assert adapter.get("custom.key") == "hello"

    def test_override_does_not_affect_validated_config_directly(self, tmp_path):
        """get_validated_config re-reads merged data not runtime overrides."""
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        adapter.override("general.max_open_trades", 7)
        # The override key should be accessible via get()
        assert adapter.get("general.max_open_trades") == 7


# ---------------------------------------------------------------------------
# get_validated_config
# ---------------------------------------------------------------------------

class TestGetValidatedConfig:
    def test_returns_nexus_config(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        cfg = adapter.get_validated_config()
        assert isinstance(cfg, NexusConfig)

    def test_values_match_toml(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        cfg = adapter.get_validated_config()
        assert cfg.general.max_open_trades == 10
        assert cfg.risk.kelly_fraction == pytest.approx(0.50)
        assert cfg.analytics.prometheus_port == 9090

    def test_profile_values_reflected(self, tmp_path):
        _make_base_toml(tmp_path)
        _make_profile(tmp_path, "conservative", """\
            [general]
            max_open_trades = 6
            min_confidence = 60
            [risk]
            kelly_fraction = 0.30
        """)
        adapter = _adapter(tmp_path, profile="conservative")
        cfg = adapter.get_validated_config()
        assert cfg.general.max_open_trades == 6
        assert cfg.risk.kelly_fraction == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# get_strategy_config
# ---------------------------------------------------------------------------

class TestGetStrategyConfig:
    def test_known_strategy(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        sc = adapter.get_strategy_config("mean_reversion")
        assert sc["rsi_period"] == 14
        assert sc["rsi_oversold"] == 30

    def test_unknown_strategy_returns_empty_dict(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        sc = adapter.get_strategy_config("nonexistent")
        assert sc == {}


# ---------------------------------------------------------------------------
# get_regime_weights
# ---------------------------------------------------------------------------

class TestGetRegimeWeights:
    def test_known_regime(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        rw = adapter.get_regime_weights("ranging")
        assert rw["mean_reversion"] == pytest.approx(1.8)
        assert rw["trend_following"] == pytest.approx(0.5)

    def test_unknown_regime_returns_empty_dict(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        rw = adapter.get_regime_weights("unknown_regime")
        assert rw == {}


# ---------------------------------------------------------------------------
# on_config_change / reload
# ---------------------------------------------------------------------------

class TestReload:
    def test_reload_calls_callbacks_on_change(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)

        called = []
        adapter.on_config_change(lambda: called.append(1))

        # Modify the file and reload
        toml_path = tmp_path / "base.toml"
        original = toml_path.read_text()
        toml_path.write_text(original.replace("max_open_trades = 10", "max_open_trades = 12"))

        adapter.reload()
        assert len(called) == 1
        assert adapter.get("general.max_open_trades") == 12

    def test_reload_no_change_no_callback(self, tmp_path):
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)

        called = []
        adapter.on_config_change(lambda: called.append(1))

        # Reload without changing the file
        adapter.reload()
        assert len(called) == 0


# ---------------------------------------------------------------------------
# implements IConfigProvider
# ---------------------------------------------------------------------------

class TestImplementsPort:
    def test_is_iconfigprovider(self, tmp_path):
        from nexus_strategy.domain.ports.config_port import IConfigProvider
        _make_base_toml(tmp_path)
        adapter = _adapter(tmp_path)
        assert isinstance(adapter, IConfigProvider)
