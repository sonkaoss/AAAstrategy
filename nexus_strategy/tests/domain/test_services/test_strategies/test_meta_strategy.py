"""Tests for MetaStrategy (Signal Fusion Engine)."""
from __future__ import annotations

from datetime import datetime, timezone
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
from nexus_strategy.domain.models.signal import ExitLayer, ExitSignal, Signal
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy
from nexus_strategy.domain.services.strategies.meta_strategy import MetaStrategy


# ---------------------------------------------------------------------------
# Mock strategy
# ---------------------------------------------------------------------------


class _MockStrategy(BaseStrategy):
    """Lightweight mock strategy for testing MetaStrategy fusion."""

    def __init__(
        self,
        name: str,
        regimes: list[SynthesizedRegime],
        signal: Signal | None = None,
        exit_signal: ExitSignal | None = None,
    ) -> None:
        super().__init__(name, regimes)
        self._signal = signal
        self._exit_signal = exit_signal

    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:
        return self._signal or self._no_signal(pair)

    def generate_exit_signal(
        self,
        pair: str,
        market_state: MarketState,
        entry_price: float,
        pnl: float,
    ) -> ExitSignal:
        return self._exit_signal or self._no_exit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BULL = SynthesizedRegime.REGIME_STRONG_BULL
_BEAR = SynthesizedRegime.REGIME_STRONG_BEAR
_RANGE = SynthesizedRegime.REGIME_RANGING_TIGHT


def _make_regime(
    synthesized: SynthesizedRegime = _BULL,
) -> CompositeRegime:
    return CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=70,
        duration_candles=5,
        transition_probability=0.0,
        recommended_strategies=[],
        risk_multiplier=1.0,
        max_position_size=0.1,
        timestamp=datetime.now(timezone.utc),
    )


def _make_market_state(
    synthesized: SynthesizedRegime = _BULL,
    strategy_weights: dict | None = None,
    indicator_reliability: dict | None = None,
) -> MarketState:
    regime = _make_regime(synthesized)
    return MarketState(
        timestamp=datetime.now(timezone.utc),
        indicators={},
        composite_indicators={},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=False,
        sentinel={"key": "value"},
        sentinel_connected=True,
        sentinel_data_age_seconds=0,
        btc_price=50000.0,
        btc_change_1h=0.5,
        btc_change_24h=1.0,
        btc_above_ema200=True,
        btc_trend="bullish",
        market_phase="FULL_BULL",
        altcoin_season_index=60,
        fear_greed=55,
        indicator_weights={},
        strategy_weights=strategy_weights or {},
        indicator_reliability=indicator_reliability or {},
    )


def _make_signal(
    pair: str = "BTC/USDT",
    name: str = "MockA",
    confidence: int = 70,
    stop_loss: float = 49000.0,
    take_profits: list[dict] | None = None,
) -> Signal:
    return Signal(
        pair=pair,
        strategy_name=name,
        action="BUY",
        confidence=confidence,
        entry_price=50000.0,
        stop_loss=stop_loss,
        take_profit_levels=take_profits or [{"price": 51000.0, "pct": 0.5}],
        indicators_used=["RSI"],
        reasoning="test",
        timestamp=datetime.now(timezone.utc),
    )


def _make_exit(urgency: int = 80, should_exit: bool = True) -> ExitSignal:
    return ExitSignal(
        should_exit=should_exit,
        urgency=urgency,
        exit_layer=ExitLayer.TECHNICAL,
        partial_pct=1.0,
        reason="test exit",
        timestamp=datetime.now(timezone.utc),
    )


def _mock_config() -> MagicMock:
    return MagicMock()


def _build_meta(strategies: list[BaseStrategy]) -> MetaStrategy:
    return MetaStrategy(strategies=strategies, config=_mock_config())


# ---------------------------------------------------------------------------
# Tests — fuse
# ---------------------------------------------------------------------------


class TestFuseSingleStrongBuy:
    """Single strategy with high confidence — consensus_count == 1, multiplier 0.3."""

    def test_fuse_single_strong_buy(self) -> None:
        sig = _make_signal(confidence=90, name="A")
        strat = _MockStrategy("A", [_BULL], signal=sig)
        meta = _build_meta([strat])
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # single strategy with conf 90 > 85 → multiplier 0.3
        # composite = int(90 * 0.3) = 27 → REJECT
        assert bundle.composite_score == 27
        assert bundle.action == "REJECT"
        assert bundle.consensus_count == 1


class TestFuseMultipleStrategiesBuy:
    """Three strategies with good confidence → consensus 1.0 → BUY."""

    def test_fuse_multiple_strategies_buy(self) -> None:
        sigs = [
            _make_signal(confidence=70, name="A"),
            _make_signal(confidence=80, name="B"),
            _make_signal(confidence=75, name="C"),
        ]
        strats = [
            _MockStrategy(n, [_BULL], signal=s) for n, s in zip(["A", "B", "C"], sigs)
        ]
        meta = _build_meta(strats)
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # mean([70, 80, 75]) = 75 * 1.0 = 75 → BUY
        assert bundle.composite_score == 75
        assert bundle.action == "BUY"
        assert bundle.consensus_count == 3
        assert bundle.consensus_total == 3


