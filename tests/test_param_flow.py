from click.testing import CliRunner
import json
import pandas as pd
import yaml

from ashare.cli import cli
from ashare.config.settings import BacktestConfig

class _DummyStrategy:
    params = (
        ("z_entry", -1.0),
        ("z_exit", 0.2),
        ("use_art_filter", False),
    )

def _spec() -> dict:
    return {
        "name": "exp_param_flow",
        "strategy": "dummy",
        "symbols": ["002850.SZ"],
        "start": "2024-01-01",
        "end": "2024-12-31",
        "parameters": {"z_entry": -1.1, "use_art_filter": False},
        "grid": {"z_entry": [-1.2, -1.3], "z_exit": [0.3, 0.5]},
        "execution": {},
    }

def test_cli_param_and_date_overrides_have_highest_precedence(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig())
    monkeypatch.setattr("ashare.cli.get_strategy_class", lambda _: _DummyStrategy)
    monkeypatch.setattr("ashare.cli.load_experiment_spec", lambda _: _spec())

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", lambda *args, **kwargs: pd.DataFrame({
        "open": [1.0, 1.0, 1.0],
        "high": [1.0, 1.0, 1.0],
        "low": [1.0, 1.0, 1.0],
        "close": [1.0, 1.0, 1.0],
        "volume": [100, 100, 100],
    }, index=pd.date_range("2024-01-01", periods=3, freq="D")))

    monkeypatch.setattr(
        "ashare.experiment.executor.run_backtest",
        lambda *args, **kwargs: (None, None, {"final_value": 1.0, "rtot": 0.01, "max_drawdown": 1.0, "total_return": 0.01, "sharpe": 1.0}),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "experiment",
            "spec.yaml",
            "--param",
            "z_entry=-1.5",
            "--param",
            "use_art_filter=true",
            "--start",
            "2025-01-01",
            "--end",
            "2025-12-31",
        ],
    )

    assert result.exit_code == 0
    assert "Date range: 2025-01-01 → 2025-12-31 (CLI override)" in result.output

    run_dir = tmp_path / "outputs" / "exp_param_flow" / "run_001"
    snapshot = yaml.safe_load((run_dir / "config_snapshot.yaml").read_text())
    assert snapshot["parameters"]["z_entry"] == -1.5
    assert snapshot["parameters"]["z_exit"] == 0.3
    assert snapshot["parameters"]["use_art_filter"] is True

def test_executor_logs_running_parameters(monkeypatch, caplog, tmp_path) -> None:
    from ashare.experiment.executor import execute_experiment_spec

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", lambda *args, **kwargs: pd.DataFrame({
        "open": [1.0, 1.0, 1.0],
        "high": [1.0, 1.0, 1.0],
        "low": [1.0, 1.0, 1.0],
        "close": [1.0, 1.0, 1.0],
        "volume": [100, 100, 100],
    }, index=pd.date_range("2024-01-01", periods=3, freq="D")))

    monkeypatch.setattr(
        "ashare.experiment.executor.run_backtest",
        lambda *args, **kwargs: (None, None, {"final_value": 1.0, "rtot": 0.01, "max_drawdown": 1.0, "total_return": 0.01, "sharpe": 1.0}),
    )

    caplog.set_level("INFO", logger="ashare.experiment.executor")
    execute_experiment_spec(
        strategy_cls=_DummyStrategy,
        strategy_name="dummy",
        spec={
            "name": "exp_logging",
            "strategy": "dummy",
            "symbols": ["002850.SZ"],
            "start": "2024-01-01",
            "end": "2024-01-02",
            "parameters": {"use_art_filter": True},
            "grid": {"z_entry": [-1.5], "z_exit": [0.5]},
        },
        config=BacktestConfig(),
    )

    assert "Running: z_entry=-1.5, z_exit=0.5, use_art_filter=true" in caplog.text

def _shock_df() -> pd.DataFrame:
    closes = [100.0] * 180 + [97.0, 98.0, 99.0, 99.0] * 3
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000] * len(closes),
            "turnover_rate": [2.0] * len(closes),
        },
        index=pd.date_range("2024-01-01", periods=len(closes), freq="30min"),
    )

