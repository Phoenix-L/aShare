# mean_reversion_advanced — Strategy

## Core concept

`mean_reversion_advanced` is a long-only intraday mean-reversion strategy. It buys short-term downside dislocations when price falls far enough below a short moving average on an ATR-normalized basis, then exits after price mean-reverts back through a configurable z-score threshold.

## Signal definition

### Z-score

The primary signal is an ATR-normalized deviation from the short moving average:

```text
zscore = (close - MA20) / ATR14
```

Where:

- `close` is the current intraday bar close.
- `MA20` is a 20-day simple moving average computed from the daily-resampled feed.
- `ATR14` is a 14-bar ATR computed on the intraday execution feed.

Interpretation:

- more negative z-scores indicate a deeper short-term downside stretch versus the short mean;
- less negative or positive z-scores indicate recovery toward or above the mean.

## Entry conditions

A long entry is allowed only when all of the following are true:

1. no position is currently open;
2. `zscore <= z_entry`;
3. the trend filter passes, if enabled;
4. the ATR filter passes, if enabled.

### Trend filter

The trend gate is:

```text
close > MA120
```

- `MA120` is a 120-day simple moving average computed from the daily-resampled feed.
- Controlled by `use_trend_filter`.
- Purpose: avoid buying mean-reversion dips inside broader downtrends.

### ATR filter

The volatility gate uses a short ATR ratio:

```text
atr_ratio = ATR3 / close
```

The filter passes when:

```text
atr_ratio >= atr_ratio_min
```

- `ATR3` is a 3-bar ATR computed on the intraday execution feed.
- Controlled by `use_atr_filter`.
- If no explicit threshold is supplied, the code falls back to `0.02`.
- Legacy aliases `use_art_filter` and `art_threshold` are still accepted for backward compatibility, but the canonical naming is ATR.

## Exit logic

The strategy exits a full position when:

```text
zscore >= z_exit
```

There is no built-in take-profit ladder, stop-loss, or partial scaling logic in this strategy. The trade model is one entry, one full exit.

## Parameters

| Parameter | Purpose |
| --- | --- |
| `trade_unit` | Fixed share size per entry order. |
| `z_entry` | Entry threshold; more negative values make entries rarer and deeper. |
| `z_exit` | Exit threshold; lower values exit earlier, higher values wait for stronger recovery. |
| `use_trend_filter` | Enables the `close > MA120` trend gate. |
| `use_atr_filter` | Enables the `ATR3 / close` volatility gate. |
| `atr_ratio_min` | Minimum ATR ratio required when the ATR filter is enabled. |
| `ma_short` | Daily moving-average period used for the short mean, default 20. |
| `ma_trend` | Daily moving-average period used for the trend filter, default 120. |
| `use_art_filter` | Deprecated alias for `use_atr_filter`. |
| `art_threshold` | Deprecated alias for `atr_ratio_min`. |

## Trading workflow summary

1. Read the current intraday close.
2. Reference `MA20` and `MA120` from the daily-resampled feed.
3. Compute `zscore` and `atr_ratio`.
4. Check entry gates (`z_entry`, trend, ATR).
5. Submit a fixed-size buy order when all gates pass.
6. While in position, keep evaluating `z_exit`.
7. Close the full position once the recovery threshold is reached.

## Practical tuning notes

- Lowering `z_entry` from `-1.5` to `-2.0` usually reduces trade count and requires deeper selloffs before entry.
- Raising `z_exit` usually holds trades longer and asks for stronger reversion before exit.
- Disabling the trend filter increases opportunity count, but can materially increase exposure to persistent downtrends.
- Lowering `atr_ratio_min` relaxes the volatility gate and may admit more noisy setups.