class TestFuseStrongConsensus:
    """Five or more strategies → 1.3 multiplier."""

    def test_fuse_strong_consensus(self) -> None:
        names = ["A", "B", "C", "D", "E"]
        sigs = [_make_signal(confidence=60, name=n) for n in names]
        strats = [_MockStrategy(n, [_BULL], signal=s) for n, s in zip(names, sigs)]
        meta = _build_meta(strats)
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # mean = 60, * 1.3 = 78 → BUY
        assert bundle.composite_score == 78
        assert bundle.action == "BUY"
        assert bundle.consensus_count == 5
        assert bundle.suggested_stake_multiplier == 1.3


class TestFuseAllFilteredReject:
    """All strategies produce confidence < 40 → REJECT with composite 0."""

    def test_fuse_all_filtered_reject(self) -> None:
        sig = _make_signal(confidence=30, name="A")
        strat = _MockStrategy("A", [_BULL], signal=sig)
        meta = _build_meta([strat])
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        assert bundle.composite_score == 0
        assert bundle.action == "REJECT"
        assert bundle.consensus_count == 0


class TestFuseRegimeFiltersInactive:
    """Strategies not active for the current regime are excluded."""

    def test_fuse_regime_filters_inactive(self) -> None:
        sig = _make_signal(confidence=90, name="A")
        # Strategy only active in BEAR regime, but market is BULL
        strat = _MockStrategy("A", [_BEAR], signal=sig)
        meta = _build_meta([strat])
        ms = _make_market_state(synthesized=_BULL)

        bundle = meta.fuse("BTC/USDT", ms)

        assert bundle.composite_score == 0
        assert bundle.action == "REJECT"
        # No strategies were active, so consensus_total falls back to len(strategies)
        assert bundle.consensus_total == 1
        assert bundle.consensus_count == 0


class TestFuseNoStrategiesReject:
    """Empty strategy list → REJECT."""

    def test_fuse_no_strategies_reject(self) -> None:
        meta = _build_meta([])
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        assert bundle.composite_score == 0
        assert bundle.action == "REJECT"
        assert bundle.consensus_count == 0
        assert bundle.consensus_total == 0


class TestFuseWeightedScoring:
    """Custom strategy_weights and indicator_reliability affect composite."""

    def test_fuse_weighted_scoring(self) -> None:
        sig = _make_signal(confidence=80, name="A")
        strat = _MockStrategy("A", [_BULL], signal=sig)

        # 3 strategies total but only 1 produces a signal > 40
        sig_low = _make_signal(confidence=30, name="B")
        sig_low2 = _make_signal(confidence=30, name="C")
        strats = [
            strat,
            _MockStrategy("B", [_BULL], signal=sig_low),
            _MockStrategy("C", [_BULL], signal=sig_low2),
        ]
        meta = _build_meta(strats)
        ms = _make_market_state(
            strategy_weights={"A": {"regime_weight": 1.5}},
            indicator_reliability={"A": 0.8},
        )

        bundle = meta.fuse("BTC/USDT", ms)

        # weighted_score for A = 80 * 1.5 * 0.8 = 96.0
        # consensus_count = 1, highest conf = 80 (not > 85) → multiplier 0.0
        # composite = int(96.0 * 0.0) = 0
        assert bundle.composite_score == 0
        assert bundle.action == "REJECT"


class TestFuseStopLossMerged:
    """Weighted average of stop losses from buy signals."""

    def test_fuse_stop_loss_merged(self) -> None:
        sig_a = _make_signal(confidence=70, name="A", stop_loss=49000.0)
        sig_b = _make_signal(confidence=80, name="B", stop_loss=48000.0)
        sig_c = _make_signal(confidence=50, name="C", stop_loss=47000.0)
        strats = [
            _MockStrategy("A", [_BULL], signal=sig_a),
            _MockStrategy("B", [_BULL], signal=sig_b),
            _MockStrategy("C", [_BULL], signal=sig_c),
        ]
        meta = _build_meta(strats)
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # Weighted avg: (49000*70 + 48000*80 + 47000*50) / (70+80+50)
        expected = (49000 * 70 + 48000 * 80 + 47000 * 50) / (70 + 80 + 50)
        assert abs(bundle.weighted_stop_loss - expected) < 0.01


class TestFuseRiskRatingLow:
    """composite > 75 → LOW risk."""

    def test_fuse_risk_rating_low(self) -> None:
        names = ["A", "B", "C", "D", "E"]
        sigs = [_make_signal(confidence=65, name=n) for n in names]
        strats = [_MockStrategy(n, [_BULL], signal=s) for n, s in zip(names, sigs)]
        meta = _build_meta(strats)
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # mean=65 * 1.3 = 84.5 → int = 84 → LOW
        assert bundle.composite_score == 84
        assert bundle.risk_rating == "LOW"


