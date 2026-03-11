# Nexus Strategy - Plan 4: Execution Layer (Exit Engine, Position Manager, Risk Manager)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Execution Layer — 5-layer exit engine, position sizer (Kelly), DCA/derisk/buyback systems, and portfolio-level risk manager.

**Architecture:** Hexagonal. All services are domain services. They receive MarketState/SignalBundle/TradeContext and return decisions. No external dependencies.

**Tech Stack:** Python 3.11+, numpy, pytest

**Spec Reference:** `docs/superpowers/specs/2026-03-11-nexus-strategy-design.md` (Sections 7, 8)
**Depends on:** Plans 1-3 completed (models, data layer, signal layer)

---

## File Structure (new files this plan)

```
nexus_strategy/
├── domain/
│   └── services/
│       ├── exit_engine.py              # 5-layer exit system
│       ├── position_sizer.py           # Kelly criterion + multipliers
│       ├── position_manager.py         # DCA, derisk, buyback
│       └── risk_manager.py             # Portfolio-level risk management
└── tests/
    └── domain/
        └── test_services/
            ├── test_exit_engine.py
            ├── test_position_sizer.py
            ├── test_position_manager.py
            └── test_risk_manager.py
```

---

## Chunk 1: Exit Engine + Position Sizer

### Task 1: Exit Engine (5 Layers)

**Files:**
- Create: `nexus_strategy/domain/services/exit_engine.py`
- Test: `nexus_strategy/tests/domain/test_services/test_exit_engine.py`

**ExitEngine class:**
```python
class ExitEngine:
    def __init__(self, config: IConfigProvider):
        self._config = config
```

**evaluate(self, pair: str, market_state: MarketState, entry_price: float, current_pnl_pct: float, position_age_candles: int, strategy_exit_signals: list[ExitSignal], portfolio_state: dict) -> ExitSignal | None:**

Evaluates all 5 layers in order, returns the highest-urgency exit signal or None.

**Layer 1: Emergency Exit** (ExitLayer.EMERGENCY)
- Black Swan: pnl_pct < -10% → urgency 100, full exit, "Black Swan: extreme loss"
- Doom Stop (regime-adaptive):
  - PANIC regime: pnl_pct < -4% → urgency 95, full exit
  - STRONG_BEAR: pnl_pct < -6% → urgency 95
  - MODERATE_BEAR: pnl_pct < -8% → urgency 95
  - RANGING: pnl_pct < -10% → urgency 90
  - MODERATE_BULL: pnl_pct < -12% → urgency 90
  - STRONG_BULL: pnl_pct < -15% → urgency 85
  - Default: pnl_pct < -10% → urgency 90
- Portfolio protection: portfolio_state.get("total_pnl_pct", 0) < -20 → urgency 100, full exit

**Layer 2: Technical Exit** (ExitLayer.TECHNICAL)
- Aggregate strategy exit signals:
  - Count signals with should_exit=True
  - 4+ signals: urgency = max(urgencies), full exit (1.0)
  - 2-3 signals: urgency = max(urgencies), partial (0.5)
  - 1 signal: urgency = that signal's urgency, partial (0.25)
  - 0 signals: no exit from this layer
- Strategy-independent checks using market_state:
  - RSI > 78 on 5m → add ExitSignal(urgency=55, partial=0.5)
  - EMA_9 < EMA_21 < EMA_50 on 5m → add ExitSignal(urgency=65, partial=0.5)

**Layer 3: Regime Exit** (ExitLayer.REGIME)
- If regime just changed (market_state.regime_just_changed):
  - Check if new regime is unfavorable for the position
  - Bearish regimes (STRONG_BEAR, MODERATE_BEAR, PANIC, DISTRIBUTION): urgency 70, partial 0.5
  - Neutral regimes: no exit
- Sentinel override: sentinel risk_score > 90 → urgency 80, full exit

**Layer 4: Portfolio Exit** (ExitLayer.PORTFOLIO)
- Drawdown level checks from portfolio_state:
  - "drawdown_level" >= 4 (CATASTROPHIC): urgency 85, full exit
  - "drawdown_level" >= 3 (CRITICAL): urgency 70, partial 0.5
