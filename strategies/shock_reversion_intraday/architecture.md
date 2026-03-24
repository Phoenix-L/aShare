# System Architecture: shock_reversion_intraday

## End-to-end flow

**signal → decision → execution → logging → analysis**

1. **Signal**
   - Strategy computes excursion and shock components each bar.
2. **Decision**
   - Entry decision uses trigger + entry score bounds.
   - Add decision uses ladder price/score/time gates.
   - Exit decision uses shared execution engine.
3. **Execution**
   - Backtrader order lifecycle (`buy` / `sell`, pending-order guard).
4. **Logging**
   - Signal events, diagnostics events, completed trade records.
5. **Analysis**
   - Experiment runner/reporting persists CSV/JSON outputs and dashboard artifacts.

## Components

## 1) Strategy

- File: `src/ashare/strategies/shock_reversion_intraday.py`
- Responsibilities:
  - bar-by-bar signal generation
  - entry/add/exit orchestration
  - live trade state updates
  - signal/trade diagnostics payload construction

## 2) Execution engine (shared)

- File: `src/ashare/strategies/components/execution.py`
- Responsibilities:
  - stable position state container (`PositionState`)
  - MFE/MAE updates and export
  - target construction (recovery / take-profit)
  - unified exit decision (`evaluate_exit_engine`)

## 3) Scoring model

- File: `src/ashare/strategies/components/shock_score.py`
- Responsibilities:
  - compute shared shock components
  - compute weighted score with configurable weights
  - support separate weight sets for entry vs add score paths

## 4) Ladder engine (in strategy)

- Implemented in strategy method `_check_add_leg`
- Applies:
  - price drop gate (`ladder_min_drop_pct`)
  - score gate (`add_score_min`)
  - bar-spacing gate (`ladder_min_bars_between_legs`)
  - remaining-hold gate (`min_bars_left_for_add`)

## 5) Logging system

- Signal stream (`signal_events`) captures trigger-level observability.
- Diagnostics stream (`diagnostics`) captures per-bar decision status.
- Trade records (`completed_trades`) capture final lifecycle metrics.

## Data artifacts

Primary run artifacts:

- `signals.csv`
  - includes execution markers (`entry_executed`, `add_executed`, `execution_type`)
  - includes ladder context (`drop_from_last_leg_pct`, `bars_since_last_leg`)
- `trades.csv`
  - includes trade lifecycle fields (`leg_count`, `add_shock_scores`, anchor/effective target fields)
- dashboard outputs (from analysis tooling)
  - consolidated experiment-level views and summaries

## Design notes

- Exit behavior is unified in shared execution code and reused by strategy logic.
- Anchor logic is stateful across adds via `effective_anchor_price`.
- Strategy is long-only and event-triggered (no trend/ATR gating in this strategy class).
