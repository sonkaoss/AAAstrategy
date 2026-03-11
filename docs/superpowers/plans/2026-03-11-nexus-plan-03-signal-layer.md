# Nexus Strategy - Plan 3: Signal Layer (7 Sub-Strategies + Meta Fusion)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Signal Layer — 7 independent sub-strategies implementing a common BaseStrategy interface, plus the MetaStrategy fusion engine that combines their signals into a final SignalBundle.

**Architecture:** Hexagonal. All strategies are domain services. They receive a MarketState snapshot and return Signal/ExitSignal objects. No external dependencies. Each strategy is a self-contained module.

**Tech Stack:** Python 3.11+, numpy, pandas, pytest

**Spec Reference:** `docs/superpowers/specs/2026-03-11-nexus-strategy-design.md` (Section 6)
**Depends on:** Plan 1 (Foundation) + Plan 2 (Data Layer) — all models, ports, services completed

---

## File Structure (new files this plan)

```
nexus_strategy/
├── domain/
│   └── services/
│       └── strategies/
│           ├── __init__.py
│           ├── base_strategy.py            # ABC + common helpers
│           ├── mean_reversion.py           # Strategy 1
│           ├── trend_following.py          # Strategy 2
│           ├── momentum_breakout.py        # Strategy 3
│           ├── volatility_squeeze.py       # Strategy 4
│           ├── volume_profile.py           # Strategy 5
│           ├── divergence.py               # Strategy 6
│           ├── market_structure.py         # Strategy 7
│           └── meta_strategy.py            # Signal fusion engine
└── tests/
    └── domain/
        └── test_services/
            └── test_strategies/
                ├── __init__.py
                ├── test_base_strategy.py
                ├── test_mean_reversion.py
                ├── test_trend_following.py
                ├── test_momentum_breakout.py
                ├── test_volatility_squeeze.py
                ├── test_volume_profile.py
                ├── test_divergence.py
                ├── test_market_structure.py
                └── test_meta_strategy.py
```

---

## Common Context for All Tasks

**MarketState access pattern** (for all strategies):
```python
from nexus_strategy.domain.models.market_state import MarketState

# Get indicator value for a pair/timeframe:
rsi = market_state.get_indicator(pair, "5m", "RSI_14")  # returns float | None

# Access regime:
regime = market_state.regime  # CompositeRegime
regime.synthesized  # SynthesizedRegime enum
regime.confidence  # int 0-100

# Access BTC context:
market_state.btc_trend  # "bullish" | "bearish" | "neutral"
market_state.btc_above_ema200  # bool
```

**Signal model** (returned by strategies):
```python
from nexus_strategy.domain.models.signal import Signal, ExitSignal, ExitLayer, SignalBundle
from datetime import datetime, timezone

Signal(
    pair="BTC/USDT",
    strategy_name="MeanReversion",
    action="BUY",           # or "NO_SIGNAL"
    confidence=75,           # 0-100
    entry_price=50000.0,
    stop_loss=48500.0,
    take_profit_levels=[{"price": 51500.0, "pct": 0.25}, ...],
    indicators_used=["RSI_14", "BB_lower_20"],
    reasoning="RSI oversold + BB lower touch",
    timestamp=datetime.now(timezone.utc),
)

ExitSignal(
    should_exit=True,
    urgency=80,              # 0-100
    exit_layer=ExitLayer.TECHNICAL,
    partial_pct=0.5,         # 50% of position
    reason="RSI overbought",
    timestamp=datetime.now(timezone.utc),
)
```

