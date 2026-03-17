# Core–Satellite Mean Reversion Strategy: User Manual

## 1. Overview (UPDATED)

The `core_satellite` strategy supports two practical workflows:

1. **Single backtest mode** (`ashare backtest`) for quick validation of one setup.
2. **Experiment mode** (`ashare experiment <yaml>`) for YAML-driven batch runs.
3. **Grid search** inside experiment mode to expand parameter combinations automatically.

Use single backtests when you want a fast sanity check. Use experiment mode when you want systematic parameter exploration and reproducible run artifacts.

---

## 2. Strategy Concept (KEEP + REFINE)

### Core position (long-term holding)
- The strategy first establishes a baseline long holding using `core_position` shares.
- Sell logic is constrained so total holdings should not drop below the core target.

### Satellite trading (mean reversion)
- Around the core, the strategy trades a tactical sleeve capped by `satellite_max`.
- Tactical entries/exits are executed in `trade_unit` share blocks.

### Ladder entry logic (Z-score based)
- Z-score is computed as:

\[
Z = \frac{Close - SMA(ma\_short)}{ATR(atr\_period)}
\]

- Current defaults are `ma_short=20`, `ma_trend=120`, `atr_period=14`.
- For each threshold in `z_entry` (for example `[-1.5, -2.0, -2.5]`), if `zscore <= threshold`, the strategy can add one `trade_unit` (subject to caps and trend filter).

### Exit logic
- For each threshold in `z_exit` (for example `[0.8, 1.5]`), if `zscore >= threshold`, the strategy attempts to sell one `trade_unit` from the satellite sleeve.
- A guard prevents reducing holdings below `core_position`.

### Placeholder parameter
- `z_entry_mode` exists as a placeholder for future entry styles.
- **Current implementation:** behavior is ladder-style regardless of `z_entry_mode` value.

---

## 3. Running a Simple Backtest (UPDATED)

```bash
ashare backtest \
  --strategy core_satellite \
  --symbol 002850.SZ \
  --start 2024-01-01 \
  --end 2025-01-01
```

Use this mode when you need:
- a quick check of one symbol + one parameter set,
- immediate headline metrics (return, Sharpe, drawdown),
- fast troubleshooting before batch experiments.

---

## 4. Running an Experiment (NEW — CRITICAL)

YAML-driven experiment mode:

```bash
ashare experiment configs/experiments/core_satellite_demo.yaml
```

In this workflow:
- `experiment_name` controls the output folder name.
- `parameters` defines base strategy parameters applied to every run.
- `grid_search` defines parameter dimensions for Cartesian expansion.

You can still pass CLI overrides with repeated `--param` options; these are merged into YAML-defined parameters/grid before run generation.

Implementation note: in YAML mode, market data is loaded once per symbol for the full date range, then reused across all parameter combinations for that symbol.

---

## 5. Experiment Config Structure (NEW)

Example (`configs/experiments/core_satellite_demo.yaml`):

```yaml
experiment_name: core_satellite_demo

strategy: core_satellite

symbols:
  - 002850.SZ

date_range:
  start: 2024-01-01
  end: 2025-01-01

parameters:
  core_position: 2000
  satellite_max: 2000
  trade_unit: 500

grid_search:
  z_entry:
    - [-1.5, -2.0, -2.5]
    - [-1.8, -2.2, -2.6]
  z_exit:
    - [0.8, 1.2]
    - [1.0, 1.5]
```

Section meanings:
- `strategy`: strategy registry name used by CLI.
- `symbols`: list of symbols to backtest.
- `date_range`: start/end date boundaries.
- `parameters`: fixed base parameters shared by every run.
- `grid_search`: values to sweep; each key adds one search dimension.
- `execution` (optional): supports runtime overrides such as `initial_cash` and `commission`.

---

## 6. Grid Search Behavior (NEW)

Grid search uses Cartesian-product expansion of `grid_search` values, merged with `parameters`.

Example:
- 2 `z_entry` choices × 2 `z_exit` choices = **4 parameter combinations**.
- With 1 symbol, that is 4 runs.
- With 3 symbols, that is 12 runs.

This is how the CLI explores parameter space systematically without manual repetition.

---

## 7. Output Structure (UPDATED)

In YAML experiment mode, outputs are written to:

```text
outputs/
  <experiment_name>/
    run_001/
      metrics.json
      config_snapshot.yaml
    run_002/
      metrics.json
      config_snapshot.yaml
    ...
```

Purpose:
- `metrics.json`: machine-readable performance metrics for the run.
- `config_snapshot.yaml`: exact symbol/date/parameter snapshot used for that run.

This structure supports reproducibility and traceability across many trials.

---

## 8. Interpreting Results (NEW — IMPORTANT)

Each run writes a `metrics.json`. Core fields include:
- `total_return` (also mirrored as `rtot`): cumulative return metric from analyzer output.
- `sharpe`: risk-adjusted return metric (may be `null` if unavailable from analyzer).
- `max_drawdown`: worst peak-to-trough drawdown (%).

Manual comparison approach:
1. Compare `total_return` across runs for raw growth.
2. Use `sharpe` to prefer more stable risk-adjusted profiles.
3. Check `max_drawdown` to reject overly fragile settings.
4. Review the paired `config_snapshot.yaml` to see exactly which parameters produced each metric set.

---

## 9. Recommended Workflow (NEW — VERY IMPORTANT)

1. Create an experiment YAML in `configs/experiments/`.
2. Run it with `ashare experiment <yaml>`.
3. Inspect each `run_xxx/metrics.json`.
4. Compare runs manually by return / Sharpe / drawdown.
5. Refine parameters and rerun with narrower grids.

This loop keeps research explicit, reproducible, and easy to audit.

---

## 10. CLI Parameter Override (UPDATED)

Example override:

```bash
ashare experiment configs/experiments/core_satellite_demo.yaml \
  --param z_exit=1.2
```

Override behavior in YAML mode:
- `--param key=v` (single value) overrides/sets `parameters[key]`.
- `--param key=v1,v2,...` (multiple values) overrides/sets `grid_search[key]`.
- Effective run combinations are generated **after** these overrides are merged.

In other words, CLI `--param` has priority over the original YAML content for the same key.

---

## 11. Future Extensions (UPDATED)

Planned/possible next steps:
- `z_entry_mode` activation beyond placeholder semantics.
- Volatility-regime switching logic.
- Experiment ranking utilities (Phase 3 target).
- Walk-forward optimization enhancements (Phase 4 target).

