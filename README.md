# aShare

A-share algo trading research and backtesting framework.

- **Data**: BaoStock API (minute, daily) - free, no token required
- **Engine**: Backtrader
- **Strategies**: Modular, testable strategy modules

## Setup

```bash
pip install -e .
# No token required! BaoStock is free and doesn't need authentication.
# Optionally set ASHARE_DATA_PROVIDER=tushare in .env to use Tushare instead.
```

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
