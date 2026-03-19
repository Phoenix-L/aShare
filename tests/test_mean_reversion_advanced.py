import backtrader as bt
import pandas as pd
import pytest

from ashare.config.settings import BacktestConfig
from ashare.data.normalizers import to_backtrader_feed
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


def _run(closes: list[float], strategy_params: dict, spread: float = 1.0) -> MeanReversionAdvanced:
    # These tests run on synthetic 30-min data. After the MA refactor,
    # MA periods are interpreted as trading days from a daily-resampled feed.
    # Use small MA windows so SMA(2) is computable within the synthetic horizon.
    strategy_params = {"ma_short": 2, "ma_trend": 2, **strategy_params}
    _, strat, _ = run_backtest(
        strategy_cls=MeanReversionAdvanced,
        data_df=_synthetic_df(closes, spread=spread),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params=strategy_params,
        symbol="SYNTH",
    )
    return strat


def test_advanced_mean_reversion_entry_and_exit_trigger() -> None:
    closes = [100.0] * 180 + [97.0, 101.0, 101.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 0.3,
            "use_trend_filter": False,
            "use_atr_filter": False,
        },
    )

    assert strat.buy_events >= 1
    assert strat.sell_events >= 1
    assert strat.position.size == 0


def test_advanced_mean_reversion_trend_filter_blocks_entry() -> None:
    closes = [100.0] * 180 + [95.0, 95.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 5.0,
            "use_trend_filter": True,
            "use_atr_filter": False,
        },
    )

    assert strat.buy_events == 0
    assert strat.position.size == 0


def test_advanced_mean_reversion_art_filter_blocks_low_volatility_entry() -> None:
    closes = [100.0] * 180 + [99.0, 99.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -0.5,
            "z_exit": 5.0,
            "use_trend_filter": False,
            "use_atr_filter": True,
        },
        spread=0.01,
    )

    assert strat.buy_events == 0
    assert strat.position.size == 0


def test_advanced_mean_reversion_excursion_filter_blocks_entry() -> None:
    closes = [100.0] * 180 + [99.0, 99.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -0.5,
            "z_exit": 5.0,
            "use_trend_filter": False,
            "use_atr_filter": False,
            "use_multi_day_excursion": True,
            "excursion_window": 3,
            "excursion_min": 0.03,
        },
        spread=0.01,
    )

    assert strat.buy_events == 0
    assert strat.position.size == 0


def test_advanced_mean_reversion_excursion_filter_allows_entry() -> None:
    closes = [100.0] * 180 + [97.0, 97.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 5.0,
            "use_trend_filter": False,
            "use_atr_filter": False,
            "use_multi_day_excursion": True,
            "excursion_window": 3,
            "excursion_min": 0.01,
        },
        spread=1.0,
    )

    assert strat.buy_events >= 1
    assert strat.position.size > 0



def test_advanced_mean_reversion_excursion_disabled_with_none_window_does_not_crash() -> None:
    closes = [100.0] * 180 + [97.0, 101.0, 101.0]

    strat = _run(
        closes,
        {
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 0.3,
            "use_trend_filter": False,
            "use_atr_filter": False,
            "use_multi_day_excursion": False,
            "excursion_window": None,
        },
    )

    assert strat.excursion_ratio is None
    assert strat.buy_events >= 1


def test_excursion_signal_mode_does_not_require_excursion_window_even_if_param_set() -> None:
    closes = [100.0] * 180 + [99.0, 99.0]

    # In signal_mode="excursion", multi-day excursion is not used and should not
    # require excursion_window (grid normalization may null it out).
    strat = _run(
        closes,
        {
            "signal_mode": "excursion",
            "trade_unit": 500,
            "z_entry": -10.0,
            "z_exit": 10.0,
            "use_trend_filter": False,
            "use_atr_filter": False,
            "use_multi_day_excursion": True,
            "excursion_window": None,
            "excursion_lookback_bars": 3,
            "excursion_threshold": 0.01,
        },
    )

    assert strat.excursion_ratio is None



def test_advanced_mean_reversion_requires_excursion_window_when_enabled() -> None:
    closes = [100.0] * 180 + [97.0, 97.0]

    with pytest.raises(ValueError, match="Invalid config: excursion_window required"):
        _run(
            closes,
            {
                "trade_unit": 500,
                "z_entry": -1.0,
                "z_exit": 5.0,
                "use_trend_filter": False,
                "use_atr_filter": False,
                "use_multi_day_excursion": True,
                "excursion_window": None,
            },
        )


def test_advanced_mean_reversion_runner_resamples_for_subclasses() -> None:
    class DerivedMeanReversionAdvanced(MeanReversionAdvanced):
        pass

    _, strat, _ = run_backtest(
        strategy_cls=DerivedMeanReversionAdvanced,
        data_df=_synthetic_df([100.0] * 180 + [97.0, 101.0, 101.0]),
        config=BacktestConfig(initial_cash=500_000, commission=0.0, stamp_duty=0.0, slippage_perc=0.0),
        strategy_params={
            "trade_unit": 500,
            "z_entry": -1.0,
            "z_exit": 0.3,
            "use_trend_filter": False,
            "use_atr_filter": False,
            "ma_short": 2,
            "ma_trend": 2,
        },
        symbol="SYNTH",
    )

    assert len(strat.datas) == 2
    assert strat.datas[1]._timeframe == bt.TimeFrame.Days
    assert strat.datas[1]._compression == 1


def test_advanced_mean_reversion_requires_daily_resampled_feed() -> None:
    cerebro = bt.Cerebro()
    cerebro.adddata(to_backtrader_feed(_synthetic_df([100.0] * 200), name="SYNTH"))
    cerebro.addstrategy(
        MeanReversionAdvanced,
        trade_unit=500,
        z_entry=-1.0,
        z_exit=0.3,
        use_trend_filter=False,
        use_atr_filter=False,
        ma_short=2,
        ma_trend=2,
    )

    with pytest.raises(
        ValueError,
        match="daily-resampled feed at datas\\[1\\]",
    ):
        cerebro.run()
