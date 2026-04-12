# Migration Blueprint (Phase 6: consumer adoption wave 2)

## Scope

This phase extends `aShare` adoption of stable Phase 5 `market-data-core` APIs
while preserving `aShare` ownership of strategy/backtest/research behavior.

## Wave-2 mapping (evidence-based)

### REPLACE_NOW

- Canonical load entrypoints for daily and 30m bars:
  - `ashare.data.loaders.load_daily` now prefers `market_data_core.access.load_daily`.
  - `ashare.data.loaders.load_minute_30` now prefers `market_data_core.access.load_30m` / `load_minute_30`.

### WRAP_NOW

- Validation boundary:
  - `ashare.data.core_bridge.validate_canonical_frame` now runs
    `market_data_core.validation.validate_bars` when available, then preserves
    legacy frame-shape checks for safety.
- Dataset metadata inspection:
  - local wrapper functions expose manifest-driven upstream APIs:
    `list_available_datasets` / `inspect_available_dataset`.
- Calendar boundary:
  - wrapper helpers added for `session_open_anchors` and `is_session_aligned`
    to keep a stable local compatibility import path.

### KEEP_LOCAL

- Concrete BaoStock/Tushare provider adapters.
- Local cache IO and path conventions.
- Backtrader feed adapters and strategy-specific preprocessing.
- Backtest execution, experiments, walk-forward orchestration, reporting.

### DEFER

- Upstream ingest orchestration (`ingest_bars`) adoption.
- Upstream transform layer (`resample`, `adjust`) adoption.
- Removal of runtime fallback path when `market-data-core` is unavailable.

## Risk management

- Keep current loader function signatures unchanged for callers.
- Prefer upstream APIs only when importable; fallback keeps behavior in
  environments that have not yet installed `market-data-core`.
- Add tests for both delegation and fallback paths.

## Contract alignment notes

- Canonical bar validation now aligns with upstream strict validation semantics.
- Loader delegation aligns dataset reads with upstream access contracts.
- Dataset metadata is now treated as manifest-driven when upstream is available.
