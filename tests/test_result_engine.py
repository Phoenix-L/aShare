import json
from pathlib import Path

import yaml

from ashare.experiment.result import build_summary, collect_run_results, rank_results


def _write_run(output_root: Path, run_id: str, metrics: dict | None, parameters: dict | None = None, meta: dict | None = None) -> None:
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    metrics_payload = metrics or {}
    params_payload = parameters or {}
    meta_payload = {"run_id": run_id, **(meta or {})}
    run_payload = {"params": params_payload, "metrics": metrics_payload, "meta": meta_payload}
    (run_dir / "run_result.json").write_text(json.dumps(run_payload), encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps(metrics_payload), encoding="utf-8")
    snapshot = {"parameters": params_payload, "strategy": meta_payload.get("strategy"), "symbol": meta_payload.get("symbol"), "date_range": meta_payload.get("date_range")}
    (run_dir / "config_snapshot.yaml").write_text(yaml.safe_dump(snapshot, sort_keys=False), encoding="utf-8")


def test_build_summary_omits_irrelevant_mean_reversion_columns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "demo_experiment"
    output_root.mkdir(parents=True, exist_ok=True)
    _write_run(output_root, "run_001", metrics={"sharpe": 1.2, "total_return": 0.18, "max_drawdown": 0.12, "num_trades": 8}, parameters={"z_entry": -1.5, "z_exit": 1.0, "use_trend_filter": True, "use_atr_filter": False}, meta={"strategy": "mean_reversion_advanced"})
    _write_run(output_root, "run_002", metrics={"sharpe": 1.8, "total_return": 0.25, "max_drawdown": 0.10, "num_trades": 10}, parameters={"z_entry": -2.0, "z_exit": 1.2, "use_trend_filter": False, "use_atr_filter": True}, meta={"strategy": "mean_reversion_advanced"})
    summary_path, sorted_path, ranked = build_summary("demo_experiment")
    assert summary_path.exists()
    assert sorted_path.exists()
    assert ranked[0]["run_id"] == "run_002"
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "z_entry,z_exit,use_trend_filter,use_atr_filter,use_art_filter,total_return,sharpe,max_drawdown,num_trades" in summary_text
    assert "excursion_threshold" not in summary_text
    assert "signal_mode" not in summary_text


def test_build_summary_omits_irrelevant_shock_columns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "shock_experiment"
    output_root.mkdir(parents=True, exist_ok=True)
    _write_run(output_root, "run_001", metrics={"sharpe": 1.1, "total_return": 0.08, "max_drawdown": 0.05, "num_trades": 3}, parameters={"excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.02, "recovery_frac": 0.5, "max_hold_bars": 10, "stop_loss_pct": 0.1}, meta={"strategy": "shock_reversion_intraday"})
    summary_path, _, _ = build_summary("shock_experiment")
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "excursion_lookback_bars" in summary_text
    assert "use_trend_filter" not in summary_text
    assert "trend_ma_period" not in summary_text
    assert "z_entry" not in summary_text
    assert "z_exit" not in summary_text


def test_rank_results_handles_missing_metrics() -> None:
    records = [{"run_id": "run_001", "sharpe": None, "total_return": 0.2, "max_drawdown": 0.1}, {"run_id": "run_002", "sharpe": 1.1, "total_return": 0.1, "max_drawdown": 0.2}, {"run_id": "run_003", "total_return": None, "max_drawdown": None}]
    ranked = rank_results(records)
    assert ranked[0]["run_id"] == "run_002"
    assert ranked[-1]["run_id"] == "run_003"


def test_collect_run_results_tolerates_missing_files(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs" / "missing_metrics"
    output_root.mkdir(parents=True, exist_ok=True)
    _write_run(output_root, "run_001", metrics=None, parameters={"z_entry": -2.0, "z_exit": 1.2}, meta={"strategy": "mean_reversion_advanced"})
    records = collect_run_results(output_root)
    assert len(records) == 1
    assert records[0]["run_id"] == "run_001"
    assert records[0]["sharpe"] == -999.0
    assert set(records[0].keys()) >= {"params", "metrics", "meta"}
