import json
from pathlib import Path

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.research.experiment_runner import generate_param_combinations, run_experiment
from ashare.strategies.mid_freq_ma import MidFreqMA


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

    monkeypatch.setattr("ashare.research.experiment_runner.load_minute_30", _fake_loader)

    result = run_experiment(
        strategy_cls=MidFreqMA,
        symbols=["600519.SH", "000858.SZ"],
        param_grid={"short_period": [3, 5], "long_period": [8], "turnover_thresh": [1.0]},
        start_date="2024-01-01",
        end_date="2024-01-20",
        config=BacktestConfig(),
    )

    experiment_dir = Path(result["experiment_dir"])
    results_path = Path(result["results_path"])
    config_path = Path(result["config_path"])

    assert experiment_dir.exists()
    assert results_path.exists()
    assert config_path.exists()

    results_df = pd.read_csv(results_path)
    assert len(results_df) == 4
    assert set(["symbol", "short_period", "long_period", "turnover_thresh", "total_return", "sharpe", "max_drawdown"]).issubset(results_df.columns)

    assert results_df["total_return"].notna().all()
    assert results_df["max_drawdown"].notna().all()

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["combinations"] == 2
    assert payload["runs"] == 4
