"""MetaStrategy — Signal Fusion Engine for the Nexus trading system.

Aggregates signals from multiple sub-strategies into a single
:class:`SignalBundle` decision, applying regime filtering, weighting,
and consensus logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import TYPE_CHECKING

from nexus_strategy.domain.models.signal import ExitSignal, Signal, SignalBundle
from nexus_strategy.domain.services.strategies.base_strategy import BaseStrategy

if TYPE_CHECKING:
    from nexus_strategy.domain.models.market_state import MarketState
    from nexus_strategy.domain.ports.config_port import IConfigProvider


class MetaStrategy:
    """Fuses signals from all registered sub-strategies into a single bundle."""

    def __init__(
        self,
        strategies: list[BaseStrategy],
        config: IConfigProvider,
    ) -> None:
        self._strategies = strategies
        self._config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fuse(self, pair: str, market_state: MarketState) -> SignalBundle:
        """Run every active strategy, weight and fuse signals into a bundle."""

        current_regime = market_state.regime.synthesized

        # ---- 1. Filter phase ----
        active_count = 0
        buy_signals: list[Signal] = []

        for strategy in self._strategies:
            if not strategy.is_active_for_regime(current_regime):
                continue
            active_count += 1
            signal = strategy.generate_signal(pair, market_state)
            if signal.confidence >= 40:
                buy_signals.append(signal)

        # ---- 2. Weighting phase ----
        weighted_scores: list[float] = []
        for signal in buy_signals:
            regime_weight = (
                market_state.strategy_weights
                .get(signal.strategy_name, {})
                .get("regime_weight", 1.0)
            )
            perf_weight = market_state.indicator_reliability.get(
                signal.strategy_name, 1.0,
            )
            weighted_scores.append(signal.confidence * regime_weight * perf_weight)

        # ---- 3. Consensus phase ----
        consensus_count = len(buy_signals)
        consensus_total = active_count if active_count > 0 else len(self._strategies)

        if consensus_count >= 5:
            consensus_multiplier = 1.3
        elif consensus_count >= 3:
            consensus_multiplier = 1.0
        elif consensus_count == 2:
            consensus_multiplier = 0.6
        elif consensus_count == 1:
            highest_conf = max(s.confidence for s in buy_signals)
            consensus_multiplier = 0.3 if highest_conf > 85 else 0.0
        else:
            consensus_multiplier = 0.0

        # ---- 4. Composite score ----
        if not weighted_scores:
            composite = 0
        else:
            composite = int(mean(weighted_scores) * consensus_multiplier)
        composite = max(0, min(100, composite))

        # ---- 5. Decision ----
        action = "BUY" if composite >= 55 else "REJECT"

        # ---- 6. Build SignalBundle ----
        merged_stop = self._merge_stop_losses(buy_signals)
        merged_tps = self._merge_take_profits(buy_signals)

        if composite > 75:
            risk_rating = "LOW"
        elif composite > 55:
            risk_rating = "MEDIUM"
        else:
            risk_rating = "HIGH"

        if consensus_count >= 5:
            stake_multiplier = 1.3
        elif consensus_count >= 3:
            stake_multiplier = 1.0
        elif consensus_count == 2:
            stake_multiplier = 0.6
        else:
            stake_multiplier = 0.3

        reasoning = (
            f"MetaStrategy fuse: {consensus_count}/{consensus_total} strategies "
            f"agreed | composite={composite} | action={action} | "
            f"risk={risk_rating}"
        )

        return SignalBundle(
            action=action,
            pair=pair,
            composite_score=composite,
            consensus_count=consensus_count,
            consensus_total=consensus_total,
            source_signals=buy_signals,
            regime=market_state.regime.synthesized,
            suggested_stake_multiplier=stake_multiplier,
            weighted_stop_loss=merged_stop,
            merged_take_profits=merged_tps,
            risk_rating=risk_rating,
            reasoning=reasoning,
            sentinel_context=market_state.sentinel,
            expiry_candles=6,
            created_at=datetime.now(timezone.utc),
        )

    def generate_all_exit_signals(
        self,
        pair: str,
        market_state: MarketState,
        entry_price: float,
        current_pnl_pct: float,
    ) -> list[ExitSignal]:
        """Collect exit signals from all active strategies, sorted by urgency."""

        current_regime = market_state.regime.synthesized
        exits: list[ExitSignal] = []

        for strategy in self._strategies:
            if not strategy.is_active_for_regime(current_regime):
                continue
            exit_signal = strategy.generate_exit_signal(
                pair, market_state, entry_price, current_pnl_pct,
            )
            if exit_signal.should_exit:
                exits.append(exit_signal)

        exits.sort(key=lambda e: e.urgency, reverse=True)
        return exits

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_stop_losses(signals: list[Signal]) -> float:
        """Weighted average of stop losses (weighted by confidence)."""
        if not signals:
            return 0.0
        total_conf = sum(s.confidence for s in signals)
        if total_conf == 0:
            return 0.0
        return sum(s.stop_loss * s.confidence for s in signals) / total_conf

    @staticmethod
    def _merge_take_profits(signals: list[Signal]) -> list[dict]:
        """Collect and deduplicate all TP levels from buy signals."""
        seen: set[float] = set()
        merged: list[dict] = []
        for signal in signals:
            for tp in signal.take_profit_levels:
                price = tp.get("price", 0.0)
                if price not in seen:
                    seen.add(price)
                    merged.append(tp)
        return merged
