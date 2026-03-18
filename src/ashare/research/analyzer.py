from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


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


def _extract_top_configs(summary_sorted_df: pd.DataFrame, limit: int = 5) -> list[dict[str, Any]]:
    """Build top-ranked configurations from the sorted summary artifact."""
    if summary_sorted_df.empty:
        return []

    metric_columns = {"sharpe", "total_return", "rtot", "max_drawdown", "num_trades"}
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
                "return": _safe_float(row.get("total_return", row.get("rtot"))),
                "params": params,
            }
        )

    return top_configs


def analyze_experiment(output_dir: str) -> dict[str, Any]:
    """Aggregate experiment outputs into deterministic research metrics."""
    output_path = Path(output_dir)
    if not output_path.exists() or not output_path.is_dir():
        raise FileNotFoundError(f"Experiment output directory not found: {output_dir}")

    summary_df = _read_summary_csv(output_path / "summary.csv")
    summary_sorted_df = _read_summary_csv(output_path / "summary_sorted.csv")

    run_dirs = sorted(path for path in output_path.iterdir() if path.is_dir() and path.name.startswith("run_"))

    sharpe_values: list[float] = []
    return_values: list[float] = []
    trade_efficiencies: list[float] = []
    art_block_rates: list[float] = []
    excursion_block_rates: list[float] = []

    for run_dir in run_dirs:
        metrics = _load_json(run_dir / "metrics.json")
        diagnostics_summary = _load_json(run_dir / "diagnostics_summary.json")

        if metrics:
            sharpe_values.append(_safe_float(metrics.get("sharpe")))
            return_values.append(_safe_float(metrics.get("total_return", metrics.get("rtot"))))

        entry_signals = _safe_float(diagnostics_summary.get("entry_signals"))
        executed_trades = _safe_float(diagnostics_summary.get("executed_trades"))
        blocked_by_art = _safe_float(diagnostics_summary.get("blocked_by_art"))
        blocked_by_excursion = _safe_float(diagnostics_summary.get("blocked_by_excursion"))

        if entry_signals > 0:
            trade_efficiencies.append(executed_trades / entry_signals)
            art_block_rates.append(blocked_by_art / entry_signals)
            excursion_block_rates.append(blocked_by_excursion / entry_signals)
        else:
            trade_efficiencies.append(0.0)
            art_block_rates.append(0.0)
            excursion_block_rates.append(0.0)

    if not sharpe_values and not summary_df.empty:
        sharpe_values = pd.to_numeric(summary_df.get("sharpe"), errors="coerce").fillna(0.0).tolist()
    if not return_values and not summary_df.empty:
        return_values = pd.to_numeric(summary_df.get("total_return", summary_df.get("rtot")), errors="coerce").fillna(0.0).tolist()

    total_runs = len(run_dirs)
    if total_runs == 0 and not summary_df.empty:
        total_runs = int(len(summary_df))

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
            "blocked_by_art": sum(art_block_rates) / len(art_block_rates) if art_block_rates else 0.0,
            "blocked_by_excursion": sum(excursion_block_rates) / len(excursion_block_rates) if excursion_block_rates else 0.0,
        },
        "top_configs": _extract_top_configs(summary_sorted_df),
    }