**Test helper** — create a mock MarketState for tests:
```python
from unittest.mock import MagicMock
from nexus_strategy.domain.models.regime import (
    CompositeRegime, MicroRegime, MidRegime, MacroRegime, SynthesizedRegime
)
from datetime import datetime, timezone

def make_market_state(
    pair: str = "BTC/USDT",
    indicators_5m: dict | None = None,
    indicators_15m: dict | None = None,
    indicators_1h: dict | None = None,
    synthesized: SynthesizedRegime = SynthesizedRegime.REGIME_MODERATE_BULL,
    confidence: int = 70,
    btc_trend: str = "bullish",
) -> MarketState:
    """Build a MarketState for testing."""
    ind_5m = indicators_5m or {}
    ind_15m = indicators_15m or {}
    ind_1h = indicators_1h or {}
    regime = CompositeRegime(
        micro=MicroRegime.MICRO_TRENDING_UP,
        mid=MidRegime.TREND_BULL_STRONG,
        macro=MacroRegime.MACRO_BULL_HEALTHY,
        synthesized=synthesized,
        confidence=confidence,
        duration_candles=5,
        transition_probability=0.0,
        recommended_strategies=[],
        risk_multiplier=1.0,
        max_position_size=0.1,
        timestamp=datetime.now(timezone.utc),
    )
    return MarketState(
        timestamp=datetime.now(timezone.utc),
        indicators={pair: {"5m": ind_5m, "15m": ind_15m, "1h": ind_1h}},
        composite_indicators={},
        regime=regime,
        previous_regime=regime,
        regime_just_changed=False,
        sentinel={},
        sentinel_connected=False,
        sentinel_data_age_seconds=0,
        btc_price=50000.0,
        btc_change_1h=0.5,
        btc_change_24h=1.0,
        btc_above_ema200=True,
        btc_trend=btc_trend,
        market_phase="FULL_BULL",
        altcoin_season_index=60,
        fear_greed=55,
        indicator_weights={},
        strategy_weights={},
        indicator_reliability={},
    )
```

---

## Chunk 1: Base Strategy + Mean Reversion + Trend Following

### Task 1: Base Strategy ABC

**Files:**
- Create: `nexus_strategy/domain/services/strategies/__init__.py`
- Create: `nexus_strategy/domain/services/strategies/base_strategy.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/__init__.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_base_strategy.py`

**BaseStrategy ABC:**
```python
from abc import ABC, abstractmethod
from nexus_strategy.domain.models.market_state import MarketState
from nexus_strategy.domain.models.signal import Signal, ExitSignal
from nexus_strategy.domain.models.regime import SynthesizedRegime

class BaseStrategy(ABC):
    """Common interface for all 7 sub-strategies."""

    def __init__(self, name: str, optimal_regimes: list[SynthesizedRegime]):
        self._name = name
        self._optimal_regimes = optimal_regimes

    @property
    def name(self) -> str:
        return self._name

    @property
    def optimal_regimes(self) -> list[SynthesizedRegime]:
        return list(self._optimal_regimes)

    def is_active_for_regime(self, regime: SynthesizedRegime) -> bool:
        """Return True if this strategy should run for the given regime."""
        return regime in self._optimal_regimes

    @abstractmethod
    def generate_signal(self, pair: str, market_state: MarketState) -> Signal:
        """Generate a trading signal for the given pair."""
        ...

    @abstractmethod
    def generate_exit_signal(self, pair: str, market_state: MarketState, entry_price: float, current_pnl_pct: float) -> ExitSignal:
        """Generate an exit signal for an open position."""
        ...

    def _no_signal(self, pair: str) -> Signal:
        """Helper: return a NO_SIGNAL Signal."""
        from datetime import datetime, timezone
        return Signal(
            pair=pair,
            strategy_name=self._name,
            action="NO_SIGNAL",
            confidence=0,
            entry_price=0.0,
            stop_loss=0.0,
            take_profit_levels=[],
            indicators_used=[],
            reasoning="No signal conditions met",
            timestamp=datetime.now(timezone.utc),
        )

    def _no_exit(self) -> ExitSignal:
        """Helper: return a no-exit ExitSignal."""
        from datetime import datetime, timezone
        return ExitSignal(
            should_exit=False,
            urgency=0,
            exit_layer=ExitLayer.TECHNICAL,
            partial_pct=0.0,
            reason="",
            timestamp=datetime.now(timezone.utc),
        )

    def _get(self, market_state: MarketState, pair: str, tf: str, key: str, default: float = 0.0) -> float:
        """Shortcut to get an indicator value with default."""
        val = market_state.get_indicator(pair, tf, key)
        return val if val is not None else default
```

