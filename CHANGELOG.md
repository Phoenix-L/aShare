# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] - 2026-03-24

### Added

- Experiment-level dashboard (cross-run analytics)
- latest/previous experiment pointers
- Research notebook layer
- add_shock_scores (list per trade)
- ladder diagnostics in signals.csv:
  - add_executed
  - execution_type
  - drop_from_last_leg_pct
  - bars_since_last_leg

### Changed

- Unified exit logic into shared execution engine
- Recovery target now anchor-based (L + r(A - L))
- Documentation fully synchronized (README, strategy, architecture, usage)

### Removed

- add_score_min/max/avg from trades.csv

### Fixed

- signal logging timing (entry/add execution consistency)
- recovery target incorrect reference bug

## [0.6.0] - 2026-03-21

### Added

- Added canonical v0.6.0 strategy documentation under `strategies/shock_reversion_intraday/`.
- Added a runnable experiment template for `shock_reversion_intraday`.
- Added release notes for `v0.6.0`.

### Changed

- Removed deprecated compatibility metrics from shock-reversion release artifacts and standardized decimal-only metric outputs.
- Stabilized `selection_report_v2.csv` around a deterministic scoring and ranking flow.
- Bumped package version metadata to `0.6.0`.

## [0.5.0] - 2026-03-19

### Added

- Standardized research documentation for `mean_reversion_advanced` into dedicated strategy, system architecture, and user manual documents.
- Added a parallel three-document research set for `shock_reversion_intraday`.
- Added release notes for `v0.5.0`.

### Changed

- Promoted the standardized strategy research docs under `research/` so both strategies share the same documentation layout.
- Bumped package version metadata to `0.5.0`.


## [0.3.0] - 2025-03-17

### Added

- **Experiment specification (YAML)** — Declarative experiment specs with `experiment_name`, `strategy`, `symbols`, `date_range`, `parameters`, `grid_search`, and optional `execution` (e.g. `initial_cash`, `commission`). Run with `ashare experiment path/to/spec.yaml`.
- **Grid search engine** — Cartesian product expansion over parameter grids; supports scalar and list-valued strategy parameters.
- **Core–satellite mean reversion strategy** — Parameterized core/satellite position sizing, Z-score entry/exit bands, trend filter, and configurable `z_entry_mode` placeholder for future entry logic.
- **Walk-forward optimization** — CLI command `ashare walk-forward` with configurable train/test windows and parameter grid; outputs per-window best params and out-of-sample metrics.
- **Experiment runner** — Multi-symbol, multi-parameter sweep with CSV results and optional YAML spec; outputs `metrics.json` and `config_snapshot.yaml` per run when using a spec.
- **CLI user manual** — Documentation for the core–satellite mean reversion strategy and usage.

### Changed

- **Experiment command** — Supports both YAML spec file and ad-hoc `--strategy`, `--symbols`, `--param`, `--start`, `--end`; spec-driven runs write to `outputs/<experiment_name>/run_XXX/`.
- **Strategy registry** — Added `core_satellite` (CoreSatelliteMeanReversion) alongside `mid_freq_ma`.

### Improved

- **Research workflow** — Single backtest, parameter-sweep experiments, and walk-forward validation are all available from the CLI.
- **Reproducibility** — Experiment specs and config snapshots make runs reproducible and auditable.
- **Documentation** — System architecture, PRD, design docs, and strategy-specific manuals aligned with current features.

### Fixed

- (None in this release.)

[Unreleased]: https://github.com/Phoenix-L/aShare/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/Phoenix-L/aShare/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/Phoenix-L/aShare/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/Phoenix-L/aShare/compare/v0.3.0...v0.5.0
[0.3.0]: https://github.com/Phoenix-L/aShare/compare/v0.2.0...v0.3.0
