# PRD — aShare (Implementation-aligned)

## 1. Product definition

aShare is a CLI-first A-share quantitative research toolkit for an **individual quant researcher**.

It supports iterative workflow:
- define strategy/config,
- run backtests,
- run parameter experiments,
- review metrics and compare runs.

## 2. Target user

Primary user:
- one developer-researcher (or very small team) who can run Python CLI locally,
- needs repeatable strategy evaluation over A-share symbols,
- prefers transparent files/artifacts over complex platforms.

## 3. Core capabilities (current)

### A) Single backtest
- Command: `ashare backtest --symbol ... --strategy ... --start ... --end ...`
- Uses selected data provider, normalized feed, and Backtrader engine.
- Returns headline metrics (return, sharpe, drawdown, trades).

### B) Experiment + grid search
- Command: `ashare experiment <spec.yaml>` (recommended)
- Also available: direct CLI mode without YAML.
- Supports cartesian parameter sweeps and multi-symbol runs.
- Writes per-run metrics and configuration snapshots (YAML mode).

## 4. Non-goals (current phase)

1. Live broker execution / order routing.
2. Multi-user SaaS operation.
3. Cloud/distributed scaling orchestration.
4. Portfolio OMS/PMS-grade execution controls.

## 5. Constraints

### Data constraints
- Data quality and field consistency depend on provider (`baostock` default, `tushare` optional).
- Minute-level coverage/turnover mapping can vary by backend and date range.

### Performance constraints
- Experiments are sequential loops (no built-in parallel execution).
- Runtime grows linearly with symbol count × parameter combinations.

### Reproducibility constraints
- Output contracts differ by experiment entry path (`outputs/` vs `experiments/`).

## 6. Current limitations

1. Dual experiment pipelines create inconsistent outputs.
2. `backtest` command lacks strategy param override flags.
3. Grid expansion duplicated in two modules.
4. Ranking summary is only generated in YAML experiment path.
5. Broker config overrides from YAML `execution` are partial (primarily cash/commission).

## 7. Roadmap (aligned with current architecture)

### Phase A — Consolidation
- Unify experiment execution and artifact schema.
- Centralize grid expansion logic.
- Normalize summary generation for all experiment modes.

### Phase B — Research ergonomics
- Add strategy param overrides for `backtest` command.
- Improve run metadata and traceability across commands.
- Add richer metrics (win rate/profit factor/expectancy) into ranking pipeline.

### Phase C — Validation depth
- Expand walk-forward workflows and compare-train-test reporting.
- Improve analyzer consistency and edge-case handling for sparse-trade runs.

### Phase D — Platform extension
- Add additional data providers and stronger data QA layers.
- Introduce optional parallel experiment execution.