**Tests:** Verify ABC can't be instantiated, concrete subclass works, is_active_for_regime, _no_signal helper, _get helper.

### Task 2: Mean Reversion Strategy

**Files:**
- Create: `nexus_strategy/domain/services/strategies/mean_reversion.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_mean_reversion.py`

**MeanReversionStrategy(BaseStrategy):**
- name: "MeanReversion"
- optimal_regimes: REGIME_RANGING_TIGHT, REGIME_RANGING_WIDE, REGIME_WEAK_BEAR, REGIME_ACCUMULATION

**generate_signal logic:**
1. Get indicators: RSI_14, BB_lower_20, BB_upper_20, BB_mid_20, close, EMA_50, EMA_21, MFI_14, StochRSI_K, Volume_SMA_20, CMF_20
2. Score system (each condition adds points):
   - Oversold RSI (<30 = +25, <35 = +15, <40 = +10)
   - Close near/below BB lower (close <= BB_lower = +25, within 0.5% = +15)
   - MFI oversold (<25 = +15, <35 = +10)
   - StochRSI_K oversold (<20 = +15, <30 = +10)
   - Volume confirmation (volume > 1.5x SMA = +10)
   - CMF positive (>0 = +5, >0.1 = +10) — money flowing in
   - 15m RSI also oversold (<35 = +10)
3. If score >= 50: BUY with confidence = min(score, 95)
4. Stop loss: min(BB_lower, close * 0.97) — 3% max
5. Take profit: [BB_mid (25%), EMA_50 (25%), BB_upper (25%), EMA_50 * 1.02 (25%)]

**generate_exit_signal logic:**
- RSI > 70 → urgency 60, partial 0.5
- Close > BB_upper → urgency 70, full exit
- current_pnl_pct > 3% and RSI > 60 → urgency 50, partial 0.5
- Position age > 48h (not trackable here, skip for now)

**Tests:** 12+ tests covering:
- Oversold conditions → BUY signal with confidence
- Normal conditions → NO_SIGNAL
- Regime check (active in RANGING, inactive in STRONG_BULL)
- Exit on RSI overbought
- Exit on BB_upper touch
- Edge cases: missing indicators, all zeros

### Task 3: Trend Following Strategy

**Files:**
- Create: `nexus_strategy/domain/services/strategies/trend_following.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_trend_following.py`

**TrendFollowingStrategy(BaseStrategy):**
- name: "TrendFollowing"
- optimal_regimes: REGIME_STRONG_BULL, REGIME_MODERATE_BULL, REGIME_BREAKOUT_BULL

**generate_signal logic:**
1. Get indicators: EMA_9, EMA_21, EMA_50, EMA_200, ADX_14, MACD_12_26_9, MACD_hist, RSI_14, Supertrend_10_3, close, ATR_14
2. Score system:
   - EMA alignment (9 > 21 > 50 > 200 = +20, 9 > 21 > 50 = +15, 9 > 21 = +10)
   - ADX strong (> 30 = +20, > 25 = +15, > 20 = +10)
   - MACD positive and histogram positive = +15
   - RSI in sweet spot (50-70 = +15, 45-75 = +10)
   - EMA pullback entry (close near EMA_21, within 1% = +15)
   - Supertrend bullish (close > Supertrend = +10)
   - Volume above average = +5
3. If score >= 55: BUY with confidence = min(score, 95)
4. Stop loss: max(EMA_50, close - ATR * 3.0)
5. Take profit: [close + ATR*2 (25%), close + ATR*3 (25%), close + ATR*4 (25%), close + ATR*6 (25%)]

