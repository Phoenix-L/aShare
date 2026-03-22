from pathlib import Path
import json

import pandas as pd
import pytest

from ashare.config.settings import BacktestConfig
from ashare.experiment.grid import expand_grid, generate_parameter_sets
from ashare.experiment.executor import execute_experiment_spec, prepare_output_dir
from ashare.research.experiment_runner import generate_param_combinations
from ashare.strategies.mid_freq_ma import MidFreqMA
from ashare.strategies.shock_reversion_intraday import ShockReversionIntradayStrategy


def _synthetic_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=60, freq="30min")
    close = [10 + (i * 0.05) for i in range(60)]
    return pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.1 for c in close],
            "low": [c - 0.1 for c in close],
            "close": close,
            "volume": [1000] * 60,
            "turnover_rate": [2.0] * 60,
        },
        index=idx,
    )


def test_generate_param_combinations_expands_cross_product() -> None:
    param_grid = {
        "short_period": [5, 10, 15],
        "long_period": [20, 30],
    }

    combos = generate_param_combinations(param_grid)

    assert len(combos) == 6
    assert {"short_period": 5, "long_period": 20} in combos
    assert {"short_period": 15, "long_period": 30} in combos


def test_run_experiment_creates_outputs_and_metrics(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

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
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id, output_dir)
        return None, None, {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    experiment_name = "test_experiment"
    result = execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={
            "name": experiment_name,
            "strategy": "mid_freq_ma",
            "symbols": ["600519.SH", "000858.SZ"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {},
            "grid": {"short_period": [3, 5], "long_period": [8], "turnover_thresh": [1.0]},
        },
        config=BacktestConfig(),
    )

    experiment_dir = Path(result["output_dir"])
    results_path = Path(result["summary_path"])
    results_sorted_path = Path(result["summary_sorted_path"])
    run_report_path = Path(result["run_performance_report_path"])

    assert experiment_dir.exists()
    assert results_path.exists()
    assert results_sorted_path.exists()
    assert run_report_path.exists()

    results_df = pd.read_csv(results_path)
    assert len(results_df) == 4
    assert list(results_df.columns) == [
        "initial_cash",
        "total_return",
        "total_return_simple",
        "total_return_log",
        "sharpe",
        "max_drawdown",
        "num_trades",
    ]

    assert results_df["total_return"].notna().all()
    assert results_df["max_drawdown"].notna().all()

    run_payload = json.loads((experiment_dir / "run_001" / "run_result.json").read_text(encoding="utf-8"))
    assert set(run_payload.keys()) == {"params", "metrics", "meta"}
    assert run_payload["meta"]["initial_cash"] == BacktestConfig().initial_cash


def test_execute_experiment_spec_applies_yaml_execution_initial_cash(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    captured_configs: list[BacktestConfig] = []

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
        _ = (strategy_cls, data_df, strategy_params, symbol, experiment_name, run_id, output_dir)
        captured_configs.append(config)
        return None, None, {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    result = execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={
            "name": "execution_initial_cash",
            "strategy": "mid_freq_ma",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {},
            "grid": {"short_period": [3], "long_period": [8], "turnover_thresh": [1.0]},
            "execution": {"initial_cash": 250000},
        },
        config=BacktestConfig(initial_cash=100000),
    )

    assert captured_configs[0].initial_cash == 250000.0
    run_payload = json.loads((Path(result["output_dir"]) / "run_001" / "run_result.json").read_text(encoding="utf-8"))
    assert run_payload["meta"]["initial_cash"] == 250000.0


def test_prepare_output_dir_cleans_existing_contents_but_keeps_parent(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs" / "cleanup_case"
    (output_root / "run_001").mkdir(parents=True)
    (output_root / "run_001" / "metrics.json").write_text("{}", encoding="utf-8")
    (output_root / "summary.csv").write_text("stale", encoding="utf-8")

    prepared = prepare_output_dir(output_root)

    assert prepared == output_root
    assert output_root.exists()
    assert list(output_root.iterdir()) == []


def test_execute_experiment_overwrites_existing_output_directory_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

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
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id, output_dir)
        return None, None, {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    experiment_name = "cleanup_overwrite"
    base_spec = {
        "name": experiment_name,
        "strategy": "mid_freq_ma",
        "symbols": ["600519.SH"],
        "start": "2024-01-01",
        "end": "2024-01-20",
        "parameters": {},
        "execution": {},
    }

    execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={**base_spec, "grid": {"short_period": [3, 5, 7, 9], "long_period": [8, 10, 12, 14, 16, 18, 20, 22]}},
        config=BacktestConfig(),
    )

    output_root = tmp_path / "outputs" / experiment_name
    assert (output_root / "run_032").exists()

    execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={**base_spec, "grid": {"short_period": [3, 5, 7], "long_period": [8, 10, 12, 14, 16, 18, 20, 22]}},
        config=BacktestConfig(),
    )

    run_dirs = sorted(path.name for path in output_root.iterdir() if path.is_dir() and path.name.startswith("run_"))
    report_df = pd.read_csv(output_root / "run_performance_report.csv")

    assert len(run_dirs) == 24
    assert run_dirs[0] == "run_001"
    assert run_dirs[-1] == "run_024"
    assert not (output_root / "run_025").exists()
    assert len(report_df.index) == 24


def test_execute_experiment_can_preserve_existing_outputs_when_clean_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

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
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id, output_dir)
        return None, None, {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    experiment_name = "cleanup_disabled"
    output_root = tmp_path / "outputs" / experiment_name
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "stale.txt").write_text("keep me", encoding="utf-8")

    execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={
            "name": experiment_name,
            "strategy": "mid_freq_ma",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {},
            "grid": {"short_period": [3], "long_period": [8], "turnover_thresh": [1.0]},
            "execution": {},
        },
        config=BacktestConfig(),
        clean_output=False,
    )

    assert (output_root / "stale.txt").exists()


