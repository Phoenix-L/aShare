import json
from pathlib import Path

import pandas as pd
import pytest
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
    assert "z_entry,z_exit,use_trend_filter,use_atr_filter,use_art_filter,total_return,total_return_simple,total_return_log,sharpe,max_drawdown,num_trades" in summary_text
    assert "excursion_threshold" not in summary_text
    assert "signal_mode" not in summary_text

def test_build_summary_omits_irrelevant_shock_columns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "shock_experiment"
    output_root.mkdir(parents=True, exist_ok=True)
    _write_run(output_root, "run_001", metrics={"sharpe": 1.1, "total_return": 0.08, "max_drawdown": 0.05, "num_trades": 3}, parameters={"excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.02, "recovery_frac": 0.5, "max_hold_bars": 10, "stop_loss_pct": 0.1, "use_shock_score_filter": True, "shock_score_min": 60, "shock_score_max": 80}, meta={"strategy": "shock_reversion_intraday"})
    summary_path, _, _ = build_summary("shock_experiment")
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "excursion_lookback_bars" in summary_text
    assert "use_shock_score_filter" in summary_text
    assert "shock_score_min" in summary_text
    assert "shock_score_max" in summary_text
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

def test_build_summary_writes_shock_config_selection_artifacts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "shock_selection"
    output_root.mkdir(parents=True, exist_ok=True)

    runs = [
        (
            "run_001",
            {"excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.02, "recovery_frac": 0.4, "max_hold_bars": 12, "stop_loss_pct": 0.01},
            {"sharpe": 1.1, "total_return": 0.08, "max_drawdown": 0.05, "num_trades": 12},
            {"executed_trades": 12, "avg_return_per_trade": 0.015, "avg_mfe": 0.04, "avg_mae": -0.008, "avg_etd": 0.008},
        ),
        (
            "run_002",
            {"excursion_lookback_bars": 4, "excursion_threshold": 0.012, "take_profit_pct": 0.025, "recovery_frac": 0.45, "max_hold_bars": 10, "stop_loss_pct": 0.012},
            {"sharpe": 1.6, "total_return": 0.12, "max_drawdown": 0.04, "num_trades": 14},
            {"executed_trades": 14, "avg_return_per_trade": 0.018, "avg_mfe": 0.05, "avg_mae": -0.009, "avg_etd": 0.007},
        ),
        (
            "run_003",
            {"excursion_lookback_bars": 5, "excursion_threshold": 0.014, "take_profit_pct": 0.03, "recovery_frac": 0.5, "max_hold_bars": 9, "stop_loss_pct": 0.015},
            {"sharpe": 1.4, "total_return": 0.10, "max_drawdown": 0.06, "num_trades": 15},
            {"executed_trades": 15, "avg_return_per_trade": 0.016, "avg_mfe": 0.044, "avg_mae": -0.0085, "avg_etd": 0.0075},
        ),
        (
            "run_004",
            {"excursion_lookback_bars": 6, "excursion_threshold": 0.016, "take_profit_pct": 0.031, "recovery_frac": 0.55, "max_hold_bars": 8, "stop_loss_pct": 0.015},
            {"sharpe": 0.9, "total_return": 0.06, "max_drawdown": 0.07, "num_trades": 11},
            {"executed_trades": 11, "avg_return_per_trade": 0.012, "avg_mfe": 0.03, "avg_mae": -0.01, "avg_etd": 0.009},
        ),
        (
            "run_005",
            {"excursion_lookback_bars": 7, "excursion_threshold": 0.018, "take_profit_pct": 0.032, "recovery_frac": 0.6, "max_hold_bars": 7, "stop_loss_pct": 0.016},
            {"sharpe": 1.3, "total_return": 0.09, "max_drawdown": 0.03, "num_trades": 13},
            {"executed_trades": 13, "avg_return_per_trade": 0.014, "avg_mfe": 0.042, "avg_mae": -0.007, "avg_etd": 0.006},
        ),
        (
            "run_006",
            {"excursion_lookback_bars": 8, "excursion_threshold": 0.02, "take_profit_pct": 0.034, "recovery_frac": 0.65, "max_hold_bars": 6, "stop_loss_pct": 0.02},
            {"sharpe": 1.8, "total_return": 0.14, "max_drawdown": 0.05, "num_trades": 9},
            {"executed_trades": 9, "avg_return_per_trade": 0.02, "avg_mfe": 0.055, "avg_mae": -0.01, "avg_etd": 0.006},
        ),
    ]

    trade_rows: list[dict[str, object]] = []
    for run_id, parameters, metrics, diagnostics in runs:
        _write_run(output_root, run_id, metrics=metrics, parameters=parameters, meta={"strategy": "shock_reversion_intraday"})
        (output_root / run_id / "diagnostics_summary.json").write_text(json.dumps(diagnostics), encoding="utf-8")
        stop_loss_count = 2 if run_id == "run_004" else 1
        total_trades = int(diagnostics["executed_trades"])
        for trade_index in range(total_trades):
            trade_rows.append(
                {
                    "run_id": run_id,
                    "symbol": "600519.SH",
                    "entry_datetime": f"2024-01-01 09:{trade_index:02d}:00",
                    "exit_datetime": f"2024-01-01 10:{trade_index:02d}:00",
                    "entry_price": 100.0,
                    "exit_price": 101.0,
                    "holding_bars": 3,
                    "trade_return": diagnostics["avg_return_per_trade"],
                                        "mfe": diagnostics["avg_mfe"],
                    "mae": diagnostics["avg_mae"],
                                                            "etd": diagnostics["avg_etd"],
                                                            "mfe_price": 102.0,
                    "mae_price": 99.0,
                    "anchor_price_at_entry": 100.0,
                    "excursion_at_entry": -0.02,
                    "recovery_target": 101.5,
                    "take_profit_price": 102.0,
                    "effective_target_price": 101.8,
                    "bars_to_mfe": 2,
                    "bars_to_mae": 1,
                    "exit_reason": "stop_loss" if trade_index < stop_loss_count else "recovery",
                    "exit_subtype": "stop_loss" if trade_index < stop_loss_count else "recovery",
                }
            )
    pd.DataFrame(trade_rows).to_csv(output_root / "trades.csv", index=False)

    build_summary("shock_selection")

    ranked_df = pd.read_csv(output_root / "selection_ranked.csv")
    report_df = pd.read_csv(output_root / "selection_report.csv")
    top_config = json.loads((output_root / "top_config.json").read_text(encoding="utf-8"))

    assert len(ranked_df.index) == 5
    assert set(ranked_df["run_id"]) == {"run_001", "run_002", "run_003", "run_004", "run_005"}
    assert report_df.loc[report_df["run_id"] == "run_006", "rejection_reason"].item() == "hard:executed_trades<10"
    assert report_df.loc[report_df["run_id"] == "run_004", "selected"].item()
    assert "return" not in report_df.columns
    assert "total_return" in report_df.columns
    assert "avg_return_per_trade" in report_df.columns
    assert "return_alignment_warning" in report_df.columns
    assert not report_df["return_sign_mismatch"].any()
    assert top_config["run_id"] == "run_002"
    assert "total_return" in top_config
    assert "avg_return_per_trade" in top_config
    assert top_config["params"]["excursion_threshold"] == 0.012

def test_build_summary_writes_run_performance_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "shock_run_report"
    output_root.mkdir(parents=True, exist_ok=True)

    runs = [
        (
            "run_001",
            {"trade_unit": 500, "use_margin": True, "margin_rate_annual": 0.0835, "bars_per_day": 8, "excursion_lookback_bars": 3, "excursion_threshold": 0.01, "recovery_frac": 0.4, "take_profit_pct": 0.02, "max_hold_bars": 12, "stop_loss_pct": 0.01, "use_shock_score_filter": True, "shock_score_min": 60, "shock_score_max": 80},
            {"final_value": 100624.56337900016, "total_return": 0.99, "total_return_log": 0.006226210650540601, "sharpe": 1.1, "max_drawdown": 0.05, "num_trades": 36, "total_margin_interest_paid": 12.5},
            {"strategy": "shock_reversion_intraday", "symbol": "600519.SH", "date_range": {"start": "2024-01-01", "end": "2024-01-20"}, "initial_cash": 100000.0},
            {"entry_signals": 40, "executed_trades": 36, "blocked_by_multiple": 5, "avg_return_per_trade": 0.0035608091836527733, "avg_mfe": 0.025, "avg_mae": -0.005, "avg_etd": 0.0025},
            [
                {
                    "run_id": "run_001",
                    "symbol": "600519.SH",
                    "position_size": 500,
                    "entry_price": 100.0,
                    "avg_entry_price": 100.0,
                    "exit_price": 100.35608091836528,
                    "holding_period": 3,
                    "trade_return": 0.0035608091836527733,
                    "mfe": 0.025,
                    "mae": -0.005,
                    "etd": 0.0025,
                    "anchor_price_at_entry": 100.0,
                    "effective_anchor_price": 100.0,
                    "leg_count": 1,
                    "exit_reason": "recovery",
                    "shock_score_at_entry": 70.0,
                    "trade_pnl_amount": 178.04045918263888,
                }
                for _ in range(36)
            ],
        ),
        (
            "run_002",
            {"trade_unit": 100, "use_margin": False, "margin_rate_annual": 0.0835, "bars_per_day": 8, "excursion_lookback_bars": 4, "excursion_threshold": 0.012, "recovery_frac": 0.45, "take_profit_pct": 0.025, "max_hold_bars": 10, "stop_loss_pct": 0.012, "use_shock_score_filter": False},
            {"final_value": 95000.0, "total_return": -0.50, "total_return_log": -0.05129329438755058, "sharpe": 0.6, "max_drawdown": 0.08, "num_trades": 1, "total_margin_interest_paid": 0.0},
            {"strategy": "shock_reversion_intraday", "symbol": "000858.SZ", "date_range": {"start": "2024-02-01", "end": "2024-02-20"}, "initial_cash": 100000.0},
            {"entry_signals": 3, "executed_trades": 1, "blocked_by_multiple": 0, "avg_return_per_trade": 0.0, "avg_mfe": 0.025510204081632654, "avg_mae": -0.00510204081632653, "avg_etd": 0.02040816326530612},
            [
                {
                    "run_id": "run_002",
                    "symbol": "000858.SZ",
                    "position_size": 300,
                    "entry_price": 100.0,
                    "avg_entry_price": 98.0,
                    "exit_price": 98.0,
                    "holding_period": 3,
                    "trade_return": 0.0,
                    "mfe": 0.025510204081632654,
                    "mae": -0.00510204081632653,
                    "etd": 0.02040816326530612,
                    "anchor_price_at_entry": 100.0,
                    "effective_anchor_price": 102.0,
                    "leg_count": 3,
                    "exit_reason": "max_hold",
                    "shock_score_at_entry": 35.0,
                    "trade_pnl_amount": 0.0,
                },
            ],
        ),
    ]

    trade_rows: list[dict[str, object]] = []
    for run_id, parameters, metrics, meta, diagnostics, trades in runs:
        _write_run(output_root, run_id, metrics=metrics, parameters=parameters, meta=meta)
        (output_root / run_id / "diagnostics_summary.json").write_text(json.dumps(diagnostics), encoding="utf-8")
        trade_rows.extend(trades)
    pd.DataFrame(trade_rows).to_csv(output_root / "trades.csv", index=False)

    build_summary("shock_run_report")

    report_df = pd.read_csv(output_root / "run_performance_report.csv")

    assert list(report_df["run_id"]) == ["run_001", "run_002"]
    assert "selection_report.csv" not in report_df.columns

    first = report_df.loc[report_df["run_id"] == "run_001"].iloc[0]
    assert first["symbol"] == "600519.SH"
    assert first["start_date"] == "2024-01-01"
    assert first["end_date"] == "2024-01-20"
    assert first["initial_cash"] == 100000.0
    assert first["trade_unit"] == 500
    assert first["use_margin"]
    assert first["margin_rate_annual"] == pytest.approx(0.0835)
    assert first["total_margin_interest_paid"] == pytest.approx(12.5)
    assert first["total_return"] == pytest.approx(0.006245633790001739)
    assert first["total_return_simple"] == pytest.approx(0.006245633790001739)
    assert first["total_return_log"] == pytest.approx(0.006226210650540601)
    assert first["sum_trade_return"] == pytest.approx(0.12818913061149985)
    assert first["compound_trade_return"] > first["sum_trade_return"]
    assert first["capital_efficiency"] == pytest.approx(0.006245633790001739 / 0.12818913061149985)
    assert first["avg_return_per_trade"] == pytest.approx(0.0035608091836527733)
    assert first["avg_legs_per_trade"] == pytest.approx(1.0)
    assert first["multi_leg_trade_share"] == pytest.approx(0.0)
    assert first["total_trade_pnl_amount"] == pytest.approx(6409.456530575)
    assert first["executed_trades"] == 36
    assert first["entry_signals"] == 40
    assert first["blocked_by_multiple"] == 5
    assert first["stop_loss_share"] == 0.0
    assert first["recovery_share"] == 1.0
    assert first["take_profit_share"] == 0.0
    assert first["max_hold_share"] == 0.0
    assert first["avg_holding_bars"] == 3.0
    assert first["avg_shock_score"] == 70.0
    assert first["pnl_capture_ratio"] == pytest.approx(0.14243236734611094)
    assert first["shock_score_min"] == 60
    assert first["shock_score_max"] == 80
    assert first["use_shock_score_filter"]
    assert first["sum_trade_return"] > first["total_return_simple"]

    second = report_df.loc[report_df["run_id"] == "run_002"].iloc[0]
    assert second["trade_unit"] == 100
    assert second["use_margin"] in {False, 0}
    assert second["margin_rate_annual"] == pytest.approx(0.0835)
    assert second["total_return"] == pytest.approx(-0.05)
    assert second["total_return_simple"] == pytest.approx(-0.05)
    assert second["total_return_log"] == pytest.approx(-0.05129329438755058)
    assert second["sum_trade_return"] == pytest.approx(0.0)
    assert second["capital_efficiency"] == pytest.approx(0.0)
    assert second["avg_legs_per_trade"] == pytest.approx(3.0)
    assert second["multi_leg_trade_share"] == pytest.approx(1.0)
    assert second["avg_etd"] == pytest.approx(0.02040816326530612)
    assert second["total_trade_pnl_amount"] == pytest.approx(0.0)
    assert second["max_hold_share"] == 1.0
    assert second["use_shock_score_filter"] in {False, 0}

def test_build_summary_marks_return_sign_mismatch_in_selection_report(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "shock_selection_mismatch"
    output_root.mkdir(parents=True, exist_ok=True)

    _write_run(
        output_root,
        "run_001",
        metrics={"sharpe": 1.1, "total_return": 0.08, "max_drawdown": 0.05, "num_trades": 12},
        parameters={"excursion_lookback_bars": 3, "excursion_threshold": 0.01},
        meta={"strategy": "shock_reversion_intraday"},
    )
    (output_root / "run_001" / "diagnostics_summary.json").write_text(
        json.dumps({"executed_trades": 12, "avg_return_per_trade": -0.015, "avg_mfe": 0.04, "avg_mae": -0.008, "avg_etd": 0.008}),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "run_id": "run_001",
                "exit_reason": "recovery",
            }
        ]
    ).to_csv(output_root / "trades.csv", index=False)

    build_summary("shock_selection_mismatch")

    report_df = pd.read_csv(output_root / "selection_report.csv")
    mismatch_row = report_df.loc[report_df["run_id"] == "run_001"].iloc[0]

    assert mismatch_row["total_return"] == 0.08
    assert mismatch_row["avg_return_per_trade"] == -0.015
    assert mismatch_row["return_sign_mismatch"]
    assert mismatch_row["return_alignment_warning"] == "sign_mismatch"

def test_build_summary_writes_selection_report_v2_with_expected_order(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "shock_selection_v2"
    output_root.mkdir(parents=True, exist_ok=True)

    run_specs = [
        ("run_001", 0.02, 5, 0.005, 0.10, 0.004, -0.003, 0.12, 0.0080),
        ("run_002", 0.03, 12, -0.002, 0.10, 0.004, -0.003, 0.15, 0.0080),
        ("run_003", 0.04, 12, 0.003, 0.35, 0.004, -0.003, 0.18, 0.0080),
        ("run_008", 0.09, 15, 0.011, 0.10, 0.021, -0.008, 0.14, 0.0070),
        ("run_009", 0.11, 18, 0.013, 0.09, 0.022, -0.007, 0.15, 0.0050),
        ("run_010", 0.10, 16, 0.012, 0.11, 0.020, -0.009, 0.155, 0.0055),
        ("run_011", 0.12, 20, 0.014, 0.08, 0.024, -0.008, 0.16, 0.0045),
        ("run_012", 0.13, 22, 0.016, 0.07, 0.025, -0.009, 0.165, 0.0040),
    ]

    trade_rows: list[dict[str, object]] = []
    for run_id, total_return, executed_trades, avg_return_per_trade, max_drawdown, avg_mfe, avg_mae, trade_sum, avg_etd in run_specs:
        parameters = {"excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.02, "recovery_frac": 0.4, "max_hold_bars": 10, "stop_loss_pct": 0.01}
        metrics = {"sharpe": 1.0, "total_return": total_return, "max_drawdown": max_drawdown, "num_trades": executed_trades}
        diagnostics = {"executed_trades": executed_trades, "avg_return_per_trade": avg_return_per_trade, "avg_mfe": avg_mfe, "avg_mae": avg_mae, "avg_etd": avg_etd}
        _write_run(output_root, run_id, metrics=metrics, parameters=parameters, meta={"strategy": "shock_reversion_intraday", "initial_cash": 100000.0})
        (output_root / run_id / "diagnostics_summary.json").write_text(json.dumps(diagnostics), encoding="utf-8")
        per_trade_pnl = trade_sum / max(executed_trades, 1)
        for trade_index in range(executed_trades):
            trade_rows.append(
                {
                    "run_id": run_id,
                    "symbol": "600519.SH",
                    "entry_datetime": f"2024-01-01 09:{trade_index % 60:02d}:00",
                    "exit_datetime": f"2024-01-01 10:{trade_index % 60:02d}:00",
                    "entry_price": 100.0,
                    "exit_price": 101.0,
                    "holding_bars": 3,
                    "trade_return": per_trade_pnl,
                                        "mfe": avg_mfe,
                    "mae": avg_mae,
                                                            "etd": avg_etd,
                                                            "mfe_price": 102.0,
                    "mae_price": 99.0,
                    "anchor_price_at_entry": 100.0,
                    "excursion_at_entry": -0.02,
                    "recovery_target": 101.5,
                    "take_profit_price": 102.0,
                    "effective_target_price": 101.8,
                    "bars_to_mfe": 2,
                    "bars_to_mae": 1,
                    "exit_reason": "recovery",
                    "exit_subtype": "recovery",
                }
            )
    pd.DataFrame(trade_rows).to_csv(output_root / "trades.csv", index=False)

    build_summary("shock_selection_v2")

    report_df = pd.read_csv(output_root / "selection_report_v2.csv")

    assert list(report_df["run_id"]) == ["run_012", "run_011", "run_009", "run_010", "run_008"]
    assert list(report_df["rank"]) == [1, 2, 3, 4, 5]
    assert set(["capital_efficiency", "ladder_ready", "norm_return", "norm_efficiency", "norm_etd", "norm_trades"]).issubset(report_df.columns)
    assert report_df.loc[report_df["run_id"] == "run_012", "ladder_ready"].item()
    assert pytest.approx(report_df.loc[report_df["run_id"] == "run_012", "capital_efficiency"].item(), rel=1e-6) == 0.13 / 0.165
    assert "run_001" not in set(report_df["run_id"])
    assert "run_002" not in set(report_df["run_id"])
    assert "run_003" not in set(report_df["run_id"])

def test_build_summary_selection_report_v2_keeps_positive_return_runs_with_percent_drawdown(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "shock_selection_v2_percent_drawdown"
    output_root.mkdir(parents=True, exist_ok=True)

    run_specs = [
        ("run_001", 0.08, 9, -0.005, 12.0, 0.020, -0.008, 0.12, 0.0070),
        ("run_002", -0.03, 16, -0.004, 11.0, 0.018, -0.007, -0.04, 0.0065),
        ("run_003", 0.07, 14, -0.002, 31.0, 0.021, -0.009, 0.10, 0.0075),
        ("run_009", 0.11, 18, -0.003, 14.0, 0.022, -0.007, 0.15, 0.0050),
        ("run_010", 0.10, 16, -0.001, 15.0, 0.020, -0.009, 0.155, 0.0055),
        ("run_011", 0.12, 20, -0.002, 13.0, 0.024, -0.008, 0.16, 0.0045),
        ("run_012", 0.13, 22, -0.004, 12.0, 0.025, -0.009, 0.165, 0.0040),
    ]

    trade_rows: list[dict[str, object]] = []
    for run_id, total_return, executed_trades, avg_return_per_trade, max_drawdown, avg_mfe, avg_mae, trade_sum, avg_etd in run_specs:
        parameters = {"excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.02, "recovery_frac": 0.4, "max_hold_bars": 10, "stop_loss_pct": 0.01}
        metrics = {"sharpe": 1.0, "total_return": total_return, "max_drawdown": max_drawdown, "num_trades": executed_trades}
        diagnostics = {"executed_trades": executed_trades, "avg_return_per_trade": avg_return_per_trade, "avg_mfe": avg_mfe, "avg_mae": avg_mae, "avg_etd": avg_etd}
        _write_run(output_root, run_id, metrics=metrics, parameters=parameters, meta={"strategy": "shock_reversion_intraday", "initial_cash": 100000.0})
        (output_root / run_id / "diagnostics_summary.json").write_text(json.dumps(diagnostics), encoding="utf-8")
        per_trade_pnl = trade_sum / max(executed_trades, 1)
        for trade_index in range(executed_trades):
            trade_rows.append(
                {
                    "run_id": run_id,
                    "symbol": "600519.SH",
                    "entry_datetime": f"2024-01-01 09:{trade_index % 60:02d}:00",
                    "exit_datetime": f"2024-01-01 10:{trade_index % 60:02d}:00",
                    "entry_price": 100.0,
                    "exit_price": 101.0,
                    "holding_bars": 3,
                    "trade_return": per_trade_pnl,
                                        "mfe": avg_mfe,
                    "mae": avg_mae,
                                                            "etd": avg_etd,
                                                            "mfe_price": 102.0,
                    "mae_price": 99.0,
                    "anchor_price_at_entry": 100.0,
                    "excursion_at_entry": -0.02,
                    "recovery_target": 101.5,
                    "take_profit_price": 102.0,
                    "effective_target_price": 101.8,
                    "bars_to_mfe": 2,
                    "bars_to_mae": 1,
                    "exit_reason": "recovery",
                    "exit_subtype": "recovery",
                }
            )
    pd.DataFrame(trade_rows).to_csv(output_root / "trades.csv", index=False)

    build_summary("shock_selection_v2_percent_drawdown")

    report_df = pd.read_csv(output_root / "selection_report_v2.csv")
    captured = capsys.readouterr().out

    assert len(report_df.index) >= 3
    assert not report_df.empty
    assert set(["run_009", "run_010", "run_011", "run_012"]).issubset(set(report_df["run_id"]))
    assert "[selection_v2] initial rows: 7" in captured
    assert "[selection_v2] after executed_trades filter: 6" in captured


def test_build_summary_selection_report_v2_deduplicates_identical_runs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    output_root = tmp_path / "outputs" / "shock_selection_v2_dedup"
    output_root.mkdir(parents=True, exist_ok=True)

    run_specs = [
        ("run_003", 0.11, 18, 0.013, 0.09, 0.022, -0.007, 0.15, 0.0050),
        ("run_004", 0.11, 18, 0.013, 0.09, 0.022, -0.007, 0.15, 0.0050),
        ("run_011", 0.12, 20, 0.014, 0.08, 0.024, -0.008, 0.16, 0.0045),
        ("run_012", 0.13, 22, 0.016, 0.07, 0.025, -0.009, 0.165, 0.0040),
    ]

    trade_rows: list[dict[str, object]] = []
    for run_id, total_return, executed_trades, avg_return_per_trade, max_drawdown, avg_mfe, avg_mae, trade_sum, avg_etd in run_specs:
        parameters = {"excursion_lookback_bars": 3, "excursion_threshold": 0.01, "take_profit_pct": 0.02, "recovery_frac": 0.4, "max_hold_bars": 10, "stop_loss_pct": 0.01}
        metrics = {"sharpe": 1.0, "total_return": total_return, "max_drawdown": max_drawdown, "num_trades": executed_trades}
        diagnostics = {"executed_trades": executed_trades, "avg_return_per_trade": avg_return_per_trade, "avg_mfe": avg_mfe, "avg_mae": avg_mae, "avg_etd": avg_etd}
        _write_run(output_root, run_id, metrics=metrics, parameters=parameters, meta={"strategy": "shock_reversion_intraday", "initial_cash": 100000.0})
        (output_root / run_id / "diagnostics_summary.json").write_text(json.dumps(diagnostics), encoding="utf-8")
        per_trade_pnl = trade_sum / max(executed_trades, 1)
        for trade_index in range(executed_trades):
            trade_rows.append(
                {
                    "run_id": run_id,
                    "symbol": "600519.SH",
                    "entry_datetime": f"2024-01-01 09:{trade_index % 60:02d}:00",
                    "exit_datetime": f"2024-01-01 10:{trade_index % 60:02d}:00",
                    "entry_price": 100.0,
                    "exit_price": 101.0,
                    "holding_bars": 3,
                    "trade_return": per_trade_pnl,
                    "mfe": avg_mfe,
                    "mae": avg_mae,
                    "etd": avg_etd,
                    "mfe_price": 102.0,
                    "mae_price": 99.0,
                    "anchor_price_at_entry": 100.0,
                    "excursion_at_entry": -0.02,
                    "recovery_target": 101.5,
                    "take_profit_price": 102.0,
                    "effective_target_price": 101.8,
                    "bars_to_mfe": 2,
                    "bars_to_mae": 1,
                    "exit_reason": "recovery",
                    "exit_subtype": "recovery",
                }
            )
    pd.DataFrame(trade_rows).to_csv(output_root / "trades.csv", index=False)

    build_summary("shock_selection_v2_dedup")

    report_df = pd.read_csv(output_root / "selection_report_v2.csv")

    assert "run_003" in set(report_df["run_id"]) or "run_004" in set(report_df["run_id"])
    assert not ({"run_003", "run_004"} <= set(report_df["run_id"]))
    signatures = {
        (
            round(float(row["total_return_simple"]), 6),
            round(float(row["sum_trade_return"]), 6),
            round(float(row["avg_return_per_trade"]), 6),
            round(float(row["avg_mfe"]), 6),
            round(float(row["avg_mae"]), 6),
            round(float(row["avg_etd"]), 6),
            int(row["executed_trades"]),
        )
        for _, row in report_df.iterrows()
    }
    assert len(signatures) == len(report_df.index)