**generate_exit_signal logic:**
- EMA_9 < EMA_21 (trend weakening) → urgency 50, partial 0.5
- ADX < 20 (trend dying) → urgency 60, partial 0.5
- Close < EMA_50 → urgency 75, full exit
- MACD histogram turns negative while MACD still positive → urgency 40, partial 0.25

**Tests:** 12+ tests covering bullish trend BUY, weak trend NO_SIGNAL, exit conditions, regime filtering.

---

## Chunk 2: Momentum Breakout + Volatility Squeeze + Volume Profile

### Task 4: Momentum Breakout Strategy

**Files:**
- Create: `nexus_strategy/domain/services/strategies/momentum_breakout.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_momentum_breakout.py`

**MomentumBreakoutStrategy(BaseStrategy):**
- name: "MomentumBreakout"
- optimal_regimes: REGIME_SQUEEZE, REGIME_BREAKOUT_BULL, REGIME_TRANSITION_UP, REGIME_ACCUMULATION

**generate_signal logic:**
1. Get: close, BB_upper_20, BB_lower_20, BB_width_20, Keltner_upper, Keltner_lower, ROC_9, ADX_14, RSI_14, volume (via Volume_SMA_20), ATR_14, OBV
2. Score system:
   - BB breakout (close > BB_upper = +25)
   - Keltner squeeze release (BB was inside Keltner, now BB expanding = +20)
   - Strong ROC (> 1.5 = +20, > 1.0 = +15, > 0.5 = +10)
   - Volume explosion (current volume > 2x SMA = +15, > 1.5x = +10)
   - ADX rising (> 25 = +10)
   - RSI momentum (55-75 = +10)
   - OBV rising = +5
3. Fake breakout filter: if RSI > 80 and volume < 1.5x SMA → reduce score by 20
4. If score >= 55: BUY, confidence = min(score, 95)
5. Stop loss: BB_mid or close - ATR * 2.0
6. Take profit: [close + ATR*1.5 (30%), close + ATR*3 (30%), close + ATR*5 (40%)]

**generate_exit_signal logic:**
- Failed breakout: close falls back below BB_upper → urgency 80, full exit
- ROC turns negative → urgency 60, partial 0.5
- Volume dries up (< 0.7x SMA) → urgency 50, partial 0.5

**Tests:** 12+ tests.

### Task 5: Volatility Squeeze Strategy

**Files:**
- Create: `nexus_strategy/domain/services/strategies/volatility_squeeze.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_volatility_squeeze.py`

**VolatilitySqueezeStrategy(BaseStrategy):**
- name: "VolatilitySqueeze"
- optimal_regimes: REGIME_SQUEEZE, REGIME_RANGING_TIGHT, REGIME_ACCUMULATION

**generate_signal logic:**
1. Get: BB_upper_20, BB_lower_20, BB_width_20, Keltner_upper, Keltner_lower, ATR_14, ROC_9, RSI_14, MACD_hist, EMA_9, EMA_21, close, ADX_14
2. Squeeze detection:
   - BB inside Keltner: BB_lower > Keltner_lower AND BB_upper < Keltner_upper = squeeze
   - BB_width < 0.03 = tight squeeze
   - ADX < 20 = low directional movement
3. Direction prediction score:
   - RSI > 50 = +15 (bullish bias)
   - MACD_hist > 0 = +15
   - EMA_9 > EMA_21 = +10
   - ROC > 0 = +10
   - Close in upper half of BB range = +10
4. If squeeze detected AND direction score >= 35: BUY, confidence = min(40 + direction_score, 90)
5. Stop loss: BB_lower or close - ATR * 2.0
6. TP: [close + ATR*2 (30%), close + ATR*3 (30%), close + ATR*5 (40%)]

**generate_exit_signal logic:**
- Squeeze released but wrong direction (close < BB_lower) → urgency 90, full exit
- BB_width expanding but price not moving up → urgency 60, partial 0.5

**Tests:** 10+ tests.

### Task 6: Volume Profile Strategy

**Files:**
- Create: `nexus_strategy/domain/services/strategies/volume_profile.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_volume_profile.py`

