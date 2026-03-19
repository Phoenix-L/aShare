# Mean Reversion Advanced Strategy

## 1. Strategy Overview

`mean_reversion_advanced` is a long-only mean-reversion strategy implemented in Backtrader. Its core idea is to buy short-term downside overreactions after price has moved sufficiently below a short moving average on an ATR-normalized basis, or after price has dropped sufficiently from a recent intraday closing high, then exit when price mean-reverts back toward the average. The strategy is designed to capture short-term overreaction reversals rather than trend continuation or breakout behavior.

In the current implementation, the strategy does **not** maintain a permanent core position, does **not** pyramid, and uses a single fixed-size entry each time all entry conditions pass.

## 2. Signal Components

### 2.1 Signal Mode

The strategy supports two primary entry-trigger modes:

- `signal_mode = "zscore"` *(default)*: use the ATR-normalized z-score as the primary signal
- `signal_mode = "excursion"`: use a close-based downside excursion from the rolling maximum close as the primary signal

This switch affects only the entry trigger. The exit rule remains z-score-based in both modes.

### 2.2 Z-Score

The entry and exit trigger is an ATR-normalized z-score:

- `zscore = (close - MA20) / ATR14`

This is computed every bar using:

- `close`: current bar close
- `MA20`: 20-bar simple moving average
- `ATR14`: 14-bar Average True Range

Role in the strategy:

- **Entry trigger**: the bar becomes a candidate entry when `zscore <= z_entry`
- **Exit trigger**: an open position is closed when `zscore >= z_exit`

Because ATR is in the denominator, the z-score scales the deviation from the short mean by recent volatility rather than by raw price distance.

### 2.3 Close-Based Excursion Signal

When `signal_mode == "excursion"`, the primary entry trigger uses the current intraday close and the rolling maximum intraday close:

- `rolling_max_close = highest(close, excursion_lookback_bars)`
- `excursion = (close - rolling_max_close) / rolling_max_close`

Properties:

- `excursion <= 0`
- `0` means the bar is at the local rolling close high
- more negative values mean a deeper drop from the recent closing peak

Trigger rule:

- the bar becomes a candidate entry when `excursion <= -excursion_threshold`

Purpose:

- capture directional downside displacement directly from recent intraday closes
- allow excursion to act as the primary signal instead of as a secondary gate

### 2.4 ATR Filter (Volatility)

The strategy also computes an ATR ratio:

- `atr_ratio = ATR3 / close`

This is used as a volatility gate via the ATR filter. The strategy intentionally uses a shorter ATR for this gate than for the z-score calculation.

Current behavior:

- canonical params: `use_atr_filter`, `atr_ratio_min`
- legacy compatibility params: `use_art_filter`, `art_threshold`
- effective default behavior: ATR filter is enabled, and the default threshold is `0.02` if neither canonical nor legacy override is supplied

Purpose:

- reject low-volatility setups where the mean-reversion signal may be too small or noisy
- require enough very recent realized range for the z-score signal to matter

Exact pass condition:

- ATR filter passes when either the filter is disabled or `atr_ratio >= atr_ratio_min`

### 2.5 Legacy Multi-Day Excursion Filter

The strategy optionally uses a multi-day excursion ratio computed from a rolling high-low range:

- highest high over `excursion_window`
- lowest low over `excursion_window`
- `excursion_ratio = (rolling_high - rolling_low) / close`

Purpose:

- detect whether the market has actually displaced enough over the recent lookback window
- avoid reacting to tiny local deviations that satisfy z-score math but lack meaningful range expansion

Current behavior:

- disabled unless `use_multi_day_excursion` is `True`
- when enabled, the bar must have enough history for the excursion value to be defined
- pass condition: `excursion_ratio >= excursion_min`
- this filter only applies when `signal_mode == "zscore"`
- this filter is bypassed when `signal_mode == "excursion"`

### 2.6 Trend Filter (MA120)

The trend filter is a simple long-only direction gate based on a 120-bar moving average:

- trend filter passes when `close > MA120`

Purpose:

- reduce entries against broader downside pressure
- keep the mean-reversion strategy from repeatedly buying into persistent downtrends

