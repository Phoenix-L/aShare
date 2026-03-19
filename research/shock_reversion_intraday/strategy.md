# shock_reversion_intraday — Strategy

## Core concept

`shock_reversion_intraday` is an event-driven intraday reversion strategy. It looks for sharp downside excursions from a recent rolling high, enters after a sufficiently deep shock, and exits through a shared exit engine that balances recovery, take-profit, stop-loss, and maximum holding time.

## Signal definition

The strategy anchors the current bar to a recent rolling maximum close:

```text
anchor_price = rolling_max(close, N)
excursion = (close - anchor_price) / anchor_price
```

Where:

- `N = excursion_lookback_bars`;
- `anchor_price` is the highest close over the rolling lookback;
- `excursion` is non-positive, with more negative values representing deeper selloffs from the local anchor.

## Entry conditions

A long entry is allowed only when all of the following are true:

1. no position is open;
2. `excursion <= -excursion_threshold`;
3. the trend filter passes, if enabled;
4. no order is already active.

### Trend filter

If enabled, the strategy compares the intraday close against a daily-resampled moving average:

```text
close > trend_MA
```

- The period is controlled by `trend_ma_period`.
- This filter is optional and can be disabled.

## Exit logic

The strategy uses a shared exit engine with four exit paths.

### Recovery target

The strategy freezes the entry anchor and computes a partial recovery objective:

```text
recovery_target = entry_price + recovery_frac * (anchor_price_at_entry - entry_price)
```

### Take profit

```text
take_profit_price = entry_price * (1 + take_profit_pct)
```

### Stop loss

```text
stop_price = entry_price * (1 - stop_loss_pct)
```

### Max hold

The trade is forcibly closed once `holding_bars >= max_hold_bars`.

### Effective exit rule

The exit engine closes the position when the first of these conditions is met:

- price reaches the effective profit target derived from recovery and take-profit;
- price hits the stop-loss threshold;
- holding time reaches `max_hold_bars`.

## Parameters

| Parameter | Purpose |
| --- | --- |
| `trade_unit` | Fixed share size per entry order. |
| `excursion_lookback_bars` | Rolling lookback window for the anchor price. |
| `excursion_threshold` | Minimum shock depth required to enter. |
| `use_trend_filter` | Enables the daily trend gate. |
| `trend_ma_period` | Daily moving-average period used by the trend filter. |
| `recovery_frac` | Fraction of the shock to recover before the recovery exit can fire. |
| `take_profit_pct` | Absolute profit target from entry price. |
| `stop_loss_pct` | Maximum tolerated loss from entry price. |
| `max_hold_bars` | Maximum number of bars a trade can remain open. |

## Key insights

- Small `excursion_threshold` values often react to noise and produce many weak signals.
- Larger `excursion_threshold` values usually create fewer but stronger shock events.
- Higher `recovery_frac` values demand a more complete rebound before the recovery exit can trigger.
- Tight `stop_loss_pct` settings reduce downside per trade but may prematurely cut otherwise recoverable events.
