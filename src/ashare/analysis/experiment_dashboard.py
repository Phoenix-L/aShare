from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from ashare.utils.logging import get_logger

logger = get_logger("ashare.analysis.experiment_dashboard")

DASHBOARD_FILENAMES = {
    "experiment_trades": "experiment_trades.csv",
    "exit_analysis": "exit_analysis.csv",
    "ladder_analysis": "ladder_analysis.csv",
    "entry_score_analysis": "entry_score_analysis.csv",
    "add_score_analysis": "add_score_analysis.csv",
    "config_analysis": "config_analysis.csv",
    "recovery_diagnostic": "recovery_diagnostic.csv",
}
SCORE_BUCKETS = [0.0, 30.0, 50.0, 70.0, 90.0, 100.0]
SCORE_BUCKET_LABELS = ["0-30", "30-50", "50-70", "70-90", "90-100"]
EXPERIMENT_TRADE_COLUMNS = [
    "run_id",
    "symbol",
    "entry_datetime",
    "exit_datetime",
    "trade_return",
    "trade_pnl_amount",
    "exit_reason",
    "leg_count",
    "ladder_used",
    "entry_shock_score",
    "add_shock_score",
    "holding_period",
]
CONFIG_GROUP_COLUMNS = ["recovery_frac", "ladder_enabled", "add_score_min", "max_legs"]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Skipping invalid JSON file: %s", path)
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _coalesce_column(frame: pd.DataFrame, candidates: list[str], *, fill_value: Any = None) -> pd.Series:
    for column in candidates:
        if column in frame.columns:
            return frame[column]
    return pd.Series([fill_value] * len(frame.index), index=frame.index)


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _normalize_bool_value(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def _safe_ratio(series: pd.Series, predicate) -> float:
    valid = series.dropna()
    if valid.empty:
        return 0.0
    return float(predicate(valid).mean())


def _aggregate_trade_frame(frame: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if frame.empty or group_column not in frame.columns:
        columns = [group_column, "trade_count", "avg_return", "median_return", "win_rate", "avg_holding_period"]
        return pd.DataFrame(columns=columns)

    working = frame.copy()
    working["trade_return"] = _coerce_numeric(working["trade_return"])
    working["holding_period"] = _coerce_numeric(working["holding_period"])

    aggregated = (
        working.groupby(group_column, dropna=False)
        .agg(
            trade_count=("trade_return", "size"),
            avg_return=("trade_return", "mean"),
            median_return=("trade_return", "median"),
            avg_holding_period=("holding_period", "mean"),
        )
        .reset_index()
    )
    win_rates = (
        working.groupby(group_column, dropna=False)["trade_return"]
        .apply(lambda series: _safe_ratio(series, lambda values: values > 0))
        .rename("win_rate")
        .reset_index()
    )
    return aggregated.merge(win_rates, on=group_column, how="left")


def _score_bucket_analysis(frame: pd.DataFrame, score_column: str) -> pd.DataFrame:
    columns = ["score_bucket", "trade_count", "avg_return", "win_rate"]
    if frame.empty or score_column not in frame.columns:
        return pd.DataFrame({"score_bucket": SCORE_BUCKET_LABELS, "trade_count": 0, "avg_return": 0.0, "win_rate": 0.0})[columns]

    working = frame.copy()
    working[score_column] = _coerce_numeric(working[score_column])
    working["trade_return"] = _coerce_numeric(working["trade_return"])
    working = working.dropna(subset=[score_column])
    if working.empty:
        return pd.DataFrame({"score_bucket": SCORE_BUCKET_LABELS, "trade_count": 0, "avg_return": 0.0, "win_rate": 0.0})[columns]

    clipped = working[score_column].clip(lower=SCORE_BUCKETS[0], upper=SCORE_BUCKETS[-1])
    working["score_bucket"] = pd.cut(
        clipped,
        bins=SCORE_BUCKETS,
        labels=SCORE_BUCKET_LABELS,
        include_lowest=True,
        right=True,
    )

    aggregated = (
        working.groupby("score_bucket", observed=False)
        .agg(
            trade_count=("trade_return", "size"),
            avg_return=("trade_return", "mean"),
        )
        .reindex(SCORE_BUCKET_LABELS, fill_value=0)
        .reset_index()
    )
    win_rates = (
        working.groupby("score_bucket", observed=False)["trade_return"]
        .apply(lambda series: _safe_ratio(series, lambda values: values > 0))
        .reindex(SCORE_BUCKET_LABELS, fill_value=0.0)
        .rename("win_rate")
        .reset_index()
    )
    return aggregated.merge(win_rates, on="score_bucket", how="left")[columns]


def _normalize_ladder_enabled(value: Any, max_legs: Any, add_score_min: Any) -> bool | None:
    explicit = _normalize_bool_value(value)
    if explicit is not None:
        return explicit

    max_legs_value = pd.to_numeric(pd.Series([max_legs]), errors="coerce").iloc[0]
    if pd.notna(max_legs_value):
        return bool(float(max_legs_value) > 1.0)

    add_score_min_value = pd.to_numeric(pd.Series([add_score_min]), errors="coerce").iloc[0]
    if pd.notna(add_score_min_value):
        return True
    return None


def _derive_trade_frame(trades_df: pd.DataFrame, run_id: str) -> pd.DataFrame:
    if trades_df.empty:
        return pd.DataFrame(columns=EXPERIMENT_TRADE_COLUMNS)

    working = trades_df.copy()
    if "run_id" in working.columns:
        working["run_id"] = working["run_id"].fillna(run_id).astype(str)
    else:
        working["run_id"] = pd.Series([run_id] * len(working.index), index=working.index)
    working["symbol"] = _coalesce_column(working, ["symbol"], fill_value=None)
    working["entry_datetime"] = _coalesce_column(working, ["entry_datetime", "entry_time"], fill_value=None)
    working["exit_datetime"] = _coalesce_column(working, ["exit_datetime", "exit_time"], fill_value=None)
    working["trade_return"] = _coerce_numeric(_coalesce_column(working, ["trade_return", "pnl_pct"], fill_value=None))
    working["trade_pnl_amount"] = _coerce_numeric(_coalesce_column(working, ["trade_pnl_amount"], fill_value=None))
    working["exit_reason"] = _coalesce_column(working, ["exit_reason", "exit_subtype"], fill_value=None)
    working["leg_count"] = _coerce_numeric(_coalesce_column(working, ["leg_count", "num_legs"], fill_value=1)).fillna(1)
    working["ladder_used"] = working["leg_count"] > 1
    working["entry_shock_score"] = _coerce_numeric(
        _coalesce_column(working, ["entry_shock_score_at_entry", "shock_score_at_entry", "entry_shock_score"], fill_value=None)
    )
    working["add_shock_score"] = _coerce_numeric(
        _coalesce_column(working, ["add_shock_score_at_entry", "add_shock_score", "add_shock_score_at_signal"], fill_value=None)
    )
    working["holding_period"] = _coerce_numeric(_coalesce_column(working, ["holding_period", "holding_bars"], fill_value=None))
    return working[EXPERIMENT_TRADE_COLUMNS].copy()


def _load_run_payload(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    run_payload = _read_json(run_dir / "run_result.json")
    if run_payload:
        params = run_payload.get("params") if isinstance(run_payload.get("params"), dict) else {}
        meta = run_payload.get("meta") if isinstance(run_payload.get("meta"), dict) else {}
        return params, meta

    snapshot = _read_yaml(run_dir / "config_snapshot.yaml")
    params = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}
    meta = {
        "run_id": run_dir.name,
        "symbol": snapshot.get("symbol"),
        "date_range": snapshot.get("date_range"),
    }
    return params, meta


def _root_trades_by_run(experiment_dir: Path) -> dict[str, pd.DataFrame]:
    root_trades = _read_csv(experiment_dir / "trades.csv")
    if root_trades.empty or "run_id" not in root_trades.columns:
        return {}
    return {str(run_id): frame.copy() for run_id, frame in root_trades.groupby("run_id", dropna=True)}


def _load_all_trades(experiment_dir: Path, run_dirs: list[Path]) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    warnings: list[dict[str, str]] = []
    root_trade_frames = _root_trades_by_run(experiment_dir)
    trade_frames: list[pd.DataFrame] = []

    for run_dir in run_dirs:
        per_run_path = run_dir / "trades.csv"
        if per_run_path.exists():
            raw_trades = _read_csv(per_run_path)
        else:
            raw_trades = root_trade_frames.get(run_dir.name, pd.DataFrame())

        if raw_trades.empty:
            logger.warning("Skipping %s because no trade rows were found", run_dir.name)
            continue

        derived = _derive_trade_frame(raw_trades, run_dir.name)
        missing_required = [
            column for column in [
                "run_id",
                "symbol",
                "entry_datetime",
                "exit_datetime",
                "trade_return",
                "trade_pnl_amount",
                "exit_reason",
                "leg_count",
                "entry_shock_score",
                "holding_period",
            ]
            if column not in derived.columns
        ]
        if missing_required:
            warnings.append({"run_id": run_dir.name, "warning": f"missing required columns after normalization: {', '.join(missing_required)}"})
            logger.warning("Run %s missing required columns after normalization: %s", run_dir.name, ", ".join(missing_required))

        if derived["symbol"].isna().all():
            warnings.append({"run_id": run_dir.name, "warning": "symbol missing for all trades"})
            logger.warning("Run %s has no symbol values in trade data", run_dir.name)

        trade_frames.append(derived)

    if not trade_frames:
        return pd.DataFrame(columns=EXPERIMENT_TRADE_COLUMNS), warnings
    return pd.concat(trade_frames, ignore_index=True), warnings


def _load_run_performance_report(experiment_dir: Path, run_dirs: list[Path]) -> pd.DataFrame:
    root_report = _read_csv(experiment_dir / "run_performance_report.csv")
    if not root_report.empty:
        return root_report

    frames: list[pd.DataFrame] = []
    for run_dir in run_dirs:
        run_report = _read_csv(run_dir / "run_performance_report.csv")
        if run_report.empty:
            continue
        if "run_id" not in run_report.columns:
            run_report = run_report.copy()
            run_report["run_id"] = run_dir.name
        frames.append(run_report)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_run_configs(run_dirs: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        params, meta = _load_run_payload(run_dir)
        row = {
            "run_id": str(meta.get("run_id") or run_dir.name),
            "recovery_frac": params.get("recovery_frac"),
            "add_score_min": params.get("add_score_min", params.get("ladder_score_min_add")),
            "max_legs": params.get("max_legs"),
            "ladder_enabled": _normalize_ladder_enabled(params.get("ladder_enabled"), params.get("max_legs"), params.get("add_score_min", params.get("ladder_score_min_add"))),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _build_config_analysis(report_df: pd.DataFrame, config_df: pd.DataFrame, trades_df: pd.DataFrame) -> pd.DataFrame:
    if report_df.empty:
        columns = [*CONFIG_GROUP_COLUMNS, "run_count", "avg_total_return", "avg_drawdown", "avg_trade_return", "trade_count"]
        return pd.DataFrame(columns=columns)

    merged = report_df.copy()
    if "run_id" not in merged.columns:
        logger.warning("run_performance_report.csv missing run_id column; config analysis will be empty")
        columns = [*CONFIG_GROUP_COLUMNS, "run_count", "avg_total_return", "avg_drawdown", "avg_trade_return", "trade_count"]
        return pd.DataFrame(columns=columns)

    merged["run_id"] = merged["run_id"].astype(str)
    merged = merged.merge(config_df, on="run_id", how="left")

    avg_trade_return_by_run = (
        trades_df.groupby("run_id", dropna=False)["trade_return"].mean().rename("trade_return_from_trades").reset_index()
        if not trades_df.empty
        else pd.DataFrame(columns=["run_id", "trade_return_from_trades"])
    )
    trade_count_by_run = (
        trades_df.groupby("run_id", dropna=False).size().rename("trade_count_from_trades").reset_index()
        if not trades_df.empty
        else pd.DataFrame(columns=["run_id", "trade_count_from_trades"])
    )
    merged = merged.merge(avg_trade_return_by_run, on="run_id", how="left")
    merged = merged.merge(trade_count_by_run, on="run_id", how="left")

    merged["avg_trade_return_source"] = _coerce_numeric(_coalesce_column(merged, ["avg_return_per_trade", "trade_return_from_trades"], fill_value=None))
    merged["total_return_source"] = _coerce_numeric(_coalesce_column(merged, ["total_return", "total_return_simple"], fill_value=None))
    merged["max_drawdown_source"] = _coerce_numeric(_coalesce_column(merged, ["max_drawdown"], fill_value=None))
    merged["trade_count_source"] = _coerce_numeric(_coalesce_column(merged, ["executed_trades", "num_trades", "trade_count_from_trades"], fill_value=0)).fillna(0)

    available_group_columns = [column for column in CONFIG_GROUP_COLUMNS if column in merged.columns]
    if not available_group_columns:
        available_group_columns = ["run_id"]

    aggregated = (
        merged.groupby(available_group_columns, dropna=False)
        .agg(
            run_count=("run_id", "nunique"),
            avg_total_return=("total_return_source", "mean"),
            avg_drawdown=("max_drawdown_source", "mean"),
            avg_trade_return=("avg_trade_return_source", "mean"),
            trade_count=("trade_count_source", "sum"),
        )
        .reset_index()
    )
    return aggregated


def _build_recovery_diagnostic(trades_df: pd.DataFrame) -> pd.DataFrame:
    columns = ["exit_reason", "trade_count", "avg_return", "median_return", "pct_exit_within_3_bars", "pct_profitable"]
    reasons = ["recovery", "take_profit", "stop_loss"]
    if trades_df.empty:
        return pd.DataFrame({
            "exit_reason": reasons,
            "trade_count": 0,
            "avg_return": 0.0,
            "median_return": 0.0,
            "pct_exit_within_3_bars": 0.0,
            "pct_profitable": 0.0,
        })[columns]

    working = trades_df.copy()
    working["trade_return"] = _coerce_numeric(working["trade_return"])
    working["holding_period"] = _coerce_numeric(working["holding_period"])

    rows: list[dict[str, Any]] = []
    for reason in reasons:
        subset = working.loc[working["exit_reason"] == reason].copy()
        if subset.empty:
            rows.append({
                "exit_reason": reason,
                "trade_count": 0,
                "avg_return": 0.0,
                "median_return": 0.0,
                "pct_exit_within_3_bars": 0.0,
                "pct_profitable": 0.0,
            })
            continue
        rows.append({
            "exit_reason": reason,
            "trade_count": int(len(subset.index)),
            "avg_return": float(subset["trade_return"].mean()),
            "median_return": float(subset["trade_return"].median()),
            "pct_exit_within_3_bars": _safe_ratio(subset["holding_period"], lambda values: values <= 3),
            "pct_profitable": _safe_ratio(subset["trade_return"], lambda values: values > 0),
        })
    return pd.DataFrame(rows)[columns]


def build_experiment_dashboard(experiment_path: str) -> dict[str, str]:
    experiment_dir = Path(experiment_path).expanduser().resolve()
    if not experiment_dir.exists():
        raise FileNotFoundError(f"Experiment path does not exist: {experiment_dir}")

    run_dirs = sorted(path for path in experiment_dir.iterdir() if path.is_dir() and path.name.startswith("run_"))
    dashboard_dir = experiment_dir / "dashboard"
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    trades_df, _ = _load_all_trades(experiment_dir, run_dirs)
    if not trades_df.empty:
        trades_df = trades_df.sort_values(["run_id", "entry_datetime", "exit_datetime"], kind="stable").reset_index(drop=True)
    trades_df.to_csv(dashboard_dir / DASHBOARD_FILENAMES["experiment_trades"], index=False)

    exit_analysis = _aggregate_trade_frame(trades_df, "exit_reason")
    exit_analysis.to_csv(dashboard_dir / DASHBOARD_FILENAMES["exit_analysis"], index=False)

    ladder_analysis = _aggregate_trade_frame(trades_df, "ladder_used")
    if not ladder_analysis.empty:
        avg_pnl = (
            trades_df.groupby("ladder_used", dropna=False)["trade_pnl_amount"]
            .mean()
            .rename("avg_pnl")
            .reset_index()
        )
        ladder_analysis = ladder_analysis.merge(avg_pnl, on="ladder_used", how="left")
        ladder_analysis = ladder_analysis[["ladder_used", "trade_count", "avg_return", "median_return", "win_rate", "avg_pnl", "avg_holding_period"]]
    else:
        ladder_analysis = pd.DataFrame(columns=["ladder_used", "trade_count", "avg_return", "median_return", "win_rate", "avg_pnl", "avg_holding_period"])
    ladder_analysis.to_csv(dashboard_dir / DASHBOARD_FILENAMES["ladder_analysis"], index=False)

    entry_score_analysis = _score_bucket_analysis(trades_df, "entry_shock_score")
    entry_score_analysis.to_csv(dashboard_dir / DASHBOARD_FILENAMES["entry_score_analysis"], index=False)

    add_score_analysis = _score_bucket_analysis(trades_df, "add_shock_score")
    add_score_analysis.to_csv(dashboard_dir / DASHBOARD_FILENAMES["add_score_analysis"], index=False)

    run_report_df = _load_run_performance_report(experiment_dir, run_dirs)
    run_config_df = _load_run_configs(run_dirs)
    config_analysis = _build_config_analysis(run_report_df, run_config_df, trades_df)
    config_analysis.to_csv(dashboard_dir / DASHBOARD_FILENAMES["config_analysis"], index=False)

    recovery_diagnostic = _build_recovery_diagnostic(trades_df)
    recovery_diagnostic.to_csv(dashboard_dir / DASHBOARD_FILENAMES["recovery_diagnostic"], index=False)

    logger.info("Experiment dashboard written to %s", dashboard_dir)
    return {name: str(dashboard_dir / filename) for name, filename in DASHBOARD_FILENAMES.items()}
