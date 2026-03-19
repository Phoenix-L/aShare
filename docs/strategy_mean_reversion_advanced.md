# Strategy Documentation — `mean_reversion_advanced`

## 1) Strategy logic

`mean_reversion_advanced` is a long-only mean-reversion strategy with optional entry filters.

Core indicators:
- `MA20` (short mean)
- `MA120` (trend reference)
- `ATR14` (volatility proxy)

Derived values:
- `zscore = (close - MA20) / ATR14`
- `ATR Ratio = ATR14 / close`

### Entry
Enter long when all are true:
1. no current position
2. `zscore <= z_entry`
3. trend filter passes (if enabled)
4. ATR filter passes (if enabled)

### Exit
If holding position and `zscore >= z_exit`, close position.

## 2) Filters

### Trend filter
- condition: `close > MA120`
- controlled by `use_trend_filter`
- when disabled, always passes

### ATR filter
- condition: `ATR Ratio >= 0.02`
- controlled by `use_atr_filter`
- when disabled, always passes

## 3) Parameters

- `z_entry` (default `-1.5`)
  - more negative => rarer entries
- `z_exit` (default `0.5`)
  - lower values => earlier exits
- `trade_unit` (default `500`)
  - fixed share size per entry
- `use_trend_filter` (default `true`)
  - protects against catching downtrends, but may reduce trade frequency
- `use_atr_filter` (default `true`)
  - blocks low-volatility setups below the ATR ratio threshold

## 4) Known issues / practical caveats

1. **Trade starvation**
   - Combining strict `z_entry`, trend filter, and ATR filter may produce zero trades.

2. **Threshold sensitivity**
   - Small changes in `z_entry` / `z_exit` can materially change trade count and holding profile.

3. **ATR dependency**
   - If ATR is near zero, strategy skips signal processing for that bar.

4. **Single-position model**
   - No pyramiding/scaling logic; one position opened and later fully closed.
