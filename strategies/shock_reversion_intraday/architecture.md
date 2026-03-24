# System Architecture: shock_reversion_intraday

## End-to-end flow

**signal → decision → execution → state update → logging → analysis**

1. **Signal**: compute excursion + shock components each bar.
2. **Decision**: resolve entry/add/exit intent.
3. **Execution**: submit orders through Backtrader.
4. **State update**: update live trade state after fills and per-bar tracking.
5. **Logging**: serialize signal/trade/diagnostic events.
6. **Analysis**: aggregate into run and experiment artifacts.

## Source of truth by layer

- **Strategy layer** (`shock_reversion_intraday.py`) → orchestration + state transitions.
- **Shared exit / trade-state engine** (`components/execution.py`) → exit logic + target construction + shared metrics.
- **Scoring model** (`components/shock_score.py`) → shock component computation and weighted scores.
- **Logging layer** (strategy event payloads + runner serialization) → serialization only.

## Decision semantics

- **Entry** → signal-triggered + score-filtered.
- **Add** → continuation + score + spacing.
- **Exit** → shared engine.

## Components

### 1) Strategy

- File: `src/ashare/strategies/shock_reversion_intraday.py`
- Responsibilities:
  - bar-by-bar signal generation
  - entry/add/exit orchestration
  - live trade state updates
  - signal/trade diagnostics payload construction

### 2) Shared exit / trade-state engine

- File: `src/ashare/strategies/components/execution.py`
- Responsibilities:
  - stable position state container (`PositionState`)
  - MFE/MAE updates and export
  - target construction (recovery / take-profit)
  - unified exit decision (`evaluate_exit_engine`)

### 3) Scoring model

- File: `src/ashare/strategies/components/shock_score.py`
- Responsibilities:
  - compute shared shock components
  - compute weighted score with configurable weights
  - support separate weight sets for entry vs add score paths

### 4) Ladder engine (in strategy)

- Implemented in strategy method `_check_add_leg`
- Applies:
  - price drop gate (`ladder_min_drop_pct`)
  - score gate (`add_score_min`)
  - bar-spacing gate (`ladder_min_bars_between_legs`)
  - remaining-hold gate (`min_bars_left_for_add`)

### 5) Logging system

- Signal stream (`signal_events`) captures trigger-level observability.
- Diagnostics stream (`diagnostics`) captures per-bar decision status.
- Trade records (`completed_trades`) capture final lifecycle metrics.

## Output hierarchy

- **Run-level**: `signals.csv`, `trades.csv`, and run summaries.
- **Experiment-level**: dashboard artifacts over multiple runs.
- **Folder lifecycle**: `latest/` for current run output, `previous/` for prior snapshot.

## Data artifacts

Primary run artifacts:

- `signals.csv`
  - includes execution markers (`entry_executed`, `add_executed`, `execution_type`)
  - includes ladder context (`drop_from_last_leg_pct`, `bars_since_last_leg`)
- `trades.csv`
  - includes trade lifecycle fields (`leg_count`, `add_shock_scores`, anchor/effective target fields)
- dashboard outputs
  - consolidated experiment-level views and summaries

## Design notes

- Exit behavior is unified in shared execution code and reused by strategy logic.
- Anchor logic is stateful across adds via `effective_anchor_price`.
- Strategy is long-only and event-triggered (no trend/ATR gating in this strategy class).
