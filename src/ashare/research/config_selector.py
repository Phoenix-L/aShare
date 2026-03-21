from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

SUMMARY_EXCLUDE_COLUMNS = {
    "run_id",
    "return",
    "total_return",
    "total_return_simple",
    "total_return_log",
    "rtot",
    "avg_trade_return",
    "avg_return_per_trade",
    "sharpe",
    "max_drawdown",
    "num_trades",
    "trade_count",
}

def _safe_float(value: Any, default: float = 0.0) -> float:
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


def _normalize_ratio_maybe_percent(value: Any, default: float = 0.0) -> float:
    normalized = _safe_float(value, default)
    return normalized / 100.0 if abs(normalized) >= 1.0 else normalized


def _normalize_drawdown(value: Any, default: float = 0.0) -> float:
    normalized = _safe_float(value, default)
    return normalized / 100.0 if normalized > 1.0 else normalized


def _coerce_avg_return_per_trade(diagnostics_summary: dict[str, Any]) -> float:
    if "avg_return_per_trade" in diagnostics_summary:
        return _safe_float(diagnostics_summary.get("avg_return_per_trade"))
    return _normalize_ratio_maybe_percent(diagnostics_summary.get("avg_pnl"))

def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}

def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

def _normalize_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return pd.Series([0.0] * len(series), index=series.index, dtype=float)
    minimum = float(valid.min())
    maximum = float(valid.max())
    if maximum == minimum:
        return pd.Series([0.0] * len(series), index=series.index, dtype=float)
    return (numeric - minimum) / (maximum - minimum)

