"""Orchestrate: load data, attach strategy, run backtest, return results."""

from typing import Any, Type

import backtrader as bt
import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.analyzers import extract_results, register_analyzers
from ashare.engine.cerebro_builder import build_cerebro
from ashare.data.normalizers import to_backtrader_feed


def run_backtest(
    strategy_cls: Type[bt.Strategy],
    data_df: pd.DataFrame,
    config: BacktestConfig,
    strategy_params: dict | None = None,
) -> tuple[bt.Cerebro, bt.Strategy, dict[str, Any]]:
    """
    Build cerebro, add data and strategy, run, return cerebro, strategy instance, and metrics.

    strategy_params: optional dict of strategy params (e.g. short_period=5).
    """
    cerebro = build_cerebro(config)
    feed = to_backtrader_feed(data_df)
    cerebro.adddata(feed)
    cerebro.addstrategy(strategy_cls, **(strategy_params or {}))
    register_analyzers(cerebro)

    results = cerebro.run()
    strat = results[0]
    metrics = extract_results(cerebro, strat)
    return cerebro, strat, metrics
