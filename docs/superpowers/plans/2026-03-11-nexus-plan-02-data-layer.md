# Nexus Strategy - Plan 2: Data Layer (Indicators, Regime Detection, Sentinel Bridge)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Data Layer — indicator calculation engine, 3-layer regime detection, sentinel bridge adapters, and market context service.

**Architecture:** Hexagonal. Domain services use port interfaces, adapters implement them. Indicator calculations use numpy/scipy/pandas (math libraries allowed in domain). ta-lib NOT required (pure implementations).

**Tech Stack:** Python 3.11+, numpy, scipy, pandas, pytest

**Spec Reference:** `docs/superpowers/specs/2026-03-11-nexus-strategy-design.md` (Sections 3, 4, 9)
**Depends on:** Plan 1 (Foundation) — all models, ports, utils, config completed

---

## File Structure (new files this plan)

```
nexus_strategy/
├── domain/
│   └── services/
│       ├── indicator_engine.py          # Indicator calculation orchestrator
│       ├── indicator_registry.py        # Indicator performance tracking
│       ├── regime_service.py            # 3-layer regime detection + synthesizer
│       └── market_context_service.py    # BTC/macro/inter-market analysis
├── adapters/
│   ├── freqtrade/
│   │   └── data_adapter.py             # IDataProvider implementation
│   └── sentinel/
│       ├── redis_adapter.py            # ISentinelProvider via Redis
│       └── json_adapter.py             # ISentinelProvider via JSON file
└── tests/
    ├── domain/
    │   └── test_services/
    │       ├── __init__.py
    │       ├── test_indicator_engine.py
    │       ├── test_indicator_registry.py
    │       ├── test_regime_service.py
    │       └── test_market_context_service.py
    └── adapters/
        ├── test_freqtrade/
        │   ├── __init__.py
        │   └── test_data_adapter.py
        └── test_sentinel/
            ├── __init__.py
            ├── test_redis_adapter.py
            └── test_json_adapter.py
```

---

## Chunk 1: Indicator Engine + Registry

### Task 1: Indicator Registry

**Files:**
- Create: `nexus_strategy/domain/services/indicator_registry.py`
- Test: `nexus_strategy/tests/domain/test_services/test_indicator_registry.py`

The IndicatorRegistry tracks which indicators exist, their configurations, and runtime performance metrics (accuracy, false positive rate). Domain service — no external deps.

**IndicatorSpec dataclass:**
- name: str (e.g. "RSI_14")
- category: str ("momentum", "trend", "volatility", "volume", "statistical")
- timeframes: list[str] (which TFs this indicator is calculated on)
- params: dict[str, Any] (e.g. {"period": 14})
- weight: float (current adaptive weight, default 1.0)
- reliability: float (0.0-1.0, default 0.5)
- signal_count: int (times this indicator contributed to a signal)
- correct_count: int (times the signal was correct)

**IndicatorRegistry class:**
- register(spec: IndicatorSpec) -> None
- get(name: str) -> IndicatorSpec | None
- get_by_category(category: str) -> list[IndicatorSpec]
- get_all() -> list[IndicatorSpec]
- update_performance(name: str, was_correct: bool) -> None (updates counts + reliability)
- get_weight(name: str) -> float
- update_weight(name: str, new_weight: float) -> None (clamp 0.1 to 3.0)
- get_reliability(name: str) -> float

Default indicators to register (at least 30): RSI_14, RSI_7, StochRSI_K, StochRSI_D, MFI_14, CCI_20, WilliamsR_14, ROC_9, EMA_9, EMA_21, EMA_50, EMA_200, SMA_20, SMA_50, MACD_12_26_9, MACD_signal, MACD_hist, ADX_14, DI_plus_14, DI_minus_14, Supertrend_10_3, BB_upper_20, BB_mid_20, BB_lower_20, BB_width_20, ATR_14, Keltner_upper, Keltner_lower, OBV, CMF_20, Volume_SMA_20, Hurst_50, Parkinson_Vol

### Task 2: Indicator Engine

**Files:**
- Create: `nexus_strategy/domain/services/indicator_engine.py`
- Test: `nexus_strategy/tests/domain/test_services/test_indicator_engine.py`

The IndicatorEngine calculates all indicators from OHLCV candle data. Domain service using numpy/scipy/pandas for math.

**IndicatorEngine class:**
- __init__(self, registry: IndicatorRegistry, config: IConfigProvider)
- calculate_all(self, pair: str, candles: pd.DataFrame, timeframe: str) -> dict[str, float]
  - Takes OHLCV DataFrame, returns {indicator_name: value} for latest candle
- calculate_single(self, name: str, candles: pd.DataFrame) -> float | None