def _normalize_series_unit(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return pd.Series([1.0] * len(series), index=series.index, dtype=float)
    minimum = float(valid.min())
    maximum = float(valid.max())
    if maximum == minimum:
        return pd.Series([1.0] * len(series), index=series.index, dtype=float)
    return ((numeric - minimum) / (maximum - minimum)).fillna(1.0)


def _portfolio_return_column(summary_df: pd.DataFrame) -> str | None:
    for column in ("return", "total_return", "rtot"):
        if column in summary_df.columns:
            return column
    return None

def _build_stop_loss_share_map(trades_df: pd.DataFrame, run_ids: list[str]) -> dict[str, float]:
    if trades_df.empty:
        return {run_id: 0.0 for run_id in run_ids}

    if "run_id" not in trades_df.columns:
        if len(run_ids) == 1:
            stop_loss_share = float((trades_df.get("exit_reason") == "stop_loss").mean()) if len(trades_df.index) else 0.0
            return {run_ids[0]: stop_loss_share}
        return {run_id: 1.0 for run_id in run_ids}

    shares: dict[str, float] = {run_id: 0.0 for run_id in run_ids}
    for run_id, run_trades in trades_df.groupby("run_id", dropna=True):
        if run_id not in shares:
            continue
        exit_reasons = run_trades.get("exit_reason")
        shares[str(run_id)] = float((exit_reasons == "stop_loss").mean()) if exit_reasons is not None and len(run_trades.index) else 0.0
    return shares

def _build_selection_frame(output_root: Path) -> pd.DataFrame:
    summary_df = _read_csv(output_root / "summary.csv")
    if summary_df.empty:
        return pd.DataFrame()

    portfolio_return_column = _portfolio_return_column(summary_df)
    if portfolio_return_column is None:
        raise ValueError(f"Missing return column in {output_root / 'summary.csv'}")

    run_dirs = sorted(path for path in output_root.iterdir() if path.is_dir() and path.name.startswith("run_"))
    run_ids = [run_dir.name for run_dir in run_dirs]
    trades_df = _read_csv(output_root / "trades.csv")
    stop_loss_share_map = _build_stop_loss_share_map(trades_df, run_ids)

    records: list[dict[str, Any]] = []
    for index, run_dir in enumerate(run_dirs):
        summary_row = summary_df.iloc[index] if index < len(summary_df.index) else pd.Series(dtype=object)
        diagnostics_summary = _load_json(run_dir / "diagnostics_summary.json")
        record = {
            column: summary_row[column]
            for column in summary_df.columns
            if column in summary_row.index and column not in {"return", "rtot", "total_return_simple", "total_return_log"}
        }
        record.update(
            {
                "run_id": run_dir.name,
                "total_return": _safe_float(summary_row.get(portfolio_return_column)),
                "sharpe": _safe_float(summary_row.get("sharpe")),
                "max_drawdown": _normalize_drawdown(summary_row.get("max_drawdown")),
                "num_trades": _safe_float(summary_row.get("num_trades", summary_row.get("trade_count"))),
                "executed_trades": _safe_float(diagnostics_summary.get("executed_trades")),
                "avg_return_per_trade": _coerce_avg_return_per_trade(diagnostics_summary),
                "avg_pnl": _coerce_avg_return_per_trade(diagnostics_summary),
                "avg_mfe": _normalize_ratio_maybe_percent(diagnostics_summary.get("avg_mfe")),
                "avg_mae": _normalize_ratio_maybe_percent(diagnostics_summary.get("avg_mae")),
                "avg_etd": _normalize_ratio_maybe_percent(diagnostics_summary.get("avg_etd")),
                "stop_loss_share": float(stop_loss_share_map.get(run_dir.name, 0.0)),
            }
        )
        record["avg_trade_return"] = record["avg_return_per_trade"]
        record["capture_ratio"] = record["avg_trade_return"] / record["avg_mfe"] if record["avg_mfe"] > 0 else 0.0
        record["pain_gain_ratio"] = abs(record["avg_mae"]) / record["avg_trade_return"] if record["avg_trade_return"] > 0 else float("inf")
        record["etd_ratio"] = record["avg_etd"] / record["avg_mfe"] if record["avg_mfe"] > 0 else float("inf")

        portfolio_return = record["total_return"]
        avg_trade_return = record["avg_trade_return"]
        signs_match = (portfolio_return == 0.0 or avg_trade_return == 0.0) or ((portfolio_return > 0) == (avg_trade_return > 0))
        record["return_sign_mismatch"] = not signs_match
        record["return_alignment_warning"] = "sign_mismatch" if not signs_match else ""
        records.append(record)

    return pd.DataFrame(records)

def _apply_selection_rules(selection_df: pd.DataFrame) -> pd.DataFrame:
    if selection_df.empty:
        return selection_df

    evaluated = selection_df.copy()
    rejection_reasons: list[str] = []
    ladder_ready: list[bool] = []

    for _, row in evaluated.iterrows():
        reasons: list[str] = []
        if row["executed_trades"] < 10:
            reasons.append("hard:executed_trades<10")
        if row["total_return"] <= 0:
            reasons.append("hard:total_return<=0")
        if row["avg_trade_return"] <= 0:
            reasons.append("hard:avg_trade_return<=0")
        if row["avg_mfe"] <= 0:
            reasons.append("hard:avg_mfe<=0")
        if row["capture_ratio"] < 0.25:
            reasons.append("hard:capture_ratio<0.25")
        if row["max_drawdown"] > 0.12:
            reasons.append("hard:max_drawdown>0.12")
        if row["stop_loss_share"] > 0.60:
            reasons.append("hard:stop_loss_share>0.60")

        is_ladder_ready = True
        if row["avg_mfe"] < 2 * row["avg_trade_return"]:
            reasons.append("ladder:avg_mfe<2x_avg_trade_return")
            is_ladder_ready = False
        if row["executed_trades"] < 10:
            is_ladder_ready = False
        if row["stop_loss_share"] > 0.50:
            reasons.append("ladder:stop_loss_share>0.50")
            is_ladder_ready = False
        if row["etd_ratio"] > 0.70:
            reasons.append("ladder:etd_ratio>0.70")
            is_ladder_ready = False

        rejection_reasons.append(";".join(reasons))
        ladder_ready.append(is_ladder_ready and not any(reason.startswith("hard:") for reason in reasons))

    evaluated["ladder_ready"] = ladder_ready
    evaluated["rejection_reason"] = rejection_reasons
    evaluated["selected"] = evaluated["rejection_reason"] == ""

    selected_mask = evaluated["selected"]
    for column in ["total_return", "sharpe", "avg_trade_return", "capture_ratio", "executed_trades", "max_drawdown", "avg_etd"]:
        normalized = pd.Series([0.0] * len(evaluated.index), index=evaluated.index, dtype=float)
        normalized.loc[selected_mask] = _normalize_series(evaluated.loc[selected_mask, column])
        evaluated[f"{column}_normalized"] = normalized

    evaluated["score"] = 0.0
    evaluated.loc[selected_mask, "score"] = (
        0.40 * evaluated.loc[selected_mask, "total_return_normalized"]
        + 0.20 * evaluated.loc[selected_mask, "sharpe_normalized"]
        + 0.15 * evaluated.loc[selected_mask, "avg_trade_return_normalized"]
        + 0.10 * evaluated.loc[selected_mask, "capture_ratio_normalized"]
        + 0.05 * evaluated.loc[selected_mask, "executed_trades_normalized"]
        - 0.05 * evaluated.loc[selected_mask, "max_drawdown_normalized"]
        - 0.05 * evaluated.loc[selected_mask, "avg_etd_normalized"]
    )
    return evaluated

SELECTION_V2_COLUMNS = [
    "run_id",
    "rank",
    "score",
    "total_return_simple",
    "sum_trade_return",
    "capital_efficiency",
    "avg_etd",
    "executed_trades",
    "ladder_ready",
    "norm_return",
    "norm_efficiency",
    "norm_etd",
    "norm_trades",
    "score_return_component",
    "score_efficiency_component",
    "score_etd_component",
    "score_trades_component",
]

def _empty_selection_v2_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=SELECTION_V2_COLUMNS)