Current behavior:

- controlled by `use_trend_filter`
- when disabled, it always passes

## 3. Entry Logic

A bar generates an **entry signal candidate** when:

- `signal_mode == "zscore"` and `zscore <= z_entry`, or
- `signal_mode == "excursion"` and `excursion <= -excursion_threshold`
- and there is no current position

An actual entry is executed only when **all** of the following are true:

1. the active primary signal triggers
2. trend filter passes
3. ATR filter passes
4. legacy excursion filter passes *(only in `signal_mode == "zscore"` when `use_multi_day_excursion` is enabled)*
5. there is no open position

If the entry candidate fails one or more filters, the strategy records the failure reasons in diagnostics under `blocked_by`.

Important current details:

- if `ATR14 == 0`, the strategy returns early and performs no signal processing for that bar
- `entry_signal` reflects whichever primary signal is active for the run
- `blocked_by_excursion` only applies to the legacy multi-day excursion filter path in `signal_mode == "zscore"`

## 4. Exit Logic

The exit rule is simple and exact:

- if the strategy holds a position **and** `zscore >= z_exit`, it closes the full position

There is no additional stop-loss, trailing exit, or profit-target logic in the current implementation.

On exit, if the strategy stored an entry reason for the open trade, it appends a trade-level diagnostic record containing:

- the recorded entry context
- an exit reason containing the exit-bar z-score

## 5. Position Sizing

Position sizing is fixed-size and explicit:

- `self.buy(size=self.p.trade_unit)`

This means:

- each entry buys exactly `trade_unit` shares
- there is no volatility scaling, cash-based sizing, or adaptive sizing inside the strategy
- the strategy currently behaves as a one-position model: enter once, exit fully, then wait for the next signal

## 6. Diagnostics

The strategy emits per-bar diagnostics through `self.diagnostics`, and the engine aggregates them into `diagnostics_summary.json`.

### Per-bar diagnostics fields

Each processed bar appends a record containing:

- `datetime`
- `zscore`
- `signal_mode`
- `signal_trigger`
- `trend_ok`
- `atr_ok`
- `art_ok` *(legacy alias preserved in output)*
- `atr_ratio`
- `excursion`
- `excursion_trigger`
- `excursion_ratio`
- `excursion_ok`
- `entry_signal`
- `executed`
- `blocked_by`

### Aggregated diagnostics summary fields

`runner.py` currently aggregates the following counters:

- `total_bars`
- `entry_signals`
- `executed_trades`
- `blocked_by_trend`
- `blocked_by_atr`
- `blocked_by_art` *(legacy alias, same count as `blocked_by_atr`)*
- `blocked_by_excursion`
- `blocked_by_multiple`

How to interpret the key fields:

- **entry_signals**: number of bars where the active primary signal was strong enough to trigger a candidate entry
- **executed_trades**: candidate entries that survived all filters and executed a buy
- **blocked_by_atr**: candidate entries rejected by the ATR ratio filter
- **blocked_by_excursion**: candidate entries rejected by the legacy multi-day excursion filter while running in `signal_mode == "zscore"`
- **blocked_by_trend**: candidate entries rejected by the MA120 trend filter

## 7. Strengths & Limitations

### Strengths

- ATR-normalized z-score makes entry logic volatility-aware
- close-based excursion mode offers a directional downside trigger without relying on MA distance
- optional filters make the strategy modular and easy to tune in experiments
- multi-day excursion can help separate meaningful displacement from small noisy deviations
- detailed diagnostics make filter impact measurable in downstream research analysis

### Limitations

- can become over-filtered and produce very few trades
- fixed-size entries ignore portfolio volatility, account equity changes, and signal strength
- no stop-loss or advanced risk management layer exists in the strategy itself
- single-position design limits flexibility for scaling in or managing partial exits
- results can be highly sensitive to `signal_mode`, `z_entry`, `z_exit`, `excursion_lookback_bars`, `excursion_threshold`, `atr_ratio_min`, `excursion_min`, and `excursion_window`
- if ATR is very small or zero, signal processing is skipped for that bar
