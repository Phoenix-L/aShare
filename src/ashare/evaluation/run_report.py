from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


REPORT_COLUMNS = [
    "run_id",
    "symbol",
    "start_date",
    "end_date",
    "initial_cash",
    "trade_unit",
    "use_margin",
    "margin_rate_annual",
    "total_margin_interest_paid",
    "total_return",
    "sum_trade_return",
    "compound_trade_return",
    "total_return_simple",
    "total_return_log",
    "avg_return_per_trade",
    "avg_legs_per_trade",
    "multi_leg_trade_share",
    "executed_trades",
    "sharpe",
    "max_drawdown",
    "avg_mfe",
    "avg_mae",
    "avg_etd",
    "pnl_capture_ratio",
    "entry_signals",
    "blocked_by_multiple",
    "stop_loss_share",
    "recovery_share",
    "take_profit_share",
    "max_hold_share",
    "avg_holding_bars",
    "avg_shock_score",
    "shock_score_min",
    "shock_score_max",
    "excursion_lookback_bars",
    "excursion_threshold",
    "recovery_frac",
    "take_profit_pct",
    "max_hold_bars",
    "stop_loss_pct",
    "use_shock_score_filter",
    "use_score_conditioned_exit",
]


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _summary_row_by_run_id(summary_df: pd.DataFrame, run_ids: list[str]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for index, run_id in enumerate(run_ids):
        if index >= len(summary_df.index):
            break
        row = summary_df.iloc[index]
        rows[run_id] = {column: row[column] for column in summary_df.columns if column in row.index}
    return rows


def _trades_by_run_id(trades_df: pd.DataFrame, run_ids: list[str]) -> dict[str, pd.DataFrame]:
    if trades_df.empty:
        return {run_id: pd.DataFrame() for run_id in run_ids}
    if "run_id" not in trades_df.columns:
        if len(run_ids) == 1:
            return {run_ids[0]: trades_df.copy()}
        return {run_id: pd.DataFrame() for run_id in run_ids}

    grouped = {str(run_id): frame.copy() for run_id, frame in trades_df.groupby("run_id", dropna=True)}
    return {run_id: grouped.get(run_id, pd.DataFrame()) for run_id in run_ids}


def _avg(series: pd.Series | list[float]) -> float:
    values = pd.to_numeric(series, errors="coerce") if isinstance(series, pd.Series) else pd.Series(series, dtype=float)
    valid = values.dropna()
    return float(valid.mean()) if not valid.empty else 0.0


def _share(trades_df: pd.DataFrame, exit_reason: str) -> float:
    if trades_df.empty or "exit_reason" not in trades_df.columns:
        return 0.0
    return float((trades_df["exit_reason"] == exit_reason).mean())


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except TypeError:
            pass
        return value
    return None


def _normalize_ratio_maybe_percent(value: Any, default: float = 0.0) -> float:
    normalized = _safe_float(value, default)
    if normalized is None:
        return default
    normalized = float(normalized)
    return normalized / 100.0 if abs(normalized) >= 1.0 else normalized


def _normalize_drawdown(value: Any, default: float = 0.0) -> float:
    normalized = _safe_float(value, default)
    if normalized is None:
        return default
    return float(normalized) / 100.0 if float(normalized) > 1.0 else float(normalized)


def _compute_total_return_simple(metrics: dict[str, Any], meta: dict[str, Any], summary_row: dict[str, Any]) -> float:
    final_equity = _safe_float(metrics.get("final_value"), None)
    initial_equity = _safe_float(meta.get("initial_cash"), None)
    if final_equity is not None and initial_equity not in (None, 0.0):
        return float((final_equity - initial_equity) / initial_equity)

    return float(
        _coalesce(
            _safe_float(summary_row.get("total_return"), None),
            _safe_float(summary_row.get("rtot"), None),
            _safe_float(summary_row.get("return"), None),
            _safe_float(metrics.get("total_return"), None),
            _safe_float(metrics.get("rtot"), None),
            0.0,
        )
    )


def _compute_total_return_log(metrics: dict[str, Any], meta: dict[str, Any], summary_row: dict[str, Any]) -> float:
    final_equity = _safe_float(metrics.get("final_value"), None)
    initial_equity = _safe_float(meta.get("initial_cash"), None)
    if final_equity is not None and initial_equity not in (None, 0.0):
        equity_ratio = float(final_equity) / float(initial_equity)
        return math.log(equity_ratio) if equity_ratio > 0 else float("-inf")

    explicit_log_return = _coalesce(
        _safe_float(metrics.get("total_return_log"), None),
        _safe_float(summary_row.get("total_return_log"), None),
        _safe_float(metrics.get("rtot"), None),
        _safe_float(summary_row.get("rtot"), None),
    )
    if explicit_log_return is not None:
        return float(explicit_log_return)

    explicit_simple_return = _coalesce(
        _safe_float(metrics.get("total_return_simple"), None),
        _safe_float(summary_row.get("total_return_simple"), None),
        _safe_float(summary_row.get("total_return"), None),
        _safe_float(metrics.get("total_return"), None),
    )
    if explicit_simple_return is None:
        return 0.0
    return math.log1p(float(explicit_simple_return)) if float(explicit_simple_return) > -1 else float("-inf")


def _sum_trade_return(pnl_values: pd.Series) -> float:
    valid = pnl_values.dropna()
    return float(valid.sum()) if not valid.empty else 0.0


def _compound_trade_return(pnl_values: pd.Series) -> float:
    valid = pnl_values.dropna()
    if valid.empty:
        return 0.0
    compounded = 1.0
    for trade_return in valid.tolist():
        compounded *= 1.0 + float(trade_return)
    return compounded - 1.0


def _run_payload(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    run_payload = _load_json(run_dir / "run_result.json")
    if run_payload:
        params = run_payload.get("params") if isinstance(run_payload.get("params"), dict) else {}
        metrics = run_payload.get("metrics") if isinstance(run_payload.get("metrics"), dict) else {}
        meta = run_payload.get("meta") if isinstance(run_payload.get("meta"), dict) else {}
        return params, metrics, meta

    metrics = _load_json(run_dir / "metrics.json")
    snapshot = _load_yaml(run_dir / "config_snapshot.yaml")
    params = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}
    meta = {
        "run_id": run_dir.name,
        "symbol": snapshot.get("symbol"),
        "date_range": snapshot.get("date_range"),
        "initial_cash": _coalesce(snapshot.get("initial_cash"), snapshot.get("execution", {}).get("initial_cash") if isinstance(snapshot.get("execution"), dict) else None),
    }
    return params, metrics, meta


def _build_row(
    *,
    run_id: str,
    summary_row: dict[str, Any],
    params: dict[str, Any],
    metrics: dict[str, Any],
    meta: dict[str, Any],
    diagnostics_summary: dict[str, Any],
    trades_df: pd.DataFrame,
) -> dict[str, Any]:
    pnl_values = pd.Series(dtype=float)
    if not trades_df.empty and "trade_return" in trades_df.columns:
        pnl_values = pd.to_numeric(trades_df.get("trade_return"), errors="coerce")
    if pnl_values.dropna().empty and not trades_df.empty and "pnl_pct" in trades_df.columns:
        pnl_values = pd.to_numeric(trades_df.get("pnl_pct"), errors="coerce")

    mfe_values = pd.Series(dtype=float)
    if not trades_df.empty and "mfe" in trades_df.columns:
        mfe_values = pd.to_numeric(trades_df.get("mfe"), errors="coerce")
    if mfe_values.dropna().empty and not trades_df.empty:
        mfe_values = pd.to_numeric(trades_df.get("mfe_pct", trades_df.get("max_favorable_excursion")), errors="coerce")

    mae_values = pd.Series(dtype=float)
    if not trades_df.empty and "mae" in trades_df.columns:
        mae_values = pd.to_numeric(trades_df.get("mae"), errors="coerce")
    if mae_values.dropna().empty and not trades_df.empty:
        mae_values = pd.to_numeric(trades_df.get("mae_pct", trades_df.get("max_adverse_excursion")), errors="coerce")
    etd_values = pd.to_numeric(trades_df.get("etd"), errors="coerce") if "etd" in trades_df.columns else pd.Series(dtype=float)
    holding_bars = pd.to_numeric(trades_df.get("holding_bars"), errors="coerce") if "holding_bars" in trades_df.columns else pd.Series(dtype=float)
    shock_scores = pd.to_numeric(trades_df.get("shock_score_at_entry"), errors="coerce") if "shock_score_at_entry" in trades_df.columns else pd.Series(dtype=float)
    num_legs = (
        pd.to_numeric(trades_df.get("num_legs"), errors="coerce")
        if "num_legs" in trades_df.columns
        else (pd.Series([1] * len(trades_df.index), dtype=float) if not trades_df.empty else pd.Series(dtype=float))
    )

    avg_return_per_trade_from_trades = _avg(pnl_values)
    avg_mfe_from_trades = _avg(mfe_values)
    avg_mae_from_trades = _avg(mae_values)
    avg_etd_from_trades = _avg(etd_values)
    total_return_simple = _compute_total_return_simple(metrics, meta, summary_row)
    total_return_log = _compute_total_return_log(metrics, meta, summary_row)
    sum_trade_return = _sum_trade_return(pnl_values)
    compound_trade_return = _compound_trade_return(pnl_values)

    avg_return_per_trade = float(
        _coalesce(
            avg_return_per_trade_from_trades if not trades_df.empty else None,
            _safe_float(diagnostics_summary.get("avg_return_per_trade"), None),
            0.0,
        )
    )
    avg_mfe = float(
        _coalesce(
            avg_mfe_from_trades if not trades_df.empty else None,
            _normalize_ratio_maybe_percent(diagnostics_summary.get("avg_mfe"), None),
            0.0,
        )
    )
    avg_mae = float(
        _coalesce(
            avg_mae_from_trades if not trades_df.empty else None,
            _normalize_ratio_maybe_percent(diagnostics_summary.get("avg_mae"), None),
            0.0,
        )
    )
    avg_etd = float(
        _coalesce(
            avg_etd_from_trades if not trades_df.empty else None,
            _normalize_ratio_maybe_percent(diagnostics_summary.get("avg_etd"), None),
            0.0,
        )
    )
    executed_trades = int(_coalesce(len(trades_df.index) if not trades_df.empty else None, _safe_float(diagnostics_summary.get("executed_trades"), None), _safe_float(summary_row.get("num_trades"), None), 0.0))

    date_range = meta.get("date_range") if isinstance(meta.get("date_range"), dict) else {}

    return {
        "run_id": run_id,
        "symbol": _coalesce(meta.get("symbol"), summary_row.get("symbol"), trades_df.iloc[0].get("symbol") if not trades_df.empty else None),
        "start_date": _coalesce(date_range.get("start"), summary_row.get("start_date")),
        "end_date": _coalesce(date_range.get("end"), summary_row.get("end_date")),
        "initial_cash": _safe_float(meta.get("initial_cash"), None),
        "trade_unit": _coalesce(params.get("trade_unit"), summary_row.get("trade_unit")),
        "use_margin": _coalesce(params.get("use_margin"), summary_row.get("use_margin")),
        "margin_rate_annual": _coalesce(params.get("margin_rate_annual"), summary_row.get("margin_rate_annual")),
        "total_margin_interest_paid": float(_coalesce(_safe_float(metrics.get("total_margin_interest_paid"), None), 0.0)),
        "total_return": total_return_simple,
        "sum_trade_return": sum_trade_return,
        "compound_trade_return": compound_trade_return,
        "total_return_simple": total_return_simple,
        "total_return_log": total_return_log,
        "avg_return_per_trade": avg_return_per_trade,
        "avg_legs_per_trade": _avg(num_legs),
        "multi_leg_trade_share": float((num_legs > 1).mean()) if not num_legs.dropna().empty else 0.0,
        "executed_trades": executed_trades,
        "sharpe": float(_coalesce(_safe_float(summary_row.get("sharpe"), None), _safe_float(metrics.get("sharpe"), None), 0.0)),
        "max_drawdown": float(
            _coalesce(
                _normalize_drawdown(summary_row.get("max_drawdown"), None),
                _normalize_drawdown(metrics.get("max_drawdown"), None),
                0.0,
            )
        ),
        "avg_mfe": avg_mfe,
        "avg_mae": avg_mae,
        "avg_etd": avg_etd,
        "pnl_capture_ratio": float(avg_return_per_trade / avg_mfe) if avg_mfe > 0 else 0.0,
        "entry_signals": int(_safe_float(diagnostics_summary.get("entry_signals"), 0.0) or 0.0),
        "blocked_by_multiple": int(_safe_float(diagnostics_summary.get("blocked_by_multiple"), 0.0) or 0.0),
        "stop_loss_share": _share(trades_df, "stop_loss"),
        "recovery_share": _share(trades_df, "recovery"),
        "take_profit_share": _share(trades_df, "take_profit"),
        "max_hold_share": _share(trades_df, "max_hold"),
        "avg_holding_bars": _avg(holding_bars),
        "avg_shock_score": _safe_float(shock_scores.mean() if not shock_scores.dropna().empty else None, None),
        "shock_score_min": _coalesce(params.get("shock_score_min"), summary_row.get("shock_score_min")),
        "shock_score_max": _coalesce(params.get("shock_score_max"), summary_row.get("shock_score_max")),
        "excursion_lookback_bars": _coalesce(params.get("excursion_lookback_bars"), summary_row.get("excursion_lookback_bars")),
        "excursion_threshold": _coalesce(params.get("excursion_threshold"), summary_row.get("excursion_threshold")),
        "recovery_frac": _coalesce(params.get("recovery_frac"), summary_row.get("recovery_frac")),
        "take_profit_pct": _coalesce(params.get("take_profit_pct"), summary_row.get("take_profit_pct")),
        "max_hold_bars": _coalesce(params.get("max_hold_bars"), summary_row.get("max_hold_bars")),
        "stop_loss_pct": _coalesce(params.get("stop_loss_pct"), summary_row.get("stop_loss_pct")),
        "use_shock_score_filter": _coalesce(params.get("use_shock_score_filter"), summary_row.get("use_shock_score_filter")),
        "use_score_conditioned_exit": _coalesce(params.get("use_score_conditioned_exit"), summary_row.get("use_score_conditioned_exit")),
    }


def write_run_performance_report(output_dir: str | Path) -> Path:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    summary_df = _read_csv(output_root / "summary.csv")
    trades_df = _read_csv(output_root / "trades.csv")
    run_dirs = sorted(path for path in output_root.iterdir() if path.is_dir() and path.name.startswith("run_"))
    run_ids = [run_dir.name for run_dir in run_dirs]
    summary_rows = _summary_row_by_run_id(summary_df, run_ids)
    trades_by_run = _trades_by_run_id(trades_df, run_ids)

    rows: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        run_id = run_dir.name
        params, metrics, meta = _run_payload(run_dir)
        diagnostics_summary = _load_json(run_dir / "diagnostics_summary.json")
        rows.append(
            _build_row(
                run_id=run_id,
                summary_row=summary_rows.get(run_id, {}),
                params=params,
                metrics=metrics,
                meta=meta,
                diagnostics_summary=diagnostics_summary,
                trades_df=trades_by_run.get(run_id, pd.DataFrame()),
            )
        )

    report_path = output_root / "run_performance_report.csv"
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in REPORT_COLUMNS})
    return report_path