def _debug_selection_v2_stage(message: str, frame: pd.DataFrame) -> None:
    print(f"[selection_v2] {message}: {len(frame.index)}")

def _debug_selection_v2_samples(report_df: pd.DataFrame) -> None:
    sample_columns = ["run_id", "avg_return_per_trade", "max_drawdown", "total_return_simple"]
    available_columns = [column for column in sample_columns if column in report_df.columns]
    if available_columns:
        print("[selection_v2] sample run_performance_report values:")
        print(report_df.loc[:, available_columns].head(5).to_string(index=False))

def _debug_selection_v2_top(label: str, frame: pd.DataFrame) -> None:
    preview_columns = [column for column in ["run_id", "total_return_simple", "capital_efficiency", "avg_etd", "executed_trades", "score"] if column in frame.columns]
    if preview_columns:
        print(f"[selection_v2] {label}:")
        print(frame.loc[:, preview_columns].head(5).to_string(index=False))

def _build_selection_v2_frame(output_root: Path) -> pd.DataFrame:
    report_df = _read_csv(output_root / "run_performance_report.csv")
    if report_df.empty:
        _debug_selection_v2_stage("initial rows", report_df)
        return _empty_selection_v2_frame()

    _debug_selection_v2_stage("initial rows", report_df)
    _debug_selection_v2_samples(report_df)

    evaluated = report_df.copy()
    if "sum_trade_return" not in evaluated.columns and "sum_trade_return_pct" in evaluated.columns:
        evaluated["sum_trade_return"] = pd.to_numeric(evaluated.get("sum_trade_return_pct"), errors="coerce") / 100.0
    if "avg_return_per_trade" not in evaluated.columns and "avg_pnl" in evaluated.columns:
        evaluated["avg_return_per_trade"] = pd.to_numeric(evaluated.get("avg_pnl"), errors="coerce")
    evaluated["max_drawdown"] = pd.to_numeric(evaluated.get("max_drawdown"), errors="coerce").fillna(0.0).map(
        lambda value: value / 100.0 if value > 1.0 else value
    )
    evaluated["capital_efficiency"] = evaluated.apply(
        lambda row: (_safe_float(row.get("total_return_simple")) / _safe_float(row.get("sum_trade_return")))
        if _safe_float(row.get("sum_trade_return")) != 0.0
        else 0.0,
        axis=1,
    )
    evaluated["ladder_ready"] = pd.to_numeric(evaluated.get("avg_mfe"), errors="coerce").fillna(0.0) > pd.to_numeric(evaluated.get("avg_mae"), errors="coerce").fillna(0.0).abs()

    survivors = evaluated.copy()
    survivors = survivors.loc[pd.to_numeric(survivors.get("executed_trades"), errors="coerce").fillna(0.0) >= 10].copy()
    _debug_selection_v2_stage("after executed_trades filter", survivors)

    survivors = survivors.loc[pd.to_numeric(survivors.get("total_return_simple"), errors="coerce").fillna(0.0) > 0.0].copy()
    _debug_selection_v2_stage("after total_return_simple filter", survivors)

    survivors = survivors.loc[pd.to_numeric(survivors.get("max_drawdown"), errors="coerce").fillna(float("inf")) < 0.30].copy()
    _debug_selection_v2_stage("after max_drawdown filter", survivors)

    if survivors.empty:
        return _empty_selection_v2_frame()

    _debug_selection_v2_top("top 5 runs before scoring", survivors.sort_values(by=["total_return_simple", "capital_efficiency", "executed_trades", "run_id"], ascending=[False, False, False, True]).reset_index(drop=True))

    survivors["log_executed_trades"] = pd.to_numeric(survivors.get("executed_trades"), errors="coerce").fillna(0.0).map(lambda value: math.log(max(value, 1.0)))
    survivors["norm_return"] = _normalize_series_unit(survivors["total_return_simple"])
    survivors["norm_efficiency"] = _normalize_series_unit(survivors["capital_efficiency"])
    survivors["norm_etd"] = _normalize_series_unit(survivors["avg_etd"])
    survivors["norm_trades"] = _normalize_series_unit(survivors["log_executed_trades"])

    survivors["score_return_component"] = 0.5 * survivors["norm_return"]
    survivors["score_efficiency_component"] = 0.2 * survivors["norm_efficiency"]
    survivors["score_etd_component"] = -0.2 * survivors["norm_etd"]
    survivors["score_trades_component"] = 0.1 * survivors["norm_trades"]
    survivors["score"] = (
        survivors["score_return_component"]
        + survivors["score_efficiency_component"]
        + survivors["score_etd_component"]
        + survivors["score_trades_component"]
    )
    survivors = survivors.sort_values(by=["score", "total_return_simple", "capital_efficiency", "executed_trades", "run_id"], ascending=[False, False, False, False, True]).reset_index(drop=True)
    survivors["rank"] = survivors.index + 1

    _debug_selection_v2_stage("rows after filtering", survivors)
    _debug_selection_v2_top("top 5 runs after scoring", survivors)

    top_k = min(5, len(survivors.index))
    return survivors.loc[: top_k - 1, SELECTION_V2_COLUMNS]


