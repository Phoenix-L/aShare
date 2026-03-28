# Regime State Machine Research Module

This folder contains a **parallel research prototype** for classifying market structure into:

- **Oscillating**
- **Transition**
- **Trending**

It is intentionally separate from the existing `shock_reversion_intraday` implementation.
No strategy logic is modified here.

## 1) Conceptual regime definitions

### Oscillating
Price repeatedly mean-reverts around a local equilibrium anchor.
Typical signatures:
- low trend efficiency
- low persistence
- high snapback rate
- distance from equilibrium is not sustained at large magnitude

### Trending
Price displacement persists away from equilibrium.
Typical signatures:
- high trend efficiency
- high persistence
- sustained larger distance from equilibrium
- low snapback rate

### Transition
Intermediate/mixed state where oscillation quality degrades and trend signatures strengthen.

## 2) Feature definitions (interpretable)

Implemented in `regime_features.py` on OHLCV input.

1. **Equilibrium anchor**
   - `equilibrium_short`: rolling MA(20)
   - `equilibrium_long`: rolling MA(40)
   - `equilibrium`: 50/50 blend of the two

2. **Distance from equilibrium**
   - `distance_from_equilibrium = (close - equilibrium) / equilibrium`

3. **Trend efficiency** (window `N=20` default)
   - `abs(close_t - close_{t-N}) / sum(abs(diff(close)))`
   - clipped to [0, 1]

4. **Persistence**
   - average of:
     - same-sign return fraction (rolling)
     - sign autocorrelation transformed to [0,1]

5. **Snapback / reversion quality**
   - excursion event when `|distance| >= threshold` (default 2%)
   - success if `|distance| <= reset_band` (default 0.5%) within `H` bars (default 10)
   - `snapback_rate` = rolling success ratio over recent excursions

## 3) State machine logic

Implemented in `regime_rules.py` with deterministic thresholds.

### Rule intent
- **Oscillating** if trend and persistence are low while snapback is high.
- **Trending** if trend and persistence are high, displacement is large, and snapback is low.
- Otherwise **Transition**.

### Anti flip-flop control
- Uses **dwell bars / hysteresis** (`dwell_bars=3` default).
- State only changes after a candidate state persists for the dwell duration.

### Transition signal
`transition_signal=True` on:
- `Oscillating -> Transition`
- `Transition -> Trending`

This is a practical early-warning marker for oscillation breakdown.

## 4) Outputs

For each ticker under `outputs/<ticker>/`:

- `regime_state.csv`
- `regime_transition_events.csv`

`regime_state.csv` includes:
- datetime
- close
- equilibrium
- distance_from_equilibrium
- trend_efficiency
- persistence
- snapback_rate
- regime_state
- transition_signal

Also generated in `outputs/`:
- `state_behavior_summary.csv`
- `transition_signal_summary.csv`
- `config_snapshot.json`

## 5) Backtest / event-study plan

Implemented in `regime_backtest.py`.

### Universe
Default tickers:
- `002850.SZ`
- `000001.SZ`
- `600519.SH`

You can provide 2–5+ relevant additional tickers via CLI.

### Evaluation dimensions
1. **State behavior**
   - average forward return by state (default +5 bars)
   - average snapback probability by state
   - average trend efficiency by state

2. **Transition signal quality**
   Uses practical future-window "breakdown" labels based on:
   - sustained displacement from equilibrium
   - failed return to reset band within horizon `H`

   Reports:
   - precision
   - recall
   - false alarm rate
   - average lead time before confirmed trending state

## 6) How to run

Prepare OHLCV CSV files in:

`data/research/ohlcv/<ticker>.csv`

Required columns:

`datetime, open, high, low, close, volume`

Run:

```bash
python research/regime_state_machine/regime_backtest.py \
  --tickers 002850.SZ 000001.SZ 600519.SH 300750.SZ 601318.SH \
  --input-dir data/research/ohlcv \
  --output-dir research/regime_state_machine/outputs
```

## 7) Potential future integration (discussion only)

If the regime classifier is reliable in out-of-sample tests, a later strategy experiment could:
- run shock-reversion entries mostly in `Oscillating`
- reduce size / tighten risk in `Transition`
- disable or heavily constrain entries in `Trending`

This module currently provides only research artifacts and diagnostics.
