"""Tests for ExitEngine — the 5-layer exit system."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.regime import (
    CompositeRegime,
    MacroRegime,
    MicroRegime,
    MidRegime,
    SynthesizedRegime,
)
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal
from nexus_strategy.domain.ports.config_port import IConfigProvider
from nexus_strategy.domain.services.exit_engine import ExitEngine

# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_config() -> IConfigProvider:
    mock = MagicMock(spec=IConfigProvider)
    mock.get.return_value = None
    return mock


def _make_regime(
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_MODERATE_BULL,
) -> CompositeRegime:
    return CompositeRegime(
        micro=MicroRegime.MICRO_RANGING,
        mid=MidRegime.RANGING_TIGHT,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=70,
        duration_candles=10,
        transition_probability=0.1,
        recommended_strategies=["momentum"],
        risk_multiplier=1.0,
        max_position_size=1.0,
        timestamp=_NOW,
    )


def _make_market_state(
    pair: str = "BTC/USDT",
    indicators_5m: dict[str, float] | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_MODERATE_BULL,
    regime_just_changed: bool = False,
    sentinel_risk: int = 0,
) -> MarketState:
    regime = _make_regime(synthesized)
    indicators: dict[str, dict[str, dict[str, float]]] = {}
    if indicators_5m is not None:
        indicators[pair] = {"5m": indicators_5m}
    return MarketState(
        timestamp=_NOW,
        indicators=indicators,
        composite_indicators={},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=regime_just_changed,
        sentinel={"risk_score": sentinel_risk},
        sentinel_connected=True,
        sentinel_data_age_seconds=0,
        btc_price=50000.0,
        btc_change_1h=0.0,
        btc_change_24h=0.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="expansion",
        altcoin_season_index=50,
        fear_greed=50,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )


def _make_exit_signal(
    urgency: int = 60,
    should_exit: bool = True,
    reason: str = "test signal",
    partial_pct: float = 0.5,
) -> ExitSignal:
    return ExitSignal(
        should_exit=should_exit,
        urgency=urgency,
        exit_layer=ExitLayer.TECHNICAL,
        partial_pct=partial_pct,
        reason=reason,
        timestamp=_NOW,
    )


def _default_portfolio() -> dict:
    return {"total_pnl_pct": 0, "drawdown_level": 0, "slots_exceeded": False}


# ------------------------------------------------------------------ #
# Layer 1 — Emergency                                                 #
# ------------------------------------------------------------------ #


class TestEmergencyLayer:
    def test_black_swan_exit(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, -11.0, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 100
        assert result.partial_pct == 1.0
        assert "Black Swan" in result.reason

    def test_doom_stop_panic(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state(synthesized=SynthesizedRegime.REGIME_PANIC)
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, -4.0, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 95
        assert result.partial_pct == 1.0
        assert "Doom stop" in result.reason
        assert "-4.0%" in result.reason

    def test_doom_stop_strong_bull(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state(synthesized=SynthesizedRegime.REGIME_STRONG_BULL)
        # -15% threshold; pnl at -15 should trigger
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, -15.0, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 95
        assert "-15.0%" in result.reason

    def test_doom_stop_moderate_bear(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state(synthesized=SynthesizedRegime.REGIME_MODERATE_BEAR)
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, -8.0, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 95
        assert "-8.0%" in result.reason

    def test_portfolio_protection(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        portfolio = {"total_pnl_pct": -21, "drawdown_level": 0}
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.0, 5, [], portfolio
        )
        assert result is not None
        assert result.urgency == 100
        assert result.partial_pct == 1.0
        assert "Portfolio protection" in result.reason or "drawdown" in result.reason.lower()


# ------------------------------------------------------------------ #
# Layer 2 — Technical                                                 #
# ------------------------------------------------------------------ #


class TestTechnicalLayer:
    def test_technical_4_signals_full_exit(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        sigs = [_make_exit_signal(urgency=60 + i) for i in range(4)]
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, sigs, _default_portfolio()
        )
        assert result is not None
        assert result.partial_pct == 1.0
        assert result.urgency == 63  # max of 60,61,62,63

    def test_technical_2_signals_partial(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        sigs = [_make_exit_signal(urgency=50), _make_exit_signal(urgency=55)]
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, sigs, _default_portfolio()
        )
        assert result is not None
        assert result.partial_pct == 0.5
        assert result.urgency == 55

    def test_technical_1_signal_partial_quarter(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        sigs = [_make_exit_signal(urgency=42)]
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, sigs, _default_portfolio()
        )
        assert result is not None
        assert result.partial_pct == 0.25
        assert result.urgency == 42

    def test_technical_no_signals_no_exit(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], _default_portfolio()
        )
        assert result is None

    def test_rsi_extreme_check(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state(indicators_5m={"RSI": 80.0})
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.reason == "RSI extreme overbought"
        assert result.urgency == 55
        assert result.partial_pct == 0.5

    def test_ema_bearish_cross(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state(
            indicators_5m={"EMA_9": 10.0, "EMA_21": 20.0, "EMA_50": 30.0}
        )
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.reason == "Triple EMA bearish cross"
        assert result.urgency == 65
        assert result.partial_pct == 0.5


# ------------------------------------------------------------------ #
# Layer 3 — Regime                                                    #
# ------------------------------------------------------------------ #


class TestRegimeLayer:
    def test_regime_change_bearish_exit(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state(
            synthesized=SynthesizedRegime.REGIME_STRONG_BEAR,
            regime_just_changed=True,
        )
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 70
        assert result.partial_pct == 0.5
        assert "Regime turned bearish" in result.reason

    def test_regime_change_neutral_no_exit(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state(
            synthesized=SynthesizedRegime.REGIME_MODERATE_BULL,
            regime_just_changed=True,
        )
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], _default_portfolio()
        )
        assert result is None

    def test_sentinel_override(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state(sentinel_risk=92)
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 80
        assert result.partial_pct == 1.0
        assert "Sentinel risk critical" in result.reason


# ------------------------------------------------------------------ #
# Layer 4 — Portfolio                                                 #
# ------------------------------------------------------------------ #


class TestPortfolioLayer:
    def test_portfolio_catastrophic_drawdown(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        portfolio = {"total_pnl_pct": 0, "drawdown_level": 4}
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], portfolio
        )
        assert result is not None
        assert result.urgency == 85
        assert result.partial_pct == 1.0
        assert "Catastrophic drawdown" in result.reason

    def test_portfolio_critical_drawdown(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        portfolio = {"total_pnl_pct": 0, "drawdown_level": 3}
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], portfolio
        )
        assert result is not None
        assert result.urgency == 70
        assert result.partial_pct == 0.5
        assert "Critical drawdown" in result.reason

    def test_portfolio_slot_exceeded(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        portfolio = {"total_pnl_pct": 0, "drawdown_level": 0, "slots_exceeded": True}
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], portfolio
        )
        assert result is not None
        assert result.urgency == 50
        assert result.partial_pct == 0.25
        assert "Position slots exceeded" in result.reason


# ------------------------------------------------------------------ #
# Layer 5 — Profit Optimizer                                          #
# ------------------------------------------------------------------ #


class TestProfitOptimizerLayer:
    def test_tp_level_4(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 8.5, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 40
        assert result.partial_pct == 0.25
        assert "TP Level 4" in result.reason

    def test_tp_level_1(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 1.5, 5, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 25
        assert result.partial_pct == 0.25
        assert "TP Level 1" in result.reason

    def test_time_decay(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 73, [], _default_portfolio()
        )
        assert result is not None
        assert result.urgency == 45
        assert result.partial_pct == 0.5
        assert "Time decay" in result.reason


# ------------------------------------------------------------------ #
# Cross-layer                                                         #
# ------------------------------------------------------------------ #


class TestCrossLayer:
    def test_no_exit_good_conditions(self) -> None:
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, 0.5, 5, [], _default_portfolio()
        )
        assert result is None

    def test_emergency_highest_priority(self) -> None:
        """When emergency and profit layers both fire, emergency wins."""
        engine = ExitEngine(_make_config())
        ms = _make_market_state()
        # pnl < -10 triggers black swan (urgency 100)
        # simultaneously portfolio catastrophic drawdown
        portfolio = {"total_pnl_pct": -25, "drawdown_level": 4}
        sigs = [_make_exit_signal(urgency=60)]
        result = engine.evaluate(
            "BTC/USDT", ms, 50000.0, -12.0, 5, sigs, portfolio
        )
        assert result is not None
        assert result.urgency == 100
        assert result.exit_layer == ExitLayer.EMERGENCY
