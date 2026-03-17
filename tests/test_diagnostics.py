from pathlib import Path
import json

import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies.mean_reversion_advanced import MeanReversionAdvanced


def _synthetic_df(closes: list[float], spread: float = 1.0) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="30min")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
            "volume": [1000] * len(closes),
            "turnover_rate": [2.0] * len(closes),
        },
        index=idx,
    )


def _config() -> BacktestConfig:
    return BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0)


def test_diagnostics_populated_and_block_reasons_trend() -> None:
    closes = [100.0] * 180 + [95.0, 95.0]
    _, strat, metrics = run_backtest(
        strategy_cls=MeanReversionAdvanced,
        data_df=_synthetic_df(closes),
        config=_config(),
        strategy_params={
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 5.0,
            "use_trend_filter": True,
            "use_art_filter": False,
        },
        symbol="SYNTH",
    )

    assert len(strat.diagnostics) > 0
    blocked = [row for row in strat.diagnostics if row["entry_signal"] and not row["executed"]]
    assert blocked
    assert any("trend_filter" in row["blocked_by"] for row in blocked)
    summary = metrics["diagnostics_summary"]
    assert summary["entry_signals"] >= 1
    assert summary["blocked_by_trend"] >= 1


def test_diagnostics_output_files_generated(tmp_path: Path) -> None:
    closes = [100.0] * 180 + [99.0, 99.0]
    out_dir = tmp_path / "run_001"

    _, _, metrics = run_backtest(
        strategy_cls=MeanReversionAdvanced,
        data_df=_synthetic_df(closes, spread=0.01),
        config=_config(),
        strategy_params={
            "trade_unit": 500,
            "z_entry": -0.5,
            "z_exit": 5.0,
            "use_trend_filter": False,
            "use_art_filter": True,
        },
        symbol="SYNTH",
        run_id="run_001",
        output_dir=out_dir,
    )

    diagnostics_path = out_dir / "diagnostics.json"
    summary_path = out_dir / "diagnostics_summary.json"

    assert diagnostics_path.exists()
    assert summary_path.exists()

    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert len(diagnostics) == summary["total_bars"]
    assert summary == metrics["diagnostics_summary"]
    assert summary["blocked_by_art"] >= 1
