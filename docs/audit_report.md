# aShare Repository Audit Report (Code-as-Truth)

## Scope and method
This audit compares implemented behavior in `src/` against current repository documentation in `docs/` and `README.md`.

Primary code references audited:
- CLI: `src/ashare/cli.py`
- Engine: `src/ashare/engine/runner.py`, `src/ashare/research/experiment_runner.py`, `src/ashare/experiment/grid.py`
- Strategy: `src/ashare/strategies/mean_reversion_advanced.py`, `src/ashare/strategies/components/*`
- Data: `src/ashare/data/loaders.py`, `src/ashare/data/providers/*`, `src/ashare/data/normalizers.py`, `src/ashare/data/tushare_client.py`
- Config/spec: `src/ashare/experiment/spec.py`, `src/ashare/config/loader.py`, `src/ashare/config/settings.py`
- Outputs: `src/ashare/cli.py`, `src/ashare/experiment/result.py`, `src/ashare/research/experiment_runner.py`

---

## 1) Implemented system baseline (verified)

### CLI layer
Implemented commands:
- `ashare backtest`
- `ashare experiment`
- `ashare walk-forward`
- `ashare sanitytest daily`
- `ashare sanitytest minute30`

`experiment` has two execution modes:
1. **YAML mode** (`ashare experiment <spec.yaml>`)
2. **Direct CLI mode** (`ashare experiment --strategy ... --symbols ... --start ... --end ... --param ...`)

Date overrides:
- `--start` and `--end` are validated as strict `YYYY-MM-DD`.
- In YAML mode, CLI date overrides replace YAML `date_range`.

Parameter overrides (`--param key=v1,v2,...`):
- Parsed and type-coerced (`bool`, `int`, `float`, fallback `str`).
- In YAML mode:
  - single value => overrides `parameters[key]`
  - multiple values => overrides/creates `grid[key]`

### Engine layer
- `run_backtest()` builds Backtrader `Cerebro`, injects data feed, strategy, analyzers, runs simulation, returns metrics dict.
- Grid expansion exists in **two places**:
  - `engine.runner.expand_grid`
  - `experiment.grid.generate_parameter_sets`
- Experiment execution exists in **two pathways**:
  - YAML mode in CLI (writes per-run files under `outputs/<experiment_name>/run_xxx`)
  - Generic runner `run_experiment` (writes `experiments/experiment_<timestamp>/results.csv` + `config.json`)

### Strategy layer (mean_reversion_advanced)
Implemented behavior:
- Indicators: SMA(20), SMA(120), ATR(14)
- Entry signal: `zscore <= z_entry`
- Exit signal: `zscore >= z_exit`
- Trend filter (optional): `close > ma120`
- ART filter (optional): `art = atr / close`, requires `art >= 0.02`
- Position model: single long position, fixed-size buys (`trade_unit`), closes entire position on exit.

### Data layer
- Loader API: `load_minute_30`, `load_daily`
- Provider abstraction: `baostock` (default), `tushare` (env-selectable)
- Cache layer integrated in loaders before/after provider fetch.
- Required normalized schema enforced:
  - `DatetimeIndex`
  - columns: `open, high, low, close, volume, turnover_rate`

### Config/spec system
- Runtime trading config via `BacktestConfig` (`initial_cash`, `commission`, `stamp_duty`, `slippage_perc`)
- Experiment YAML spec requires:
  - `experiment_name`, `strategy`, `symbols`, `date_range.start`, `date_range.end`
- Optional sections:
  - `parameters`
  - `grid_search`
  - `execution`

### Outputs
YAML experiment mode:
- `outputs/<experiment_name>/run_xxx/metrics.json`
- `outputs/<experiment_name>/run_xxx/config_snapshot.yaml`
- `outputs/<experiment_name>/summary.csv`
- `outputs/<experiment_name>/summary_sorted.csv`

Direct `run_experiment` mode:
- `experiments/experiment_<timestamp>/results.csv`
- `experiments/experiment_<timestamp>/config.json`

---

## 2) Documentation gaps and inconsistencies

### Outdated docs
1. `docs/system_architecture.md` contained future/idealized content and mismatched output claims (e.g., equity/trade artifacts not produced by current core paths).
2. `docs/PRD-aShare.md` had roadmap/feature assumptions not fully synchronized with current dual experiment flows and actual output formats.
3. Core-satellite-specific docs (`design_core_satellite_strategy.md`, `user_manual_core_satellite_strategy.md`, `strategy_core_satellite_mean_reversion.md`) do not represent current primary CLI/experiment usage guidance and create doc fragmentation.

### Missing docs
1. No focused strategy document for `mean_reversion_advanced` despite being a primary experimental strategy.
2. No explicit repository audit artifact summarizing code-vs-doc deltas.
3. No practical unified user manual covering both experiment modes and override precedence end-to-end.

### Features implemented but poorly documented
1. Dual experiment storage roots (`outputs/...` vs `experiments/...`).
2. YAML `execution` overrides for broker parameters.
3. `--param` merge semantics (single vs multi-value behavior).
4. `summary.csv` generation path and ranking behavior.
5. Provider selection by `ASHARE_DATA_PROVIDER` and schema validation contracts.

### Features documented/implied but not implemented consistently
1. Single canonical experiment pipeline is implied in old docs, but code currently has two pipelines with different artifact contracts.
2. Some older docs imply richer output artifact set (e.g., curve/trade exports) that are not part of current default run outputs.

---

## 3) Architectural inconsistency findings (important)

1. **Two experiment engines** exist simultaneously:
   - YAML path in CLI
   - `run_experiment` path in research module
   This creates operational inconsistency in output schema and directories.

2. **Two grid expansion implementations** (`expand_grid` vs `generate_parameter_sets`) duplicate responsibility.

3. **CLI backtest currently does not expose strategy params directly**, while experiment mode does; first-time users may expect parity.

4. **Summary generation only exists for YAML experiment path**, while direct experiment path outputs `results.csv` only.

---

## 4) Realignment actions taken in this documentation phase

- Rebuilt `docs/system_architecture.md` from code behavior.
- Rebuilt `docs/PRD-aShare.md` to describe current product reality.
- Created practical `docs/user_manual.md` with runnable commands and override examples.
- Created `docs/strategy_mean_reversion_advanced.md` for strategy-level logic and caveats.
- Removed outdated fragmented docs to keep documentation surface aligned.

---

## 5) Recommended next technical follow-ups (not changed in this phase)

1. Converge experiment execution into one canonical pipeline/output contract.
2. Consolidate grid expansion into one module.
3. Optionally add strategy-parameter override support to `backtest` command.
4. Unify result artifacts (`summary.csv` generation for all experiment entry paths).