**VolumeProfileStrategy(BaseStrategy):**
- name: "VolumeProfile"
- optimal_regimes: REGIME_MODERATE_BULL, REGIME_ACCUMULATION, REGIME_RANGING_WIDE

**generate_signal logic:**
1. Get: close, OBV, CMF_20, Volume_SMA_20, RSI_14, EMA_21, EMA_50, BB_lower_20, BB_upper_20, MFI_14
2. Smart money detection score:
   - OBV rising while price flat/declining = +20 (bullish divergence)
   - CMF > 0.1 = +15, CMF > 0.05 = +10 (institutional accumulation)
   - MFI < 30 with CMF > 0 = +15 (oversold but money flowing in)
   - Volume > 1.5x SMA = +10 (institutional activity)
3. VWAP-like signals (using EMA_21 as proxy):
   - Close near EMA_21 from above with RSI 40-55 = +15 (pullback entry)
   - Close < BB_lower and CMF > 0 = +20 (reversal with institutional support)
4. If score >= 50: BUY, confidence = min(score, 90)
5. Stop loss: close - ATR * 2.5
6. TP: [EMA_50 (25%), BB_upper (25%), close * 1.03 (25%), close * 1.05 (25%)]

**generate_exit_signal logic:**
- CMF turns negative (< -0.1) → urgency 60, partial 0.5
- OBV declining with price rising → urgency 50, partial 0.5 (distribution)
- Close > BB_upper with MFI > 80 → urgency 70, full exit

**Tests:** 10+ tests.

---

## Chunk 3: Divergence + Market Structure + Meta Strategy

### Task 7: Divergence Strategy

**Files:**
- Create: `nexus_strategy/domain/services/strategies/divergence.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_divergence.py`

**DivergenceStrategy(BaseStrategy):**
- name: "Divergence"
- optimal_regimes: REGIME_WEAK_BEAR, REGIME_ACCUMULATION, REGIME_TRANSITION_UP

**generate_signal logic:**
1. Get indicators on multiple timeframes (5m, 15m, 1h):
   - RSI_14, MACD_12_26_9, OBV, CCI_20, MFI_14, close
2. Bullish divergence detection per indicator:
   - Price making lower low but indicator making higher low = bullish divergence
   - Since we only have latest values (not historical), use: price < EMA_50 but RSI > 35 (not matching the drop) as proxy
   - RSI divergence: close declining (close < EMA_21) but RSI > 40 = +20
   - MACD divergence: close < EMA_21 but MACD_hist > 0 or rising = +20
   - OBV divergence: volume accumulation (CMF > 0) while price down = +15
   - CCI divergence: CCI > -50 while close < BB_lower = +15
   - MFI divergence: MFI > 40 while close near low = +10
3. Multi-TF confirmation:
   - Same divergence on 2 TFs = score * 1.3
   - Same divergence on 3 TFs = score * 1.6
4. If score >= 50: BUY, confidence = min(score, 90)
5. Stop loss: recent low or close - ATR * 2.5
6. TP: [EMA_21 (30%), EMA_50 (30%), BB_mid (40%)]

**generate_exit_signal logic:**
- Divergence resolved (RSI > 60 and price recovered) → urgency 50, partial 0.5
- Reverse divergence forming → urgency 70, full exit

**Tests:** 10+ tests.

### Task 8: Market Structure Strategy

**Files:**
- Create: `nexus_strategy/domain/services/strategies/market_structure.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_market_structure.py`

**MarketStructureStrategy(BaseStrategy):**
- name: "MarketStructure"
- optimal_regimes: REGIME_TRANSITION_UP, REGIME_ACCUMULATION, REGIME_BREAKOUT_BULL

