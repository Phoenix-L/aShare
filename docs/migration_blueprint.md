# Migration Blueprint (Phase 4: aShare dependency adoption)

## Scope

This phase rewires `aShare` to consume the shared market-data foundation from
`market-data-core` where the Phase 3 surface is available, while preserving
strategy/backtest responsibilities inside `aShare`.

## Boundary decision

### Now delegated to `market-data-core`

- Canonical bar contract lookup (column contract resolution).
- Canonical market-data frame validation entrypoint.

Implementation note: `src/ashare/data/core_bridge.py` delegates to
`market_data_core` modules if importable and falls back to legacy local checks
if not installed.

### Kept local in `aShare`

- Provider implementations (`BaoStockProvider`, `TushareProvider`).
- Provider factory selection via `ASHARE_DATA_PROVIDER`.
- Cache path/layout and cache IO.
- Backtrader feed adapter (`to_backtrader_feed`).
- Strategy logic, backtest runner, experiment/walk-forward orchestration.

### Deferred to later phases

- Provider abstraction unification with `market-data-core` provider/access APIs.
- Calendar policy and adjustment policy alignment once shared APIs are stable.
- Storage layout standardization against `market-data-core` storage contract.

## Risk management

- Conservative adapter pattern: keep existing `ashare.data.loaders` call sites unchanged.
- Runtime fallback preserves behavior in environments where `market-data-core`
  is not yet installed.
- Added tests to verify both fallback behavior and delegation path.

## Developer setup

Recommended local editable setup:

```bash
pip install -e ../market-data-core
pip install -e .
```

If `market-data-core` is temporarily unavailable, local fallback remains active,
with a TODO to remove fallback in Phase 5 when dependency is mandatory.