class TestFuseRiskRatingMedium:
    """composite > 55 but <= 75 → MEDIUM risk."""

    def test_fuse_risk_rating_medium(self) -> None:
        sigs = [
            _make_signal(confidence=70, name="A"),
            _make_signal(confidence=65, name="B"),
            _make_signal(confidence=60, name="C"),
        ]
        strats = [
            _MockStrategy(n, [_BULL], signal=s)
            for n, s in zip(["A", "B", "C"], sigs)
        ]
        meta = _build_meta(strats)
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # mean([70,65,60]) = 65 * 1.0 = 65 → MEDIUM
        assert bundle.composite_score == 65
        assert bundle.risk_rating == "MEDIUM"


class TestFuseRiskRatingHigh:
    """composite <= 55 → HIGH risk."""

    def test_fuse_risk_rating_high(self) -> None:
        sig = _make_signal(confidence=90, name="A")
        strat = _MockStrategy("A", [_BULL], signal=sig)
        meta = _build_meta([strat])
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # single high conf → 0.3 multiplier → 27 → HIGH
        assert bundle.risk_rating == "HIGH"


class TestFuseCompositeClamped:
    """Composite score is clamped to 0-100."""

    def test_fuse_composite_clamped_0_100(self) -> None:
        # Make extremely high weighted scores
        names = ["A", "B", "C", "D", "E"]
        sigs = [_make_signal(confidence=95, name=n) for n in names]
        strats = [_MockStrategy(n, [_BULL], signal=s) for n, s in zip(names, sigs)]
        meta = _build_meta(strats)
        ms = _make_market_state(
            strategy_weights={n: {"regime_weight": 2.0} for n in names},
            indicator_reliability={n: 2.0 for n in names},
        )

        bundle = meta.fuse("BTC/USDT", ms)

        # 95 * 2.0 * 2.0 = 380 * 1.3 = 494 → clamped to 100
        assert bundle.composite_score == 100
        assert bundle.action == "BUY"


class TestFuseSingleHighConf:
    """Single strategy with conf > 85 → single multiplier 0.3."""

    def test_fuse_single_high_conf(self) -> None:
        sig = _make_signal(confidence=90, name="A")
        strat = _MockStrategy("A", [_BULL], signal=sig)
        meta = _build_meta([strat])
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # 90 * 0.3 = 27
        assert bundle.composite_score == 27
        assert bundle.consensus_count == 1


class TestFuseSingleLowConfReject:
    """Single strategy with conf <= 85 → multiplier 0.0 → REJECT."""

    def test_fuse_single_low_conf_reject(self) -> None:
        sig = _make_signal(confidence=60, name="A")
        strat = _MockStrategy("A", [_BULL], signal=sig)
        meta = _build_meta([strat])
        ms = _make_market_state()

        bundle = meta.fuse("BTC/USDT", ms)

        # 60 * 0.0 = 0 → REJECT
        assert bundle.composite_score == 0
        assert bundle.action == "REJECT"


# ---------------------------------------------------------------------------
# Tests — generate_all_exit_signals
# ---------------------------------------------------------------------------


class TestGenerateAllExitSignals:
    """Three strategies, two produce exits → sorted by urgency descending."""

    def test_generate_all_exit_signals(self) -> None:
        exit_a = _make_exit(urgency=60)
        exit_b = _make_exit(urgency=90)
        strats = [
            _MockStrategy("A", [_BULL], exit_signal=exit_a),
            _MockStrategy("B", [_BULL], exit_signal=exit_b),
            _MockStrategy("C", [_BULL]),  # no exit
        ]
        meta = _build_meta(strats)
        ms = _make_market_state()

        exits = meta.generate_all_exit_signals("BTC/USDT", ms, 50000.0, 2.0)

        assert len(exits) == 2
        assert exits[0].urgency == 90
        assert exits[1].urgency == 60


class TestGenerateAllExitSignalsEmpty:
    """No strategies produce exits → empty list."""

    def test_generate_all_exit_signals_empty(self) -> None:
        strats = [
            _MockStrategy("A", [_BULL]),
            _MockStrategy("B", [_BULL]),
        ]
        meta = _build_meta(strats)
        ms = _make_market_state()

        exits = meta.generate_all_exit_signals("BTC/USDT", ms, 50000.0, 2.0)

        assert exits == []


class TestGenerateAllExitSignalsRegimeFilter:
    """Inactive strategies are excluded from exit signal generation."""

    def test_generate_all_exit_signals_regime_filter(self) -> None:
        exit_a = _make_exit(urgency=80)
        strats = [
            _MockStrategy("A", [_BEAR], exit_signal=exit_a),  # inactive for BULL
            _MockStrategy("B", [_BULL]),  # active, no exit
        ]
        meta = _build_meta(strats)
        ms = _make_market_state(synthesized=_BULL)

        exits = meta.generate_all_exit_signals("BTC/USDT", ms, 50000.0, 2.0)

        assert exits == []
