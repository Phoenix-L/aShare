"""Result aggregation and ranking for experiment runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml

from ashare.research.config_selector import write_selection_artifacts

METRIC_COLUMNS = ["total_return", "sharpe", "max_drawdown", "num_trades"]
PARAMETER_COLUMN_PREFERENCE = {
    "mean_reversion_advanced": [
        "z_entry",
        "z_exit",
        "use_trend_filter",
        "use_atr_filter",
        "use_art_filter",
        "atr_ratio_min",
    ],
    "shock_reversion_intraday": [
        "excursion_lookback_bars",
        "excursion_threshold",
        "speed_scale",
        "noise_lookback",
        "noise_ratio_scale",
        "score_weight_depth",
        "score_weight_speed",
        "score_weight_stabilization",
        "score_weight_noise_penalty",
        "use_shock_score_filter",
        "shock_score_min",
        "shock_score_max",
        "take_profit_pct",
        "recovery_frac",
        "max_hold_bars",
        "stop_loss_pct",
    ],
}
DEFAULT_PARAMETER_COLUMN_PREFERENCE = [
    "signal_mode",
    "z_entry",
    "z_exit",
    "use_trend_filter",
    "use_atr_filter",
    "use_art_filter",
    "use_multi_day_excursion",
    "excursion_lookback_bars",
    "excursion_threshold",
    "excursion_window",
    "excursion_min",
    "atr_ratio_min",
]
RANKING_DEFAULTS = {"sharpe": -999.0, "total_return": -999.0, "max_drawdown": 999.0}
SHOCK_SCORE_BUCKETS = [(0.0, 20.0), (20.0, 40.0), (40.0, 60.0), (60.0, 80.0), (80.0, 100.0)]


def _safe_float(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _normalize_run_payload(run_dir: Path) -> dict[str, Any]:
    run_payload = _load_json(run_dir / "run_result.json")
    if run_payload:
        params = run_payload.get("params") if isinstance(run_payload.get("params"), dict) else {}
        metrics = run_payload.get("metrics") if isinstance(run_payload.get("metrics"), dict) else {}
        meta = run_payload.get("meta") if isinstance(run_payload.get("meta"), dict) else {}
        return {"params": params, "metrics": metrics, "meta": meta}

    metrics = _load_json(run_dir / "metrics.json")
    snapshot = _load_yaml(run_dir / "config_snapshot.yaml")
    params = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}
    meta = {
        "run_id": run_dir.name,
        "strategy": snapshot.get("strategy"),
        "symbol": snapshot.get("symbol"),
        "date_range": snapshot.get("date_range"),
    }
    return {"params": params, "metrics": metrics, "meta": meta}


def collect_run_results(output_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    run_dirs = sorted(path for path in output_root.iterdir() if path.is_dir() and path.name.startswith("run_"))
    for run_dir in run_dirs:
        run_payload = _normalize_run_payload(run_dir)
        params = run_payload["params"]
        metrics = run_payload["metrics"]
        meta = run_payload["meta"]
        use_atr_filter = params.get("use_atr_filter", params.get("use_art_filter"))
        atr_ratio_min = params.get("atr_ratio_min", params.get("art_threshold"))

        record = {
            "run_id": str(meta.get("run_id") or run_dir.name),
            "params": params,
            "metrics": metrics,
            "meta": meta,
            "signal_mode": params.get("signal_mode", "zscore"),
            "z_entry": params.get("z_entry"),
            "z_exit": params.get("z_exit"),
            "use_atr_filter": use_atr_filter,
            "use_art_filter": use_atr_filter,
            "use_multi_day_excursion": params.get("use_multi_day_excursion"),
            "excursion_lookback_bars": params.get("excursion_lookback_bars"),
            "excursion_threshold": params.get("excursion_threshold"),
            "speed_scale": params.get("speed_scale"),
            "noise_lookback": params.get("noise_lookback"),
            "noise_ratio_scale": params.get("noise_ratio_scale"),
            "score_weight_depth": params.get("score_weight_depth"),
            "score_weight_speed": params.get("score_weight_speed"),
            "score_weight_stabilization": params.get("score_weight_stabilization"),
            "score_weight_noise_penalty": params.get("score_weight_noise_penalty"),
            "use_shock_score_filter": params.get("use_shock_score_filter"),
            "shock_score_min": params.get("shock_score_min"),
            "shock_score_max": params.get("shock_score_max"),
            "excursion_window": params.get("excursion_window"),
            "excursion_min": params.get("excursion_min"),
            "take_profit_pct": params.get("take_profit_pct"),
            "recovery_frac": params.get("recovery_frac"),
            "max_hold_bars": params.get("max_hold_bars"),
            "stop_loss_pct": params.get("stop_loss_pct"),
            "atr_ratio_min": atr_ratio_min,
            "total_return": _safe_float(metrics.get("total_return", metrics.get("rtot")), RANKING_DEFAULTS["total_return"]),
            "sharpe": _safe_float(metrics.get("sharpe"), RANKING_DEFAULTS["sharpe"]),
            "max_drawdown": _safe_float(metrics.get("max_drawdown"), RANKING_DEFAULTS["max_drawdown"]),
            "num_trades": metrics.get("num_trades", metrics.get("trade_count")),
        }
        records.append(record)

    return records


def _summary_columns(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return DEFAULT_PARAMETER_COLUMN_PREFERENCE + METRIC_COLUMNS

    strategy_name = records[0].get("meta", {}).get("strategy")
    preferred = PARAMETER_COLUMN_PREFERENCE.get(strategy_name, DEFAULT_PARAMETER_COLUMN_PREFERENCE)
    columns = []
    for column in preferred:
        if any(
            column in (record.get("params") or {})
            or (column == "use_atr_filter" and any(key in (record.get("params") or {}) for key in {"use_atr_filter", "use_art_filter"}))
            or (column == "use_art_filter" and any(key in (record.get("params") or {}) for key in {"use_atr_filter", "use_art_filter"}))
            or (column == "atr_ratio_min" and any(key in (record.get("params") or {}) for key in {"atr_ratio_min", "art_threshold"}))
            for record in records
        ):
            columns.append(column)
    return columns + METRIC_COLUMNS


def _write_summary(path: Path, records: list[dict[str, Any]]) -> None:
    columns = _summary_columns(records)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column) for column in columns})


def _load_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _bucket_label(lower: float, upper: float) -> str:
    return f"{int(lower)}-{int(upper)}"


def _bucket_for_score(score: float | None) -> tuple[float, float] | None:
    if score is None:
        return None
    score = max(0.0, min(100.0, float(score)))
    for lower, upper in SHOCK_SCORE_BUCKETS:
        if upper == 100.0:
            if lower <= score <= upper:
                return lower, upper
            continue
        if lower <= score < upper:
            return lower, upper
    return None



def _aggregate_trade_quality(trades: list[dict[str, Any]]) -> dict[str, float]:
    pnl_values = [_safe_float(trade.get("pnl_pct"), 0.0) for trade in trades]
    mfe_values = [_safe_float(trade.get("mfe_pct", trade.get("max_favorable_excursion")), 0.0) for trade in trades]
    mae_values = [_safe_float(trade.get("mae_pct", trade.get("max_adverse_excursion")), 0.0) for trade in trades]
    etd_values = [_safe_float(trade.get("etd"), 0.0) for trade in trades]
    holding_bars_values = [_safe_float(trade.get("holding_bars"), 0.0) for trade in trades]
    executed_trades = len(trades)
    return {
        "executed_trades": executed_trades,
        "avg_pnl": _avg(pnl_values),
        "avg_mfe": _avg(mfe_values),
        "avg_mae": _avg(mae_values),
        "avg_etd": _avg(etd_values),
        "win_rate": (sum(1 for value in pnl_values if value > 0.0) / executed_trades) if executed_trades else 0.0,
        "stop_loss_share": (sum(1 for trade in trades if trade.get("exit_reason") == "stop_loss") / executed_trades) if executed_trades else 0.0,
        "avg_holding_bars": _avg(holding_bars_values),
    }


def _aggregate_signal_component_averages(signals: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "avg_depth_score": _avg([_safe_float(signal.get("depth_score"), 0.0) for signal in signals]),
        "avg_speed_score": _avg([_safe_float(signal.get("speed_score"), 0.0) for signal in signals]),
        "avg_stabilization_score": _avg([_safe_float(signal.get("stabilization_score"), 0.0) for signal in signals]),
        "avg_noise_penalty": _avg([_safe_float(signal.get("noise_penalty"), 0.0) for signal in signals]),
    }

def write_shock_score_bucket_analysis(output_root: Path) -> Path:
    """Write score-bucket quality metrics for shock_reversion_intraday experiments."""
    signals = _load_csv_rows(output_root / "signals.csv")
    trades = _load_csv_rows(output_root / "trades.csv")

    signal_counts = {_bucket_label(lower, upper): 0 for lower, upper in SHOCK_SCORE_BUCKETS}
    trade_buckets: dict[str, list[dict[str, Any]]] = {_bucket_label(lower, upper): [] for lower, upper in SHOCK_SCORE_BUCKETS}

    for signal in signals:
        bucket = _bucket_for_score(_safe_float(signal.get("shock_score"), None))
        if bucket is None:
            continue
        signal_counts[_bucket_label(*bucket)] += 1

    for trade in trades:
        bucket = _bucket_for_score(_safe_float(trade.get("shock_score_at_entry"), None))
        if bucket is None:
            continue
        trade_buckets[_bucket_label(*bucket)].append(trade)

    rows: list[dict[str, Any]] = []
    for lower, upper in SHOCK_SCORE_BUCKETS:
        label = _bucket_label(lower, upper)
        bucket_trades = trade_buckets[label]
        trade_quality = _aggregate_trade_quality(bucket_trades)
        rows.append(
            {
                "score_bucket": label,
                "bucket_min": lower,
                "bucket_max": upper,
                "signal_count": signal_counts[label],
                "executed_trades": trade_quality["executed_trades"],
                "avg_pnl": trade_quality["avg_pnl"],
                "avg_mfe": trade_quality["avg_mfe"],
                "avg_mae": trade_quality["avg_mae"],
                "avg_etd": trade_quality["avg_etd"],
                "win_rate": trade_quality["win_rate"],
                "stop_loss_share": trade_quality["stop_loss_share"],
            }
        )

    path = output_root / "shock_score_buckets.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "score_bucket",
                "bucket_min",
                "bucket_max",
                "signal_count",
                "executed_trades",
                "avg_pnl",
                "avg_mfe",
                "avg_mae",
                "avg_etd",
                "win_rate",
                "stop_loss_share",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def write_shock_score_overshock_analysis(output_root: Path) -> Path:
    """Write explicit 60-80 vs 80-100 overshock diagnostics for shock experiments."""
    signals = _load_csv_rows(output_root / "signals.csv")
    trades = _load_csv_rows(output_root / "trades.csv")

    selected_buckets = ["60-80", "80-100"]
    signal_buckets = {label: [] for label in selected_buckets}
    trade_buckets = {label: [] for label in selected_buckets}

    for signal in signals:
        bucket = _bucket_for_score(_safe_float(signal.get("shock_score"), None))
        if bucket is None:
            continue
        label = _bucket_label(*bucket)
        if label in signal_buckets:
            signal_buckets[label].append(signal)

    for trade in trades:
        bucket = _bucket_for_score(_safe_float(trade.get("shock_score_at_entry"), None))
        if bucket is None:
            continue
        label = _bucket_label(*bucket)
        if label in trade_buckets:
            trade_buckets[label].append(trade)

    baseline = _aggregate_trade_quality(trade_buckets["60-80"])
    rows: list[dict[str, Any]] = []
    for label in selected_buckets:
        trade_quality = _aggregate_trade_quality(trade_buckets[label])
        component_averages = _aggregate_signal_component_averages(signal_buckets[label])
        rows.append(
            {
                "bucket": label,
                "signal_count": len(signal_buckets[label]),
                **trade_quality,
                **component_averages,
                "pnl_diff_vs_60_80": trade_quality["avg_pnl"] - baseline["avg_pnl"],
                "winrate_diff_vs_60_80": trade_quality["win_rate"] - baseline["win_rate"],
                "stoploss_diff_vs_60_80": trade_quality["stop_loss_share"] - baseline["stop_loss_share"],
            }
        )

    path = output_root / "shock_score_overshock_analysis.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "bucket",
                "signal_count",
                "executed_trades",
                "avg_pnl",
                "avg_mfe",
                "avg_mae",
                "avg_etd",
                "win_rate",
                "stop_loss_share",
                "avg_holding_bars",
                "avg_depth_score",
                "avg_speed_score",
                "avg_stabilization_score",
                "avg_noise_penalty",
                "pnl_diff_vs_60_80",
                "winrate_diff_vs_60_80",
                "stoploss_diff_vs_60_80",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def rank_results(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda row: (
            -_safe_float(row.get("sharpe"), RANKING_DEFAULTS["sharpe"]),
            -_safe_float(row.get("total_return"), RANKING_DEFAULTS["total_return"]),
        ),
    )


def build_summary(experiment_name: str) -> tuple[Path, Path, list[dict[str, Any]]]:
    output_root = Path("outputs") / experiment_name
    output_root.mkdir(parents=True, exist_ok=True)

    records = collect_run_results(output_root)
    summary_path = output_root / "summary.csv"
    _write_summary(summary_path, records)

    sorted_records = rank_results(records)
    summary_sorted_path = output_root / "summary_sorted.csv"
    _write_summary(summary_sorted_path, sorted_records)

    if records and records[0].get("meta", {}).get("strategy") == "shock_reversion_intraday":
        write_selection_artifacts(output_root)
        write_shock_score_bucket_analysis(output_root)
        write_shock_score_overshock_analysis(output_root)

    return summary_path, summary_sorted_path, sorted_records
