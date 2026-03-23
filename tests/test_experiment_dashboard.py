from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml
from click.testing import CliRunner

from ashare.analysis.experiment_dashboard import build_experiment_dashboard
from ashare.cli import cli
from ashare.config.settings import BacktestConfig
from ashare.experiment.executor import execute_experiment_spec
from ashare.strategies.mid_freq_ma import MidFreqMA


def _write_run_payload(run_dir: Path, *, params: dict | None = None, meta: dict | None = None) -> None:
    params_payload = params or {}
    meta_payload = {"run_id": run_dir.name, **(meta or {})}
    (run_dir / "run_result.json").write_text(
        json.dumps({"params": params_payload, "metrics": {}, "meta": meta_payload}),
        encoding="utf-8",
    )
    (run_dir / "config_snapshot.yaml").write_text(
        yaml.safe_dump(
            {
                "parameters": params_payload,
                "symbol": meta_payload.get("symbol"),
                "date_range": meta_payload.get("date_range"),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_build_experiment_dashboard_writes_expected_csvs(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "experiment"
    experiment_dir.mkdir()
    run_001 = experiment_dir / "run_001"
    run_002 = experiment_dir / "run_002"
    run_003 = experiment_dir / "run_003"
    run_001.mkdir()
    run_002.mkdir()
    run_003.mkdir()

    _write_run_payload(
        run_001,
        params={"recovery_frac": 0.4, "add_score_min": 60, "max_legs": 3},
        meta={"symbol": "600519.SH", "date_range": {"start": "2024-01-01", "end": "2024-01-31"}},
    )
    _write_run_payload(
        run_002,
        params={"recovery_frac": 0.5, "add_score_min": 75, "max_legs": 1},
        meta={"symbol": "000858.SZ", "date_range": {"start": "2024-02-01", "end": "2024-02-29"}},
    )
    _write_run_payload(run_003, params={"recovery_frac": 0.7}, meta={"symbol": "300750.SZ"})

    pd.DataFrame(
        [
            {
                "run_id": "run_001",
                "symbol": "600519.SH",
                "entry_datetime": "2024-01-01 09:30:00",
                "exit_datetime": "2024-01-01 10:30:00",
                "trade_return": 0.03,
                "trade_pnl_amount": 300.0,
                "exit_reason": "recovery",
                "leg_count": 2,
                "entry_shock_score_at_entry": 65.0,
                "add_shock_score_at_entry": 82.0,
                "holding_period": 2,
            },
            {
                "run_id": "run_001",
                "symbol": "600519.SH",
                "entry_datetime": "2024-01-02 09:30:00",
                "exit_datetime": "2024-01-02 11:30:00",
                "trade_return": -0.01,
                "trade_pnl_amount": -120.0,
                "exit_reason": "stop_loss",
                "leg_count": 1,
                "entry_shock_score_at_entry": 28.0,
                "add_shock_score_at_entry": 15.0,
                "holding_period": 4,
            },
            {
                "run_id": "run_002",
                "symbol": "000858.SZ",
                "entry_datetime": "2024-02-01 09:30:00",
                "exit_datetime": "2024-02-01 10:00:00",
                "trade_return": 0.02,
                "trade_pnl_amount": 180.0,
                "exit_reason": "take_profit",
                "leg_count": 1,
                "entry_shock_score_at_entry": 92.0,
                "add_shock_score_at_entry": 55.0,
                "holding_period": 1,
            },
        ]
    ).to_csv(experiment_dir / "trades.csv", index=False)

    pd.DataFrame(
        [
            {"run_id": "run_001", "total_return": 0.08, "max_drawdown": 0.03, "avg_return_per_trade": 0.01, "executed_trades": 2},
            {"run_id": "run_002", "total_return": 0.05, "max_drawdown": 0.02, "avg_return_per_trade": 0.02, "executed_trades": 1},
            {"run_id": "run_003", "total_return": -0.01, "max_drawdown": 0.04, "avg_return_per_trade": 0.0, "executed_trades": 0},
        ]
    ).to_csv(experiment_dir / "run_performance_report.csv", index=False)

    outputs = build_experiment_dashboard(str(experiment_dir))

    dashboard_dir = experiment_dir / "dashboard"
    assert dashboard_dir.exists()
    assert set(Path(path).name for path in outputs.values()) == {
        "experiment_trades.csv",
        "exit_analysis.csv",
        "ladder_analysis.csv",
        "entry_score_analysis.csv",
        "add_score_analysis.csv",
        "config_analysis.csv",
        "recovery_diagnostic.csv",
    }

    experiment_trades = pd.read_csv(dashboard_dir / "experiment_trades.csv")
    assert list(experiment_trades.columns) == [
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
    assert len(experiment_trades.index) == 3
    assert experiment_trades.loc[experiment_trades["run_id"] == "run_001", "ladder_used"].tolist() == [True, False]

    exit_analysis = pd.read_csv(dashboard_dir / "exit_analysis.csv")
    assert set(exit_analysis["exit_reason"]) == {"recovery", "stop_loss", "take_profit"}
    recovery_row = exit_analysis.loc[exit_analysis["exit_reason"] == "recovery"].iloc[0]
    assert recovery_row["trade_count"] == 1
    assert recovery_row["avg_holding_period"] == 2.0

    ladder_analysis = pd.read_csv(dashboard_dir / "ladder_analysis.csv")
    assert set(ladder_analysis["ladder_used"].astype(str)) == {"True", "False"}

    entry_score_analysis = pd.read_csv(dashboard_dir / "entry_score_analysis.csv")
    assert list(entry_score_analysis["score_bucket"]) == ["0-30", "30-50", "50-70", "70-90", "90-100"]
    assert entry_score_analysis.loc[entry_score_analysis["score_bucket"] == "90-100", "trade_count"].item() == 1

    config_analysis = pd.read_csv(dashboard_dir / "config_analysis.csv")
    assert {"recovery_frac", "ladder_enabled", "add_score_min", "max_legs", "avg_total_return", "avg_drawdown", "avg_trade_return", "trade_count"}.issubset(config_analysis.columns)
    assert config_analysis["trade_count"].sum() == 3

    recovery_diagnostic = pd.read_csv(dashboard_dir / "recovery_diagnostic.csv")
    assert list(recovery_diagnostic["exit_reason"]) == ["recovery", "take_profit", "stop_loss"]
    assert recovery_diagnostic.loc[recovery_diagnostic["exit_reason"] == "recovery", "pct_exit_within_3_bars"].item() == 1.0


def test_execute_experiment_spec_and_dashboard_cli_generate_dashboard(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        idx = pd.date_range("2024-01-01", periods=6, freq="30min")
        return pd.DataFrame(
            {
                "open": [100, 99, 98, 99, 100, 101],
                "high": [101, 100, 99, 100, 101, 102],
                "low": [99, 98, 97, 98, 99, 100],
                "close": [100, 99, 98, 99, 100, 101],
                "volume": [1000] * 6,
                "turnover_rate": [2.0] * 6,
            },
            index=idx,
        )

    class _FakeStrategy:
        completed_trades = [
            {
                "symbol": "600519.SH",
                "entry_datetime": "2024-01-01 09:30:00",
                "exit_datetime": "2024-01-01 10:30:00",
                "position_size": 100,
                "entry_price": 100.0,
                "avg_entry_price": 100.0,
                "exit_price": 101.0,
                "holding_period": 2,
                "trade_return": 0.01,
                "mfe": 0.02,
                "mae": -0.01,
                "etd": 0.005,
                "mfe_price": 102.0,
                "mae_price": 99.0,
                "anchor_price_at_entry": 100.0,
                "effective_anchor_price": 100.0,
                "leg_count": 1,
                "excursion_at_entry": -0.02,
                "shock_score_at_entry": 72.0,
                "recovery_target": 101.0,
                "take_profit_price": 102.0,
                "effective_target_price": 101.0,
                "bars_to_mfe": 1,
                "bars_to_mae": 1,
                "exit_reason": "recovery",
                "exit_subtype": "recovery",
                "trade_pnl_amount": 100.0,
            }
        ]
        signal_events: list[dict] = []

    def _fake_backtest(
        strategy_cls,
        data_df,
        config,
        strategy_params=None,
        symbol=None,
        experiment_name=None,
        run_id=None,
        output_dir=None,
    ):
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id)
        (output_dir / "diagnostics.json").write_text("[]", encoding="utf-8")
        (output_dir / "diagnostics_summary.json").write_text(
            json.dumps({"entry_signals": 1, "executed_trades": 1, "avg_return_per_trade": 0.01}),
            encoding="utf-8",
        )
        return None, _FakeStrategy(), {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.02, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    result = execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={
            "name": "dashboard_auto",
            "strategy": "mid_freq_ma",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-10",
            "parameters": {"short_period": 3},
            "grid": {"long_period": [8]},
        },
        config=BacktestConfig(),
    )

    dashboard_dir = Path(result["dashboard_dir"])
    assert dashboard_dir.exists()
    assert (dashboard_dir / "experiment_trades.csv").exists()
    assert (dashboard_dir / "config_analysis.csv").exists()

    runner = CliRunner()
    cli_result = runner.invoke(cli, ["dashboard", "--experiment-path", result["output_dir"]])
    assert cli_result.exit_code == 0
    assert "Dashboard directory" in cli_result.output