**Indicator calculation methods (private):**
- _calc_rsi(close: pd.Series, period: int) -> float
- _calc_ema(close: pd.Series, period: int) -> float
- _calc_sma(close: pd.Series, period: int) -> float
- _calc_macd(close: pd.Series) -> tuple[float, float, float] (macd, signal, hist)
- _calc_bollinger(close: pd.Series, period: int, std: float) -> tuple[float, float, float, float] (upper, mid, lower, width)
- _calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> float
- _calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> tuple[float, float, float] (adx, di_plus, di_minus)
- _calc_stoch_rsi(close: pd.Series, period: int) -> tuple[float, float] (k, d)
- _calc_mfi(high, low, close, volume, period) -> float
- _calc_obv(close: pd.Series, volume: pd.Series) -> float (latest OBV value)
- _calc_cmf(high, low, close, volume, period) -> float
- _calc_supertrend(high, low, close, period, multiplier) -> float
- _calc_keltner(high, low, close, period, multiplier) -> tuple[float, float] (upper, lower)

All calculations use numpy/pandas operations. No ta-lib required.

Tests: create synthetic OHLCV DataFrames, verify each indicator returns reasonable values. Test edge cases (empty data, constant prices).

### Task 3: Regime Service — Micro Regime Detection

**Files:**
- Create: `nexus_strategy/domain/services/regime_service.py`
- Test: `nexus_strategy/tests/domain/test_services/test_regime_service.py`

Start with the RegimeService class and micro regime detection only. Mid/macro added in Tasks 4-5.

**RegimeService class:**
- __init__(self, config: IConfigProvider, indicator_engine: IndicatorEngine)
- detect_micro(self, indicators_5m: dict[str, float], indicators_15m: dict[str, float]) -> MicroRegime
  - Uses: ATR normalized, BB Width, RSI zone+slope, ROC+acceleration, EMA alignment, ADX, Volume ratio, OBV slope, CMF
  - Scoring system: each factor adds score for each regime
  - Returns highest-scoring MicroRegime
- detect_mid(self, indicators_1h: dict, indicators_4h: dict) -> MidRegime (Task 4)
- detect_macro(self, indicators_1d: dict, sentinel: dict) -> MacroRegime (Task 5)
- synthesize(self, micro, mid, macro) -> tuple[SynthesizedRegime, int, list[str]] (Task 6)
- detect_full(self, all_indicators: dict, sentinel: dict) -> CompositeRegime (orchestrator)

**Micro regime scoring rules:**
- TRENDING_UP: EMA_9 > EMA_21 > EMA_50, ADX > 25, RSI 50-70, ROC > 0
- TRENDING_DOWN: EMA_9 < EMA_21 < EMA_50, ADX > 25, RSI 30-50, ROC < 0
- RANGING: ADX < 20, BB_width < median, |ROC| < 0.5
- VOLATILE: ATR > 1.5x avg, BB_width > 2x median
- SQUEEZE: BB_width at minimum (< 0.5x median), ATR declining
- BREAKOUT_UP: price > BB_upper, volume > 2x avg, ROC > 1.0
- BREAKOUT_DOWN: price < BB_lower, volume > 2x avg, ROC < -1.0
- CHOPPY: ADX < 15, direction changes > 3 in last 5 candles

---

## Chunk 2: Mid/Macro Regime + Synthesizer

### Task 4: Mid Regime Detection

Add to `regime_service.py`:
- detect_mid(indicators_1h, indicators_4h) -> MidRegime
  - Uses: EMA alignment (12/26/50/200), EMA_200 slope, ADX, MACD, Hurst, rolling Sharpe, HH/HL counter, BTC correlation
  - TREND_BULL_STRONG: all EMAs aligned up, ADX>30, Hurst>0.6, MACD positive
  - TREND_BULL_WEAK: partial alignment, ADX 20-30
  - TREND_BEAR_STRONG: all EMAs aligned down, ADX>30, Hurst>0.6, MACD negative
  - TREND_BEAR_WEAK: partial alignment down
  - RANGING_TIGHT: ADX<20, BB_width small, Hurst<0.45
  - RANGING_WIDE: ADX<20, BB_width large
  - ACCUMULATION: price near support, volume declining, RSI recovering from oversold
  - DISTRIBUTION: price near resistance, volume declining, RSI weakening from overbought
  - REVERSAL_BULLISH: bearish trend + bullish divergence signals
  - REVERSAL_BEARISH: bullish trend + bearish divergence signals

### Task 5: Macro Regime Detection