def _top_config_payload(row: pd.Series) -> dict[str, Any]:
    payload = {
        "run_id": row["run_id"],
        "score": float(row["score"]),
        "total_return": float(row["total_return"]),
        "sharpe": float(row["sharpe"]),
        "avg_trade_return": float(row["avg_trade_return"]),
        "avg_pnl": float(row["avg_pnl"]),
        "capture_ratio": float(row["capture_ratio"]),
        "executed_trades": int(row["executed_trades"]),
        "max_drawdown": float(row["max_drawdown"]),
        "avg_etd": float(row["avg_etd"]),
        "stop_loss_share": float(row["stop_loss_share"]),
        "params": {},
    }
    for column, value in row.items():
        if column in SUMMARY_EXCLUDE_COLUMNS or column.endswith("_normalized"):
            continue
        if column in payload or column in {"rejection_reason", "selected", "score", "ladder_ready", "executed_trades", "avg_pnl", "avg_mfe", "avg_mae", "avg_etd", "capture_ratio", "pain_gain_ratio", "etd_ratio", "stop_loss_share"}:
            continue
        if pd.isna(value):
            continue
        payload["params"][column] = value.item() if hasattr(value, "item") else value
    return payload

def write_selection_artifacts(output_dir: str | Path) -> dict[str, Path | pd.DataFrame]:
    output_root = Path(output_dir)
    selection_df = _apply_selection_rules(_build_selection_frame(output_root))
    selection_v2_df = _build_selection_v2_frame(output_root)

    report_path = output_root / "selection_report.csv"
    ranked_path = output_root / "selection_ranked.csv"
    top_config_path = output_root / "top_config.json"
    report_v2_path = output_root / "selection_report_v2.csv"

    if selection_df.empty:
        pd.DataFrame().to_csv(report_path, index=False)
        pd.DataFrame().to_csv(ranked_path, index=False)
        selection_v2_df.to_csv(report_v2_path, index=False)
        top_config_path.write_text(json.dumps({"selected": False, "reason": "no_runs"}, indent=2), encoding="utf-8")
        return {
            "selection_report_path": report_path,
            "selection_ranked_path": ranked_path,
            "selection_report_v2_path": report_v2_path,
            "top_config_path": top_config_path,
            "selection_frame": selection_df,
            "selection_v2_frame": selection_v2_df,
        }

    selection_df.to_csv(report_path, index=False)
    ranked_df = selection_df.loc[selection_df["selected"]].sort_values(by=["score", "total_return", "sharpe"], ascending=[False, False, False]).head(5)
    ranked_df.to_csv(ranked_path, index=False)
    selection_v2_df.to_csv(report_v2_path, index=False)

    if ranked_df.empty:
        top_payload: dict[str, Any] = {"selected": False, "reason": "no_qualified_configs"}
    else:
        top_payload = _top_config_payload(ranked_df.iloc[0])
    top_config_path.write_text(json.dumps(top_payload, indent=2), encoding="utf-8")

    return {
        "selection_report_path": report_path,
        "selection_ranked_path": ranked_path,
        "selection_report_v2_path": report_v2_path,
        "top_config_path": top_config_path,
        "selection_frame": selection_df,
        "selection_v2_frame": selection_v2_df,
    }
