from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert numeric-like values to float with a deterministic fallback."""
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
    """Load a JSON object from disk, returning an empty mapping on missing/invalid files."""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML object from disk, returning an empty mapping on missing/invalid files."""
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_summary_csv(path: Path) -> pd.DataFrame:
    """Read a summary CSV if present, otherwise return an empty DataFrame."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _as_native(value: Any) -> Any:
    """Convert pandas/numpy scalars to plain Python values for JSON/Markdown output."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            return value
    return value


def _coerce_optional_bool(value: Any) -> bool | None:
    """Normalize bool-like values while preserving missing values."""
    native = _as_native(value)
    if native is None:
        return None
    if isinstance(native, bool):
        return native
    if isinstance(native, str):
        lowered = native.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return bool(native)


def _summary_row_for_run(summary_df: pd.DataFrame, run_dir: Path) -> dict[str, Any]:
    """Return the summary row aligned to a run directory when available."""
    if summary_df.empty:
        return {}
    try:
        run_index = int(run_dir.name.split("_")[-1]) - 1
    except (TypeError, ValueError):
        return {}
    if run_index < 0 or run_index >= len(summary_df):
        return {}
    row = summary_df.iloc[run_index]
    return {column: _as_native(row[column]) for column in summary_df.columns}


def _build_run_record(run_dir: Path, summary_row: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized per-run record combining metrics, diagnostics, and parameters."""
    metrics = _load_json(run_dir / "metrics.json")
    diagnostics_summary = _load_json(run_dir / "diagnostics_summary.json")
    snapshot = _load_yaml(run_dir / "config_snapshot.yaml")
    params = snapshot.get("parameters") if isinstance(snapshot.get("parameters"), dict) else {}

    def _param(name: str, *fallback_names: str) -> Any:
        lookup_names = (name, *fallback_names)
        for lookup_name in lookup_names:
            if lookup_name in params:
                return _as_native(params.get(lookup_name))
            if lookup_name in summary_row:
                return _as_native(summary_row.get(lookup_name))
        return None

    blocked_by_atr = _safe_float(diagnostics_summary.get("blocked_by_atr", diagnostics_summary.get("blocked_by_art")))

    return {
        "run_id": run_dir.name,
        "sharpe": _safe_float(metrics.get("sharpe", summary_row.get("sharpe"))),
        "return": _safe_float(
            metrics.get(
                "total_return_simple",
                metrics.get("total_return", summary_row.get("total_return_simple", summary_row.get("total_return", summary_row.get("rtot")))),
            )
        ),
        "signal_mode": _param("signal_mode") or "zscore",
        "z_entry": _safe_float(_param("z_entry"), default=0.0),
        "z_exit": _safe_float(_param("z_exit"), default=0.0),
        "use_multi_day_excursion": _coerce_optional_bool(_param("use_multi_day_excursion")),
        "excursion_lookback_bars": _safe_float(_param("excursion_lookback_bars"), default=0.0),
        "excursion_threshold": _safe_float(_param("excursion_threshold"), default=0.0),
        "excursion_min": _safe_float(_param("excursion_min"), default=0.0),
        "excursion_window": _safe_float(_param("excursion_window"), default=0.0),
        "use_atr_filter": _coerce_optional_bool(_param("use_atr_filter", "use_art_filter")),
        "atr_ratio_min": _safe_float(_param("atr_ratio_min", "art_threshold"), default=0.0),
        "entry_signals": _safe_float(diagnostics_summary.get("entry_signals")),
        "executed_trades": _safe_float(diagnostics_summary.get("executed_trades")),
        "blocked_by_atr": blocked_by_atr,
        "blocked_by_art": blocked_by_atr,
    }


def _extract_top_configs(summary_sorted_df: pd.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
    """Build top-ranked configurations from the sorted summary artifact."""
    if summary_sorted_df.empty:
        return []

    metric_columns = {"sharpe", "total_return", "total_return_simple", "total_return_log", "rtot", "max_drawdown", "num_trades"}
    top_configs: list[dict[str, Any]] = []

    for rank, (_, row) in enumerate(summary_sorted_df.head(limit).iterrows(), start=1):
        params = {
            column: _as_native(row[column])
            for column in summary_sorted_df.columns
            if column not in metric_columns and _as_native(row[column]) is not None
        }
        top_configs.append(
            {
                "rank": rank,
                "sharpe": _safe_float(row.get("sharpe")),
                "return": _safe_float(row.get("total_return_simple", row.get("total_return", row.get("rtot")))),
                "params": params,
            }
        )

    return top_configs


def _aggregate_group(frame: pd.DataFrame, column: str) -> dict[Any, dict[str, float | int]]:
    """Aggregate average Sharpe/return and run counts for a grouping column."""
    if frame.empty or column not in frame.columns:
        return {}

    grouped: dict[Any, dict[str, float | int]] = {}
    valid_frame = frame.dropna(subset=[column])
    if valid_frame.empty:
        return grouped

    for group_value, group_frame in valid_frame.groupby(column, dropna=True):
        native_group_value = _as_native(group_value)
        grouped[native_group_value] = {
            "avg_sharpe": float(group_frame["sharpe"].mean()),
            "avg_return": float(group_frame["return"].mean()),
            "num_runs": int(len(group_frame)),
        }

    return grouped


def _build_parameter_analysis(run_frame: pd.DataFrame) -> dict[str, dict[Any, dict[str, float | int]]]:
    """Compute grouped parameter contribution analysis for excursion controls."""
    return {
        "excursion_toggle": _aggregate_group(run_frame, "use_multi_day_excursion"),
        "excursion_min": _aggregate_group(run_frame, "excursion_min"),
        "excursion_window": _aggregate_group(run_frame, "excursion_window"),
    }


def analyze_experiment(output_dir: str) -> dict[str, Any]:
    """Aggregate experiment outputs into deterministic research metrics."""
    output_path = Path(output_dir)
    if not output_path.exists() or not output_path.is_dir():
        raise FileNotFoundError(f"Experiment output directory not found: {output_dir}")

    summary_df = _read_summary_csv(output_path / "summary.csv")
    summary_sorted_df = _read_summary_csv(output_path / "summary_sorted.csv")
    run_dirs = sorted(path for path in output_path.iterdir() if path.is_dir() and path.name.startswith("run_"))

    run_records = [_build_run_record(run_dir, _summary_row_for_run(summary_df, run_dir)) for run_dir in run_dirs]
    run_frame = pd.DataFrame(run_records)

    if run_frame.empty and not summary_df.empty:
        run_frame = pd.DataFrame(
            {
                "sharpe": pd.to_numeric(summary_df.get("sharpe"), errors="coerce").fillna(0.0),
                "return": pd.to_numeric(summary_df.get("total_return_simple", summary_df.get("total_return", summary_df.get("rtot"))), errors="coerce").fillna(0.0),
                "signal_mode": summary_df.get("signal_mode").fillna("zscore") if "signal_mode" in summary_df else "zscore",
                "z_entry": pd.to_numeric(summary_df.get("z_entry"), errors="coerce").fillna(0.0),
                "z_exit": pd.to_numeric(summary_df.get("z_exit"), errors="coerce").fillna(0.0),
                "use_multi_day_excursion": summary_df.get("use_multi_day_excursion"),
                "excursion_lookback_bars": pd.to_numeric(summary_df.get("excursion_lookback_bars"), errors="coerce").fillna(0.0),
                "excursion_threshold": pd.to_numeric(summary_df.get("excursion_threshold"), errors="coerce").fillna(0.0),
                "excursion_min": pd.to_numeric(summary_df.get("excursion_min"), errors="coerce").fillna(0.0),
                "excursion_window": pd.to_numeric(summary_df.get("excursion_window"), errors="coerce").fillna(0.0),
                "use_atr_filter": summary_df.get("use_atr_filter", summary_df.get("use_art_filter")),
                "atr_ratio_min": pd.to_numeric(summary_df.get("atr_ratio_min", summary_df.get("art_threshold")), errors="coerce").fillna(0.0),
            }
        )
        if "use_multi_day_excursion" in run_frame.columns:
            run_frame["use_multi_day_excursion"] = run_frame["use_multi_day_excursion"].map(_coerce_optional_bool)
        if "use_atr_filter" in run_frame.columns:
            run_frame["use_atr_filter"] = run_frame["use_atr_filter"].map(_coerce_optional_bool)

    sharpe_values = run_frame["sharpe"].tolist() if "sharpe" in run_frame.columns else []
    return_values = run_frame["return"].tolist() if "return" in run_frame.columns else []

    trade_efficiencies: list[float] = []
    atr_block_rates: list[float] = []
    if not run_frame.empty:
        for _, row in run_frame.iterrows():
            entry_signals = _safe_float(row.get("entry_signals"))
            executed_trades = _safe_float(row.get("executed_trades"))
            blocked_by_atr = _safe_float(row.get("blocked_by_atr", row.get("blocked_by_art")))

            if entry_signals > 0:
                trade_efficiencies.append(executed_trades / entry_signals)
                atr_block_rates.append(blocked_by_atr / entry_signals)
            else:
                trade_efficiencies.append(0.0)
                atr_block_rates.append(0.0)

    total_runs = len(run_dirs)
    if total_runs == 0 and not summary_df.empty:
        total_runs = int(len(summary_df))

    avg_atr_block_rate = sum(atr_block_rates) / len(atr_block_rates) if atr_block_rates else 0.0
    return {
        "total_runs": int(total_runs),
        "best_sharpe": max(sharpe_values, default=0.0),
        "best_return": max(return_values, default=0.0),
        "avg_sharpe": sum(sharpe_values) / len(sharpe_values) if sharpe_values else 0.0,
        "avg_return": sum(return_values) / len(return_values) if return_values else 0.0,
        "trade_efficiency": {
            "avg": sum(trade_efficiencies) / len(trade_efficiencies) if trade_efficiencies else 0.0,
        },
        "filters": {
            "blocked_by_atr": avg_atr_block_rate,
            "blocked_by_art": avg_atr_block_rate,
        },
        "parameter_analysis": _build_parameter_analysis(run_frame),
        "top_configs": _extract_top_configs(summary_sorted_df),
    }
