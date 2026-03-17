"""Result aggregation and ranking for experiment runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import yaml


SUMMARY_COLUMNS = [
    "z_entry",
    "z_exit",
    "use_trend_filter",
    "use_art_filter",
    "total_return",
    "sharpe",
    "max_drawdown",
    "num_trades",
]

RANKING_DEFAULTS = {
    "sharpe": -999.0,
    "total_return": -999.0,
    "max_drawdown": 999.0,
}


def _safe_float(value: Any, fallback: float) -> float:
    """Return float value or fallback when value is missing/non-numeric."""
    if value is None:
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON payload from file; return empty payload on failure."""
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML payload from file; return empty payload on failure."""
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _normalize_run_payload(run_dir: Path) -> dict[str, Any]:
    """Load canonical per-run payload and support legacy fallback files."""
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
    """Collect one standardized record per run directory under an experiment output path."""
    records: list[dict[str, Any]] = []

    run_dirs = sorted(path for path in output_root.iterdir() if path.is_dir() and path.name.startswith("run_"))
    for run_dir in run_dirs:
        run_payload = _normalize_run_payload(run_dir)
        params = run_payload["params"]
        metrics = run_payload["metrics"]
        meta = run_payload["meta"]

        record = {
            "run_id": str(meta.get("run_id") or run_dir.name),
            "params": params,
            "metrics": metrics,
            "meta": meta,
            "z_entry": params.get("z_entry"),
            "z_exit": params.get("z_exit"),
            "use_trend_filter": params.get("use_trend_filter"),
            "use_art_filter": params.get("use_art_filter"),
            "total_return": _safe_float(metrics.get("total_return", metrics.get("rtot")), RANKING_DEFAULTS["total_return"]),
            "sharpe": _safe_float(metrics.get("sharpe"), RANKING_DEFAULTS["sharpe"]),
            "max_drawdown": _safe_float(metrics.get("max_drawdown"), RANKING_DEFAULTS["max_drawdown"]),
            "num_trades": metrics.get("num_trades", metrics.get("trade_count")),
        }
        records.append(record)

    return records


def _write_summary(path: Path, records: list[dict[str, Any]]) -> None:
    """Write records to CSV with fixed column order."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column) for column in SUMMARY_COLUMNS})


def rank_results(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort records by sharpe desc, then total return desc."""
    return sorted(
        records,
        key=lambda row: (
            -_safe_float(row.get("sharpe"), RANKING_DEFAULTS["sharpe"]),
            -_safe_float(row.get("total_return"), RANKING_DEFAULTS["total_return"]),
        ),
    )


def build_summary(experiment_name: str) -> tuple[Path, Path, list[dict[str, Any]]]:
    """Build summary.csv + summary_sorted.csv for an experiment and return ranked records."""
    output_root = Path("outputs") / experiment_name
    output_root.mkdir(parents=True, exist_ok=True)

    records = collect_run_results(output_root)
    summary_path = output_root / "summary.csv"
    _write_summary(summary_path, records)

    sorted_records = rank_results(records)
    summary_sorted_path = output_root / "summary_sorted.csv"
    _write_summary(summary_sorted_path, sorted_records)

    return summary_path, summary_sorted_path, sorted_records
