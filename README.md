# aShare

A-share algo trading research and backtesting framework.

## Version

Current version: v0.7.0

- **Data**: BaoStock API (minute, daily) - free, no token required
- **Engine**: Backtrader
- **Strategies**: Modular, testable strategy modules

## Setup

```bash
# Recommended during migration: install shared core first (editable), then aShare.
pip install -e ../market-data-core
pip install -e .
# No token required! BaoStock is free and doesn't need authentication.
# Optionally set ASHARE_DATA_PROVIDER=tushare in .env to use Tushare instead.
```

If `market-data-core` is not available in your environment yet, aShare keeps a
compatibility fallback for canonical bar validation so existing local workflows
continue to run.

## Usage

```bash
ashare backtest --symbol 000001.SZ --strategy mid_freq_ma --start 2024-01-01 --end 2024-06-30
# or
python -m ashare backtest --symbol 000001.SZ --strategy mid_freq_ma --start 2024-01-01 --end 2024-06-30
```

## Structure

- `src/ashare/config/` — Capital, fees, symbols, date ranges
- `src/ashare/data/` — Data providers (BaoStock/Tushare), loaders, Backtrader normalizers
- `src/ashare/strategies/` — Strategy modules
- `src/ashare/engine/` — Cerebro builder, analyzers, runner
- `src/ashare/constraints/` — A-share rules (e.g. 100-share lot)

Outputs and logs are written to `outputs/` and `logs/` (gitignored).


## Migration status (Phase 4)

- Delegated to `market-data-core` when available: canonical bar columns and canonical frame validation (`ashare.data.core_bridge`).
- Kept local in `aShare`: provider implementations (BaoStock/Tushare), cache layout, Backtrader feed adapters, strategies, and experiment orchestration.
- Deferred: provider/access API unification and policy-level calendar/adjustment normalization once those APIs are finalized in `market-data-core`.