def test_execute_experiment_does_not_print_grid_diagnostics_when_not_deduplicated(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    def _fake_backtest(strategy_cls, data_df, config, strategy_params=None, symbol=None, experiment_name=None, run_id=None, output_dir=None):
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id, output_dir)
        return None, None, {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={
            "name": "no_dedup_report",
            "strategy": "mid_freq_ma",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {},
            "grid": {"short_period": [3, 5], "long_period": [8]},
        },
        config=BacktestConfig(),
    )

    output = capsys.readouterr().out
    assert "Original grid size:" not in output
    assert "Deduplicated runs:" not in output


def test_execute_experiment_prints_grid_diagnostics_when_deduplicated(monkeypatch, tmp_path: Path, capsys) -> None:

    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    def _fake_backtest(strategy_cls, data_df, config, strategy_params=None, symbol=None, experiment_name=None, run_id=None, output_dir=None):
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id, output_dir)
        return None, None, {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="mid_freq_ma",
        spec={
            "name": "dedup_report",
            "strategy": "mid_freq_ma",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {},
            "grid": {"short_period": [3, 3], "long_period": [8]},
        },
        config=BacktestConfig(),
    )

    output = capsys.readouterr().out
    assert "Original grid size: 2" in output
    assert "Deduplicated runs: 1" in output


def test_generate_parameter_sets_keeps_shock_ladder_grid_dimensions() -> None:
    payload = {
        "strategy": "shock_reversion_intraday",
        "parameters": {
            "trade_unit": 500,
            "enable_ladder_simulation": False,
            "max_legs": 1,
            "ladder_min_drop_pct": 0.02,
            "ladder_min_bars_between_legs": 1,
            "ladder_score_min_add": 0,
        },
        "grid": {
            "enable_ladder_simulation": [False, True],
            "max_legs": [1, 3],
        },
    }

    all_combinations = expand_grid(payload["grid"])
    final_runs = generate_parameter_sets(payload)

    assert len(all_combinations) == 4
    assert len(final_runs) == 4
    assert {tuple(sorted(run.items())) for run in final_runs} == {
        tuple(
            sorted(
                {
                    "trade_unit": 500,
                    "enable_ladder_simulation": enable_ladder_simulation,
                    "max_legs": max_legs,
                    "ladder_min_drop_pct": 0.02,
                    "ladder_min_bars_between_legs": 1,
                    "ladder_score_min_add": 0,
                }.items()
            )
        )
        for enable_ladder_simulation in [False, True]
        for max_legs in [1, 3]
    }