- Slot exceeded: portfolio_state.get("slots_exceeded", False) → urgency 50, partial 0.25

**Layer 5: Profit Optimizer** (ExitLayer.PROFIT_OPTIMIZER)
- Partial take profit based on PnL tiers:
  - pnl_pct >= 8%: urgency 40, partial 0.25, "TP Level 4"
  - pnl_pct >= 5%: urgency 35, partial 0.25, "TP Level 3"
  - pnl_pct >= 3%: urgency 30, partial 0.25, "TP Level 2"
  - pnl_pct >= 1.5%: urgency 25, partial 0.25, "TP Level 1"
- Time decay: if position_age_candles > 72 (6h) and pnl_pct < 1%: urgency 45, partial 0.5, "Time decay"

**Return:** highest-urgency ExitSignal across all layers, or None if no exit triggered.

**Tests (20+):**
- Black swan exit, doom stop per regime, portfolio protection
- Technical aggregation: 0/1/2/4 signals
- RSI independent check, EMA cross independent check
- Regime change exit, sentinel override
- Portfolio drawdown exit, slot exceeded
- Take profit tiers, time decay
- No exit when conditions are good
- Layer priority (emergency > technical > regime > portfolio > profit)

### Task 2: Position Sizer (Kelly Criterion)

**Files:**
- Create: `nexus_strategy/domain/services/position_sizer.py`
- Test: `nexus_strategy/tests/domain/test_services/test_position_sizer.py`

**PositionSizer class:**
```python
class PositionSizer:
    def __init__(self, config: IConfigProvider):
        self._config = config
```

**calculate_size(self, signal_bundle: SignalBundle, market_state: MarketState, portfolio_state: dict) -> float:**

Returns position size as fraction of total capital (0.0 to 1.0).

1. **Base Kelly**:
   - win_rate = portfolio_state.get("win_rate", 0.5)
   - avg_win = portfolio_state.get("avg_win", 0.02)
   - avg_loss = portfolio_state.get("avg_loss", 0.01)
   - kelly = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win if avg_win > 0 else 0
   - half_kelly = kelly * 0.5
   - Clamp to 0.0-0.25

2. **6 multipliers:**
   - regime_mult: STRONG_BULL=1.2, MODERATE_BULL=1.0, WEAK_BULL=0.8, RANGING=0.6, BEAR=0.4, PANIC=0.2
   - confidence_mult: signal_bundle.composite_score / 100
   - consensus_mult: signal_bundle.suggested_stake_multiplier
   - drawdown_mult: 1.0 - (portfolio_state.get("current_drawdown_pct", 0) / 100) (lower size in drawdown)
   - correlation_mult: 1.0 - portfolio_state.get("max_correlation", 0) * 0.5 (reduce if correlated)
   - sentinel_mult: 1.0 if risk < 60, 0.7 if < 80, 0.3 if >= 80

3. **Final**: half_kelly * product(multipliers)

