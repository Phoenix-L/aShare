# Core–Satellite Mean Reversion Strategy Design (Phase 0)

## Reference Context
This design extends the platform model described in `docs/system_architecture.md`, especially the Strategy Framework, Backtest Engine, and Research Layer responsibilities.

## 1. Repository Architecture Snapshot (Current State)
Current module layout confirms expected architecture:

- `src/ashare/config/` — settings and loader
- `src/ashare/data/` — providers, loaders, normalizers, cache
- `src/ashare/engine/` — Cerebro builder, analyzers, backtest runner
- `src/ashare/strategies/` — strategy implementations and registry
- `src/ashare/constraints/` — A-share rules utilities
- `src/ashare/research/` — experiment runner and walk-forward analysis

Current execution flow:
1. CLI resolves strategy name via `ashare.strategies.get_strategy_class`.
2. CLI loads market data via `ashare.data.loaders`.
3. `engine.runner.run_backtest` builds Cerebro, attaches feed + strategy, and executes.
4. Research modules (`experiment_runner`, `walk_forward`) repeatedly call `run_backtest` for parameterized studies.

## 2. Strategy Module Location
Planned strategy module:

`src/ashare/strategies/core_satellite_mean_reversion.py`

This keeps strategy logic isolated in the Strategy Framework layer and makes it available to CLI/research workflows through registry lookup.

## 3. Dependencies
Primary integration dependencies:
- **Backtrader strategy engine** (base strategy lifecycle + order execution)
- **`ashare.data.normalizers`** (feed compatibility and expected field schema)
- **`ashare.engine.runner`** (single-run execution contract)

Secondary integration touchpoints:
- `ashare.research.experiment_runner`
- `ashare.research.walk_forward`

## 4. Indicator Initialization
Inside strategy `__init__`:
- `SMA(20)` for short-term reference
- `SMA(120)` for regime filtering
- `ATR(14)` for volatility-normalized displacement

Z-score is computed each bar internally:

\[
Z = \frac{Close - SMA20}{ATR14}
\]

Design note:
- Protect against divide-by-zero when ATR is near zero by gating signal evaluation.

## 5. Position Management
The strategy should maintain explicit sleeve accounting:

- `core_position`: initialized once at strategy start (target = 2000 shares)
- `satellite_position`: mutable tactical sleeve (0–2000 shares)

Design requirements:
- Core and satellite accounting must remain separate from total broker position.
- Core position is never reduced by signal exits.
- Satellite sleeve respects cap, block size, and pause rules.

## 6. Order Execution
Execution rules:
- Satellite orders are executed in **500-share blocks**.
- New satellite buys only when trend guardrail passes (`price > SMA120`).
- Core orders are never reduced once established.

Suggested implementation sequence:
1. Ensure core target is established early in lifecycle (e.g., first eligible bar).
2. Evaluate satellite entry/scale tiers from Z-score thresholds.
3. Evaluate satellite de-risking/close thresholds.
4. Keep order sizing idempotent and bounded.

## 7. Compatibility
The strategy must be compatible with existing research workflows:

- **Experiment Runner:** supports parameter grids and multi-symbol loops by passing `strategy_params` to `run_backtest`.
- **Walk Forward:** supports train/test rolling optimization where best in-sample params are evaluated out-of-sample.

Compatibility implications:
- Strategy parameters must be declared in Backtrader `params` for external injection.
- Strategy metrics should remain serializable and robust in batch execution contexts.

## 8. Metrics
Strategy-level reporting should include:
- `core_pnl`
- `satellite_pnl`
- `combined_return`
- `drawdown`

Design approach:
- Use strategy fields or custom analyzers to expose sleeve-level PnL.
- Preserve existing engine-level metrics while adding sleeve-level decomposition.

## 9. Strategy Registry Exploration
Current strategy registration is centralized in `src/ashare/strategies/__init__.py` using a name→class mapping and `get_strategy_class(name)` lookup.

Proposed registry pattern:

```python
STRATEGY_REGISTRY = {
    "mid_freq_ma": MidFreqMA,
    "core_satellite": CoreSatelliteMeanReversion,
}
```

### Why this registry pattern matters
1. **CLI discovery**
   - `backtest --strategy <name>` resolves deterministically from one source of truth.
2. **Experiment runner compatibility**
   - Batch jobs use identical strategy name semantics as ad-hoc runs.
3. **Walk-forward compatibility**
   - Optimization workflows can reuse strategy lookup without special cases.
4. **Extensibility**
   - Adding a new strategy becomes explicit: implement class + add registry entry.

### Registration guideline for new strategies
For each new strategy:
1. Implement class in `src/ashare/strategies/<strategy_name>.py`.
2. Export/import class in `src/ashare/strategies/__init__.py`.
3. Add a unique key to `STRATEGY_REGISTRY`.
4. Ensure key naming aligns with CLI usage (`snake_case` recommended).
5. Add tests for registry resolution and execution smoke path.

---

This document is Phase 0 architecture/design guidance. It intentionally defines integration contracts and invariants before implementation coding begins.