def test_execute_experiment_spec_runs_all_shock_ladder_grid_combinations(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    captured_params: list[dict] = []

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
        _ = (strategy_cls, data_df, config, symbol, experiment_name, run_id, output_dir)
        captured_params.append(dict(strategy_params or {}))
        return None, type("Strat", (), {"completed_trades": [], "signal_events": []})(), {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 1}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    result = execute_experiment_spec(
        strategy_cls=ShockReversionIntradayStrategy,
        strategy_name="shock_reversion_intraday",
        spec={
            "name": "shock_ladder_grid",
            "strategy": "shock_reversion_intraday",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {
                "trade_unit": 500,
                "excursion_lookback_bars": 3,
                "excursion_threshold": 0.01,
                "recovery_frac": 0.5,
                "take_profit_pct": 0.02,
                "max_hold_bars": 10,
                "stop_loss_pct": 0.1,
                "enable_ladder_simulation": False,
                "max_legs": 1,
                "ladder_min_drop_pct": 0.02,
                "ladder_min_bars_between_legs": 1,
                "ladder_score_min_add": 0,
            },
            "grid": {
                "enable_ladder_simulation": [False, True],
                "max_legs": [1, 3],
            },
        },
        config=BacktestConfig(),
    )

    output = capsys.readouterr().out

    assert result["num_runs"] == 4
    assert len(captured_params) == 4
    assert {tuple((params["enable_ladder_simulation"], params["max_legs"])) for params in captured_params} == {
        (False, 1),
        (False, 3),
        (True, 1),
        (True, 3),
    }
    assert "Original grid size" not in output
    assert "Deduplicated runs" not in output


def test_execute_experiment_spec_raises_clear_missing_parameter_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.generate_parameter_sets", lambda payload: [{"short_period": 3}])

    with pytest.raises(ValueError, match="Missing parameter: long_period"):
        execute_experiment_spec(
            strategy_cls=MidFreqMA,
            strategy_name="mid_freq_ma",
            spec={
                "name": "missing_param_guard",
                "strategy": "mid_freq_ma",
                "symbols": ["600519.SH"],
                "start": "2024-01-01",
                "end": "2024-01-20",
                "parameters": {},
                "grid": {"short_period": [3], "long_period": [8]},
            },
            config=BacktestConfig(),
        )


class _ShockBacktestStrategy:
    completed_trades = [
        {
            "symbol": "600519.SH",
            "entry_datetime": "2024-01-01T10:00:00",
            "exit_datetime": "2024-01-01T11:00:00",
            "entry_price": 100.0,
            "exit_price": 101.0,
            "holding_bars": 2,
            "trade_return": 0.01,
            "mfe": 0.02,
            "mae": -0.005,
            "etd": 0.3,
            "mfe_price": 102.0,
            "mae_price": 99.5,
            "anchor_price_at_entry": 103.0,
            "excursion_at_entry": -0.03,
            "shock_score_at_entry": 72.0,
            "recovery_target": 101.5,
            "take_profit_price": 102.0,
            "effective_target_price": 101.5,
            "bars_to_mfe": 1,
            "bars_to_mae": 1,
            "exit_reason": "recovery",
            "exit_subtype": "recovery",
        },
        {
            "symbol": "600519.SH",
            "entry_datetime": "2024-01-02T10:00:00",
            "exit_datetime": "2024-01-02T11:00:00",
            "entry_price": 100.0,
            "exit_price": 98.0,
            "holding_bars": 2,
            "trade_return": -0.02,
            "mfe": 0.005,
            "mae": -0.025,
            "etd": 0.1,
            "mfe_price": 100.5,
            "mae_price": 97.5,
            "anchor_price_at_entry": 101.0,
            "excursion_at_entry": -0.01,
            "shock_score_at_entry": 35.0,
            "recovery_target": 100.5,
            "take_profit_price": 102.0,
            "effective_target_price": 100.5,
            "bars_to_mfe": 1,
            "bars_to_mae": 2,
            "exit_reason": "stop_loss",
            "exit_subtype": "stop_loss",
        },
    ]
    signal_events = [
        {
            "symbol": "600519.SH",
            "datetime": "2024-01-01T10:00:00",
            "excursion": -0.03,
            "depth_raw": 0.03,
            "depth_score": 1.0,
            "speed_ret": -0.02,
            "speed_score": 0.6667,
            "stabilization_score": 1.0,
            "noise_base": 0.004,
            "noise_ratio": 7.5,
            "noise_penalty": 0.0,
            "shock_score": 72.0,
            "threshold": 0.01,
            "shock_score_min": 60,
            "shock_score_max": 80,
            "shock_score_filter_enabled": True,
            "blocked_by_shock_score_low": False,
            "blocked_by_shock_score_high": False,
            "entry_executed": True,
        },
        {
            "symbol": "600519.SH",
            "datetime": "2024-01-02T10:00:00",
            "excursion": -0.01,
            "depth_raw": 0.01,
            "depth_score": 0.5,
            "speed_ret": -0.005,
            "speed_score": 0.1667,
            "stabilization_score": 0.0,
            "noise_base": 0.004,
            "noise_ratio": 2.5,
            "noise_penalty": 0.1667,
            "shock_score": 35.0,
            "threshold": 0.01,
            "shock_score_min": 60,
            "shock_score_max": 80,
            "shock_score_filter_enabled": True,
            "blocked_by_shock_score_low": True,
            "blocked_by_shock_score_high": False,
            "entry_executed": True,
        },
        {
            "symbol": "600519.SH",
            "datetime": "2024-01-03T10:00:00",
            "excursion": -0.005,
            "depth_raw": 0.005,
            "depth_score": 0.25,
            "speed_ret": -0.002,
            "speed_score": 0.0667,
            "stabilization_score": 0.0,
            "noise_base": 0.004,
            "noise_ratio": 1.25,
            "noise_penalty": 0.5833,
            "shock_score": 18.0,
            "threshold": 0.01,
            "shock_score_min": 60,
            "shock_score_max": 80,
            "shock_score_filter_enabled": True,
            "blocked_by_shock_score_low": True,
            "blocked_by_shock_score_high": False,
            "entry_executed": False,
        },
    ]


def test_execute_experiment_writes_shock_score_bucket_analysis(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    def _fake_backtest(strategy_cls, data_df, config, strategy_params=None, symbol=None, experiment_name=None, run_id=None, output_dir=None):
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id, output_dir)
        return None, _ShockBacktestStrategy(), {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 2}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    experiment_name = "shock_bucket_experiment"
    result = execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="shock_reversion_intraday",
        spec={
            "name": experiment_name,
            "strategy": "shock_reversion_intraday",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {"excursion_lookback_bars": 3, "excursion_threshold": 0.01, "recovery_frac": 0.5, "take_profit_pct": 0.02, "max_hold_bars": 8, "stop_loss_pct": 0.03},
            "grid": {},
        },
        config=BacktestConfig(),
    )

    bucket_path = Path(result["output_dir"]) / "shock_score_buckets.csv"
    bucket_df = pd.read_csv(bucket_path)

    assert bucket_path.exists()
    assert list(bucket_df["score_bucket"]) == ["0-20", "20-40", "40-60", "60-80", "80-100"]
    weak = bucket_df.loc[bucket_df["score_bucket"] == "20-40"].iloc[0]
    strong = bucket_df.loc[bucket_df["score_bucket"] == "60-80"].iloc[0]
    assert weak["executed_trades"] == 1
    assert weak["stop_loss_share"] == 1.0
    assert strong["executed_trades"] == 1
    assert strong["avg_return_per_trade"] == 0.01