Add to `regime_service.py`:
- detect_macro(indicators_1d, sentinel_data) -> MacroRegime
  - Uses: BTC EMA200, Golden/Death Cross, monthly RSI, market breadth, funding, on-chain
  - BULL_EUPHORIA: BTC>EMA200, RSI_monthly>70, funding>0.05%, extreme greed
  - BULL_HEALTHY: BTC>EMA200, RSI_monthly 50-70, moderate funding
  - BULL_EARLY: BTC just crossed above EMA200, golden cross forming
  - BEAR_PANIC: BTC<EMA200, RSI_monthly<30, high liquidations, extreme fear
  - BEAR_GRIND: BTC<EMA200, RSI_monthly 30-45, low volume
  - BEAR_EARLY: BTC just crossed below EMA200, death cross forming
  - TRANSITION_UP: BTC approaching EMA200 from below, improving breadth
  - TRANSITION_DOWN: BTC approaching EMA200 from above, deteriorating breadth
  - UNCERTAIN: conflicting signals

### Task 6: Regime Synthesizer

Add to `regime_service.py`:
- synthesize(micro, mid, macro) -> tuple[SynthesizedRegime, int, list[str]]
  - Returns: (synthesized_regime, confidence, recommended_strategies)
  - Compatibility matrix: 3 layers aligned = HIGH (90-100), 2 aligned = MEDIUM (60-80), conflicting = LOW (30-50)
  - Transition smoothing: min 3 candles (except PANIC = instant)
  - Strategy recommendations per regime from config

- detect_full(all_indicators, sentinel) -> CompositeRegime
  - Orchestrates: micro → mid → macro → synthesize → build CompositeRegime

---

## Chunk 3: Market Context + Sentinel Adapters

### Task 7: Market Context Service

**Files:**
- Create: `nexus_strategy/domain/services/market_context_service.py`
- Test: `nexus_strategy/tests/domain/test_services/test_market_context_service.py`

Analyzes BTC state and overall market conditions. Domain service.

**MarketContextService class:**
- __init__(self, config: IConfigProvider)
- analyze_btc(self, btc_indicators: dict[str, dict[str, float]]) -> dict
  - Returns: {price, change_1h, change_24h, above_ema200, trend, golden_cross, death_cross}
- analyze_market_phase(self, btc_analysis: dict, sentinel_data: dict) -> str
  - Returns: "BTC_RALLY", "ALT_RALLY", "FULL_BULL", "ROTATION", "RISK_OFF", "CAPITULATION", "RECOVERY", "MIXED"
- calculate_altcoin_season_index(self, btc_change: float, alt_changes: dict[str, float]) -> int
  - 0-100 index: how many alts outperform BTC

### Task 8: Sentinel JSON Adapter

**Files:**
- Create: `nexus_strategy/adapters/sentinel/json_adapter.py`
- Test: `nexus_strategy/tests/adapters/test_sentinel/test_json_adapter.py`

Implements ISentinelProvider using a JSON file (fallback when Redis unavailable).

**JsonSentinelAdapter(ISentinelProvider):**
- __init__(self, json_path: str | Path)
- get_sentinel_data() -> dict (read JSON file, return data)
- is_connected() -> bool (file exists and recent)
- get_risk_score() -> int
- get_strategy_mode() -> str
- get_data_age_seconds() -> int (file mtime vs now)

### Task 9: Sentinel Redis Adapter

**Files:**
- Create: `nexus_strategy/adapters/sentinel/redis_adapter.py`
- Test: `nexus_strategy/tests/adapters/test_sentinel/test_redis_adapter.py`

Implements ISentinelProvider using Redis. Tests mock redis connection.

**RedisSentinelAdapter(ISentinelProvider):**
- __init__(self, redis_url: str, fallback: ISentinelProvider | None = None)
- Falls back to JsonSentinelAdapter if Redis unavailable
- All methods try Redis first, fallback on error

### Task 10: Freqtrade Data Adapter

**Files:**
- Create: `nexus_strategy/adapters/freqtrade/data_adapter.py`
- Test: `nexus_strategy/tests/adapters/test_freqtrade/test_data_adapter.py`

Implements IDataProvider. Converts Freqtrade DataFrames to domain model format.

**FreqtradeDataAdapter(IDataProvider):**
- __init__(self, indicator_engine: IndicatorEngine, regime_service: RegimeService, market_context: MarketContextService, sentinel: ISentinelProvider, config: IConfigProvider)
- get_market_state(pair, timeframe) -> MarketState (builds full snapshot)
- get_candles(pair, timeframe, count) -> dict[str, np.ndarray]
- get_available_pairs() -> list[str]
- set_dataframes(self, dataframes: dict[str, dict[str, pd.DataFrame]]) -> None (called by nexus.py to inject data)

### Task 11: Final Integration Test

Run all Plan 2 tests together, verify hexagonal rule still holds.
