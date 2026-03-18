# Mean Reversion Advanced User Manual

## Multi-Day Excursion Filter

The multi-day excursion filter measures the recent trading range as the rolling highest high minus the rolling lowest low over a configurable lookback window. The raw excursion is then normalized by the current close price to produce an excursion ratio.

This filter is intended to confirm that a mean-reversion setup is happening alongside a meaningful short-term displacement, instead of reacting to very small and noisy moves. In practice it complements the z-score entry trigger and the ART volatility filter without being hardcoded into the core strategy architecture.

### Parameters

- `use_multi_day_excursion`: enable or disable the filter.
- `excursion_window`: rolling lookback window used for the highest-high/lowest-low calculation.
- `excursion_min`: minimum normalized excursion ratio required for entry.

### CLI Example

```bash
ashare experiment \
  configs/experiments/mean_reversion_advanced.yaml \
  --param use_multi_day_excursion=true \
  --param excursion_min=0.01 \
  --param excursion_window=3
```