**generate_signal logic:**
1. Get: close, EMA_9, EMA_21, EMA_50, EMA_200, high (BB_upper as proxy), low (BB_lower as proxy), RSI_14, ADX_14, ROC_9, Volume_SMA_20, ATR_14
2. Structure analysis score:
   - Break of Structure bullish: close > EMA_50 when previously below = +20
   - Change of Character: EMA_9 crosses above EMA_21 = +15
   - Higher high: close > BB_upper * 0.99 = +10
   - Higher low: close > BB_lower and BB_lower rising (BB_lower > EMA_200) = +10
   - Order Block support: close near EMA_200 with RSI < 40 = +15 (demand zone)
   - Fair Value Gap fill: large gap between high and low (ATR > 1.5x normal) = +10
   - RSI confirming structure change (crossing 50 from below) = +10
3. BTC context: btc_trend == "bullish" = +5
4. If score >= 55: BUY, confidence = min(score, 90)
5. Stop loss: EMA_200 or close - ATR * 3.0
6. TP: [EMA_50 + ATR (25%), BB_upper (25%), close + ATR*3 (25%), close + ATR*5 (25%)]

**generate_exit_signal logic:**
- Structure broken: close < EMA_50 when it was above = urgency 70, full exit
- Lower low (close < previous support) = urgency 80, full exit
- EMA_9 < EMA_21 = urgency 50, partial 0.5

**Tests:** 10+ tests.

### Task 9: Meta Strategy (Signal Fusion Engine)

**Files:**
- Create: `nexus_strategy/domain/services/strategies/meta_strategy.py`
- Test: `nexus_strategy/tests/domain/test_services/test_strategies/test_meta_strategy.py`

**MetaStrategy class (NOT a BaseStrategy subclass):**
```python
class MetaStrategy:
    def __init__(self, strategies: list[BaseStrategy], config: IConfigProvider):
        self._strategies = strategies
        self._config = config
```

**fuse(self, pair: str, market_state: MarketState) -> SignalBundle:**
1. **Filter phase:**
   - Run each strategy's generate_signal(pair, market_state)
   - Discard signals with confidence < 40
   - Discard signals from strategies not active for current regime
2. **Weighting phase:**
   - For each remaining signal:
     - weighted_score = confidence * regime_weight * strategy_weight
     - regime_weight: from market_state.strategy_weights, default 1.0
     - strategy_weight: from market_state.indicator_reliability, default 1.0
3. **Consensus phase:**
   - Count buy signals: consensus_count
   - consensus_total = number of active strategies
   - Consensus multiplier: >= 5/7 = 1.3, >= 3/7 = 1.0, 2/7 = 0.6, 1/7 = 0.3 (only if conf > 85)
4. **Composite score:**
   - composite = mean(weighted_scores) * consensus_multiplier
   - Clamp 0-100
5. **Decision:**
   - composite >= 70: "BUY" (STRONG BUY)
   - composite >= 55: "BUY"
   - composite >= 45: "BUY" (WEAK)
   - < 45: "REJECT"
6. **Build SignalBundle:**
   - Merge stop losses (weighted average)
   - Merge take profits (intersection of strategy TPs)
   - Risk rating: "LOW" if composite > 75, "MEDIUM" if > 55, "HIGH" otherwise
   - Suggested stake multiplier based on consensus and composite

**generate_all_exit_signals(self, pair: str, market_state: MarketState, entry_price: float, current_pnl_pct: float) -> list[ExitSignal]:**
- Run each active strategy's generate_exit_signal
- Return list of all non-empty ExitSignals
- Sort by urgency descending

**Tests:** 15+ tests covering:
- Single strategy BUY fused correctly
- Multiple strategies agreeing → high composite
- No strategies meet threshold → REJECT
- Consensus multiplier effects
- Regime filtering removes inactive strategies
- Exit signal aggregation
- Edge cases: no strategies, all filtered out, confidence boundary
- Weighted scoring with custom weights

### Task 10: Final Signal Layer Integration Test

Run all Plan 3 tests together, verify:
1. All tests pass
2. Hexagonal rule: `grep -r "from nexus_strategy.adapters" nexus_strategy/domain/` returns empty
3. All Plan 1+2+3 tests combined pass