def test_cli_experiment_supports_shock_reversion_strategy_and_generates_trades(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0))
    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", lambda *args, **kwargs: _shock_df())

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "experiment",
            "--strategy",
            "shock_reversion_intraday",
            "--symbols",
            "600519.SH",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
            "--param",
            "excursion_lookback_bars=3,5",
            "--param",
            "excursion_threshold=0.01,0.02",
            "--param",
            "recovery_frac=0.5",
            "--param",
            "max_hold_bars=10",
            "--param",
            "stop_loss_pct=0.10",
        ],
    )

    assert result.exit_code == 0
    assert "Running experiment: shock_reversion_intraday_cli_experiment" in result.output
    assert "Total runs: 4" in result.output

    output_root = tmp_path / "outputs" / "shock_reversion_intraday_cli_experiment"
    run_payload = json.loads((output_root / "run_001" / "run_result.json").read_text(encoding="utf-8"))
    summary_text = (output_root / "summary.csv").read_text(encoding="utf-8")
    trades_text = (output_root / "trades.csv").read_text(encoding="utf-8")
    signals_text = (output_root / "signals.csv").read_text(encoding="utf-8")

    assert run_payload["meta"]["strategy"] == "shock_reversion_intraday"
    assert run_payload["params"]["excursion_lookback_bars"] == 3
    assert run_payload["params"]["excursion_threshold"] == 0.01
    assert run_payload["metrics"]["num_trades"] >= 1
    assert "excursion_lookback_bars" in summary_text
    assert "excursion_threshold" in summary_text
    assert "entry_datetime" in trades_text
    assert "anchor_price_at_entry" in trades_text
    assert "recovery_target" in trades_text
    assert "take_profit_price" in trades_text
    assert "effective_target_price" in trades_text
    assert "bars_to_mfe" in trades_text
    assert "mfe_pct" in trades_text
    assert "etd" in trades_text
    assert "exit_reason" in trades_text
    assert "recovery" in trades_text
    assert len(trades_text.strip().splitlines()) > 1
    assert "datetime" in signals_text
    assert "threshold" in signals_text
    assert "entry_executed" in signals_text
    assert len(signals_text.strip().splitlines()) > 1


class _ShockStrategy:
    params = (
        ("excursion_lookback_bars", 3),
        ("excursion_threshold", 0.01),
        ("recovery_frac", 0.5),
        ("take_profit_pct", 0.02),
        ("max_hold_bars", 8),
        ("stop_loss_pct", 0.05),
    )



def test_cli_shock_score_filter_requires_explicit_min(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0))
    monkeypatch.setattr("ashare.experiment.executor.load_minute_30", lambda *args, **kwargs: _shock_df())

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "experiment",
            "--strategy",
            "shock_reversion_intraday",
            "--symbols",
            "600519.SH",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
            "--param",
            "use_shock_score_filter=true",
        ],
    )

    assert result.exit_code != 0
    assert "requires an explicit shock_score_min" in result.output

def test_cli_ranking_output_is_strategy_aware_for_shock(monkeypatch) -> None:
    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig())
    monkeypatch.setattr("ashare.cli.get_strategy_class", lambda _: _ShockStrategy)
    monkeypatch.setattr(
        "ashare.cli.execute_experiment_spec",
        lambda **kwargs: {
            "num_runs": 1,
            "output_dir": "outputs/demo",
            "summary_path": "outputs/demo/summary.csv",
            "summary_sorted_path": "outputs/demo/summary_sorted.csv",
            "results": [
                {
                    "sharpe": 2.02,
                    "total_return": 0.1334,
                    "params": {
                        "excursion_lookback_bars": 5,
                        "excursion_threshold": 0.05,
                        "recovery_frac": 0.5,
                        "take_profit_pct": 0.05,
                        "max_hold_bars": 8,
                        "stop_loss_pct": 0.02,
                        "use_shock_score_filter": True,
                        "shock_score_min": 60,
                        "shock_score_max": 80,
                        "z_entry": None,
                        "z_exit": None,
                    },
                }
            ],
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "experiment",
            "--strategy",
            "shock_reversion_intraday",
            "--symbols",
            "600519.SH",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
        ],
    )

    assert result.exit_code == 0
    assert "excursion_threshold=0.05" in result.output
    assert "recovery_frac=0.5" in result.output
    assert "tp=0.05" in result.output
    assert "hold=8" in result.output
    assert "use_shock_score_filter=true" in result.output
    assert "shock_score_min=60" in result.output
    assert "shock_score_max=80" in result.output
    assert "z_entry=None" not in result.output
    assert "z_exit=None" not in result.output


def test_cli_ranking_output_falls_back_to_non_null_params_for_unknown_strategy(monkeypatch) -> None:
    monkeypatch.setattr("ashare.cli.load_backtest_config", lambda: BacktestConfig())
    monkeypatch.setattr("ashare.cli.get_strategy_class", lambda _: _DummyStrategy)
    monkeypatch.setattr(
        "ashare.cli.execute_experiment_spec",
        lambda **kwargs: {
            "num_runs": 1,
            "output_dir": "outputs/demo",
            "summary_path": "outputs/demo/summary.csv",
            "summary_sorted_path": "outputs/demo/summary_sorted.csv",
            "results": [
                {
                    "sharpe": 1.11,
                    "total_return": 0.05,
                    "params": {
                        "alpha": 3,
                        "beta": None,
                        "flag": True,
                    },
                }
            ],
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "experiment",
            "--strategy",
            "dummy",
            "--symbols",
            "002850.SZ",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
        ],
    )

    assert result.exit_code == 0
    assert "alpha=3" in result.output
    assert "flag=true" in result.output
    assert "beta=None" not in result.output
