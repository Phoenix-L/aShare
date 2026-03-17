# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Phoenix-L/aShare/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/Phoenix-L/aShare/compare/v0.2.0...v0.3.0
