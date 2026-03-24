# mean_reversion_advanced — User Manual

## Quick start

Run the shipped experiment spec:

```bash
ashare experiment configs/experiments/mean_reversion_advanced.yaml
```

Run the strategy directly from the CLI with explicit parameters:

```bash
ashare experiment \
  --strategy mean_reversion_advanced \
  --symbols 000001.SZ \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --param z_entry=-1.5,-2.0 \
  --param z_exit=0.3,0.5 \
  --param use_trend_filter=true,false \
  --param atr_ratio_min=0.015,0.02
```

## Parameter guide

### Core signal parameters

- `z_entry`: entry threshold for downside dislocation. More negative means fewer, deeper entries.
- `z_exit`: recovery threshold for closing the trade. Higher values require stronger mean reversion before exit.

### Filters

- `use_trend_filter`: enables the `close > MA120` gate.
- `use_atr_filter`: enables the `ATR3 / close >= atr_ratio_min` gate.
- `atr_ratio_min`: minimum short-horizon ATR ratio required for entry.

### Sizing and MA controls

- `trade_unit`: fixed order size in shares.
- `ma_short`: daily MA period used in z-score computation.
- `ma_trend`: daily MA period used in the trend filter.

## Tuning guidance

### `z_entry`

- move `z_entry` lower when you want deeper dislocations and fewer trades;
- move `z_entry` closer to zero when you want more responsive, higher-frequency entries.

### `z_exit`

- reduce `z_exit` when you want quicker exits and shorter holding periods;
- raise `z_exit` when you want to capture more of the rebound before closing.

### Filters

- if trade count is too low, first inspect whether the trend filter or ATR filter is blocking most signals;
- if `blocked_by_atr` is high in diagnostics, consider lowering `atr_ratio_min`;
- if too many entries occur during weak market structure, re-enable or tighten the trend filter.

## Understanding the output

After a run or experiment, inspect:

- `summary_sorted.csv` for top-ranked configurations;
- `diagnostics_summary.json` for signal-to-trade conversion and block reasons;
- `diagnostics.json` for bar-level signal history;
- `run_result.json` and `config_snapshot.yaml` for exact parameter provenance.

## Recommended tuning workflow

1. start with a narrow `z_entry` / `z_exit` grid;
2. compare trade count versus Sharpe and drawdown;
3. inspect blocked reasons before loosening filters;
4. only then widen the MA or ATR-related parameter range.
