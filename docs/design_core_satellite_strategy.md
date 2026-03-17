# Core–Satellite Mean Reversion Strategy Design (Phase 2)

## Overview
Phase 2 implements a parameterized Core–Satellite mean reversion strategy where all entry/exit thresholds are externally configurable.

## Strategy Parameters
The strategy now exposes the following Backtrader parameters:

- `core_position`: baseline long-only core sleeve (default `2000` shares)
- `satellite_max`: cap for tactical sleeve (default `2000` shares)
- `trade_unit`: per-order size for satellite sleeve (default `500` shares)
- `z_entry`: list of Z-score entry thresholds (default `[-1.5, -2.0, -2.5]`)
- `z_exit`: list of Z-score exit thresholds (default `[0.8, 1.5]`)
- `trend_filter`: enable/disable trend gating for new satellite buys (default `True`)

All parameters are overridable from both experiment and walk-forward workflows through `strategy_params`.

## Configuration File
Reference strategy configuration lives in:

- `configs/core_satellite.yaml`

This file defines strategy name and default thresholds. It can be loaded through `ashare.config.loader.load_strategy_config`.

## Entry/Exit Design
- Z-score is computed as `(Close - SMA20) / ATR14`.
- For entries, strategy iterates `z_entry` list and buys `trade_unit` for each satisfied threshold, bounded by `satellite_max`.
- For exits, strategy iterates `z_exit` list and sells `trade_unit` for each satisfied threshold, but never sells below `core_position`.

## Trend Filter
When `trend_filter=True`, new satellite buys are blocked if `price < MA120`.
Core position establishment is unaffected by trend filter.

## CLI Override Design
`ashare experiment` and `ashare walk-forward` accept repeated `--param key=v1,v2` inputs.

For list-typed strategy defaults (e.g. `z_entry`, `z_exit`), CLI parses comma-separated values into a single list parameter override rather than a Cartesian scalar sweep.

Example:

```bash
ashare experiment \
  --strategy core_satellite \
  --symbols 002850.SZ \
  --param z_entry=-1.5,-2.0,-2.5 \
  --param z_exit=0.8,1.2,1.5 \
  --start 2024-01-01 \
  --end 2024-12-31
```

Behavior:
- `z_entry` is passed as `[-1.5, -2.0, -2.5]`
- `z_exit` is passed as `[0.8, 1.2, 1.5]`
- scalar params still expand as standard parameter grids.
