# shock_reversion_intraday — System Architecture

**Version:** v0.6.0

## End-to-End Data Flow

`Tushare → Backtrader → Strategy → Diagnostics → Reports`

1. Tushare loaders provide the 30-minute bar data.
2. Backtrader runs the execution loop and analyzers.
3. `ShockReversionIntradayStrategy` evaluates excursion and optional shock-score eligibility.
4. Diagnostics aggregate signal counts, block reasons, trade-quality metrics, and exit-quality metrics.
5. Reporting writes run artifacts such as `trades.csv`, `diagnostics_summary.json`, `run_performance_report.csv`, `summary.csv`, and `selection_report_v2.csv`.

## Modules

### Strategy module

- `src/ashare/strategies/shock_reversion_intraday.py`
- Owns signal generation, order placement, position lifecycle tracking, and trade export.

### Indicator / scoring components

- excursion is derived from rolling intraday close anchors
- shock score is computed from depth, speed, stabilization, and noise penalty components
- shared execution helpers track MFE, MAE, ETD, and exit targets

### Engine runner

- `src/ashare/engine/runner.py`
- validates parameters, runs Backtrader, computes diagnostics summaries, and persists per-run artifacts

### Diagnostics engine

- trade- and signal-level diagnostics are aggregated into normalized summary metrics
- output is designed for downstream selection and reporting rather than display formatting

### Reporting layer

- `src/ashare/evaluation/run_report.py`
- `src/ashare/experiment/result.py`
- `src/ashare/research/config_selector.py`

This layer converts run artifacts into cross-run reports and ranked selections.

## Metric Normalization Standard

- All return and drawdown values are stored as decimals.
- Computation stays unit-consistent end to end.
- Display formatting, such as rendering `0.05` as `5.00%`, is separated from stored values and CLI presentation.
- Deprecated percent-style compatibility fields have been removed from release artifacts.

## Selection Pipeline

The pre-ladder selection flow is intentionally minimal:

1. Basic viability filters remove runs with too few trades, non-positive portfolio return, or excessive drawdown.
2. A scoring model ranks surviving runs using normalized return, capital efficiency, ETD penalty, and trade-count support.
3. Ranking is deterministic because ties break on score, return, efficiency, trade count, and `run_id`.

## Current Implementation Boundaries

- No ladder entry manager yet.
- Position sizing is fixed per run via `trade_unit`.
- Margin can be enabled, but optimization of financing usage is not yet part of the ranking model.