def test_execute_experiment_writes_shock_score_overshock_analysis(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    class _OvershockBacktestStrategy(_ShockBacktestStrategy):
        completed_trades = _ShockBacktestStrategy.completed_trades + [
            {
                "symbol": "600519.SH",
                "entry_datetime": "2024-01-03T10:00:00",
                "exit_datetime": "2024-01-03T11:00:00",
                "entry_price": 100.0,
                "exit_price": 97.0,
                "holding_bars": 3,
                "trade_return": -0.03,
                "mfe": 0.002,
                "mae": -0.032,
                "etd": 0.4,
                "mfe_price": 100.2,
                "mae_price": 96.8,
                "anchor_price_at_entry": 105.0,
                "excursion_at_entry": -0.05,
                "shock_score_at_entry": 88.0,
                "recovery_target": 102.5,
                "take_profit_price": 102.0,
                "effective_target_price": 102.0,
                "bars_to_mfe": 1,
                "bars_to_mae": 3,
                "exit_reason": "stop_loss",
                "exit_subtype": "stop_loss",
            },
        ]
        signal_events = _ShockBacktestStrategy.signal_events + [
            {
                "symbol": "600519.SH",
                "datetime": "2024-01-04T10:00:00",
                "excursion": -0.05,
                "depth_raw": 0.05,
                "depth_score": 1.0,
                "speed_ret": -0.03,
                "speed_score": 1.0,
                "stabilization_score": 0.5,
                "noise_base": 0.004,
                "noise_ratio": 12.5,
                "noise_penalty": 0.0,
                "shock_score": 88.0,
                "threshold": 0.01,
                "shock_score_min": 60,
                "shock_score_max": 80,
                "shock_score_filter_enabled": True,
                "blocked_by_shock_score_low": False,
                "blocked_by_shock_score_high": True,
                "entry_executed": False,
            },
        ]

    def _fake_loader(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        _ = (ts_code, start_date, end_date)
        return _synthetic_df()

    def _fake_backtest(strategy_cls, data_df, config, strategy_params=None, symbol=None, experiment_name=None, run_id=None, output_dir=None):
        _ = (strategy_cls, data_df, config, strategy_params, symbol, experiment_name, run_id, output_dir)
        return None, _OvershockBacktestStrategy(), {"total_return": 0.01, "sharpe": 1.0, "max_drawdown": 0.1, "num_trades": 3}

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", _fake_loader)
    monkeypatch.setattr("ashare.experiment.executor.run_backtest", _fake_backtest)

    result = execute_experiment_spec(
        strategy_cls=MidFreqMA,
        strategy_name="shock_reversion_intraday",
        spec={
            "name": "shock_overshock_experiment",
            "strategy": "shock_reversion_intraday",
            "symbols": ["600519.SH"],
            "start": "2024-01-01",
            "end": "2024-01-20",
            "parameters": {"excursion_lookback_bars": 3, "excursion_threshold": 0.01, "recovery_frac": 0.5, "take_profit_pct": 0.02, "max_hold_bars": 8, "stop_loss_pct": 0.03, "use_shock_score_filter": True, "shock_score_min": 60, "shock_score_max": 80},
            "grid": {},
        },
        config=BacktestConfig(),
    )

    overshock_path = Path(result["output_dir"]) / "shock_score_overshock_analysis.csv"
    overshock_df = pd.read_csv(overshock_path)
    assert overshock_path.exists()
    assert list(overshock_df["bucket"]) == ["60-80", "80-100"]
    overshock = overshock_df.loc[overshock_df["bucket"] == "80-100"].iloc[0]
    assert overshock["executed_trades"] == 1
    assert overshock["stop_loss_share"] == 1.0
    assert overshock["return_diff_vs_60_80"] < 0.0
