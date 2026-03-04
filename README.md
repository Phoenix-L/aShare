# aShare

A-share algo trading research and backtesting framework.

- **Data**: Tushare API (minute, daily)
- **Engine**: Backtrader
- **Strategies**: Modular, testable strategy modules

## Setup

```bash
pip install -e .
cp .env.example .env   # Set TUSHARE_TOKEN
```

## Usage

```bash
ashare backtest --symbol 000001.SZ --strategy mid_freq_ma --start 2024-01-01 --end 2024-06-30
# or
python -m ashare backtest --symbol 000001.SZ --strategy mid_freq_ma --start 2024-01-01 --end 2024-06-30
```

## Structure

- `src/ashare/config/` — Capital, fees, symbols, date ranges
- `src/ashare/data/` — Tushare client, loaders, Backtrader normalizers
- `src/ashare/strategies/` — Strategy modules
- `src/ashare/engine/` — Cerebro builder, analyzers, runner
- `src/ashare/constraints/` — A-share rules (e.g. 100-share lot)

Outputs and logs are written to `outputs/` and `logs/` (gitignored).
