import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.runner import run_backtest
from ashare.strategies.shock_reversion_intraday import ShockReversionIntradayStrategy


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


def _run(closes: list[float], strategy_params: dict) -> ShockReversionIntradayStrategy:
    _, strat, _ = run_backtest(
        strategy_cls=ShockReversionIntradayStrategy,
        data_df=_synthetic_df(closes),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={"trend_ma_period": 2, **strategy_params},
        symbol="SYNTH",
    )
    return strat


def test_shock_reversion_enters_on_excursion_signal() -> None:
    closes = [100.0] * 180 + [97.0, 97.0, 97.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": False,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "max_hold_bars": 10,
            "stop_loss_pct": 0.10,
        },
    )

    assert strat.buy_events >= 1
    assert strat.position.size > 0


def test_shock_reversion_trend_filter_blocks_entry() -> None:
    closes = [100.0] * 180 + [95.0, 95.0, 95.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": True,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "max_hold_bars": 10,
            "stop_loss_pct": 0.10,
        },
    )

    assert strat.buy_events == 0
    assert strat.position.size == 0


def test_shock_reversion_exits_on_max_hold() -> None:
    closes = [100.0] * 180 + [97.0, 97.0, 97.0, 97.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "use_trend_filter": False,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
            "max_hold_bars": 2,
            "stop_loss_pct": 0.10,
        },
    )

    assert strat.buy_events >= 1
    assert strat.sell_events >= 1
    assert strat.position.size == 0