4. **Limits**:
   - Min: 0.05 (5% of capital)
   - Max: 0.15 (15%)
   - If final < 0.05 after multipliers: return 0.0 (don't trade)
   - Clamp to [0.05, 0.15]

**Tests (12+):**
- Basic Kelly calculation
- Each multiplier effect
- Limits enforcement (min 5%, max 15%)
- Below minimum returns 0
- Edge cases: zero win rate, zero avg_win, extreme drawdown

---

## Chunk 2: Position Manager + Risk Manager

### Task 3: Position Manager (DCA, Derisk, Buyback)

**Files:**
- Create: `nexus_strategy/domain/services/position_manager.py`
- Test: `nexus_strategy/tests/domain/test_services/test_position_manager.py`

**PositionManager class:**
```python
class PositionManager:
    def __init__(self, config: IConfigProvider):
        self._config = config
```

**evaluate_dca(self, pair: str, market_state: MarketState, current_pnl_pct: float, dca_count: int, regime: SynthesizedRegime) -> dict | None:**
- Returns {"action": "DCA", "amount_pct": float, "reason": str} or None
- DCA forbidden regimes: PANIC, STRONG_BEAR, DISTRIBUTION → return None
- DCA levels by regime:
  - STRONG_BULL: 4 levels at -4%, -8%, -12%, -16%
  - MODERATE_BULL: 3 levels at -3%, -6%, -10%
  - WEAK_BULL/RANGING: 2 levels at -3%, -5%
  - Default: 2 levels at -3%, -5%
- Check: dca_count < max_levels AND current_pnl_pct <= threshold_for_level
- Amount: level 1 = 50%, level 2 = 30%, level 3 = 15%, level 4 = 5%
- Technical filter: RSI_14 < 40 (oversold confirmation) from 5m

**evaluate_derisk(self, pair: str, current_pnl_pct: float, rsi: float) -> dict | None:**
- Returns {"action": "DERISK", "sell_pct": float, "level": int, "reason": str} or None
- Level 1 (-5%): sell 15% — skip if RSI < 30 (too oversold, might bounce)
- Level 2 (-8%): sell 25%
- Level 3 (-12%): sell 40%
- Level 4 (-16%): sell 80%

**evaluate_buyback(self, pair: str, prev_profitable: bool, price_drop_pct: float, regime: SynthesizedRegime, confidence: int) -> dict | None:**
- Returns {"action": "BUYBACK", "size_pct": float, "reason": str} or None
- Conditions: prev_profitable AND price_drop_pct > 3% AND regime not bearish
- Size: 0.6 (60% of previous), 0.8 if confidence > 80

**Tests (15+):**
- DCA: allowed regimes, forbidden regimes, level progression, amount, RSI filter
- Derisk: all 4 levels, RSI skip on level 1
- Buyback: conditions met, conditions not met, sizing
- Edge cases: max DCA reached, boundary PnL values

### Task 4: Risk Manager (Portfolio Level)

**Files:**
- Create: `nexus_strategy/domain/services/risk_manager.py`
- Test: `nexus_strategy/tests/domain/test_services/test_risk_manager.py`

**RiskManager class:**
```python
class RiskManager:
    def __init__(self, config: IConfigProvider):
        self._config = config
```

**validate_entry(self, signal_bundle: SignalBundle, market_state: MarketState, portfolio_state: dict) -> tuple[bool, str]:**
- Returns (allowed: bool, reason: str)
- Checks:
  - Drawdown level: >= 4 (CATASTROPHIC) → reject all entries
  - Drawdown level: >= 3 (CRITICAL) → only allow composite_score > 80
  - Max open slots: portfolio_state.get("open_positions", 0) >= portfolio_state.get("max_slots", 10) → reject
  - Pair already open: portfolio_state.get("open_pairs", []) contains signal_bundle.pair → reject unless DCA
  - Total exposure: portfolio_state.get("total_exposure", 0) >= 0.85 → reject
  - Sentinel risk: market_state.sentinel.get("risk_score", 0) >= 80 → reject
  - Sector limit: portfolio_state.get("sector_exposure", {}).get(sector, 0) >= 0.35 → reject

**get_drawdown_level(self, current_drawdown_pct: float) -> int:**
- 0: NORMAL (< 5%)
- 1: CAUTION (5-10%)
- 2: WARNING (10-15%)
- 3: CRITICAL (15-20%)
- 4: CATASTROPHIC (> 20%)

**get_max_slots(self, regime: SynthesizedRegime) -> int:**
- STRONG_BULL: 12
- MODERATE_BULL: 10
- WEAK_BULL/RANGING: 8
- BEAR regimes: 5
- PANIC: 2
- Default: 8

**calculate_portfolio_risk(self, positions: list[dict]) -> dict:**
- Returns {"total_exposure": float, "max_correlation": float, "sector_distribution": dict, "var_95": float}
- total_exposure: sum of position sizes / total capital
- Simplified VaR: -2.0% * total_exposure (parametric estimate)
- sector_distribution: count positions per sector using constants.SECTOR_MAP

**Tests (15+):**
- validate_entry: each rejection case, allowed entry
- Drawdown levels: each threshold
- Max slots per regime
- Portfolio risk calculation
- Edge cases: empty portfolio, single position

### Task 5: Execution Layer Integration Test

Run all Plan 4 tests together, verify:
1. All tests pass
2. Hexagonal rule clean
3. All Plans 1-4 tests combined pass
