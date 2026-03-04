"""Orchestrate: load data, attach strategy, run backtest, return results."""

from datetime import datetime
from typing import Any, Type

import backtrader as bt
import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.analyzers import extract_results, register_analyzers
from ashare.engine.cerebro_builder import build_cerebro
from ashare.data.normalizers import to_backtrader_feed
from ashare.utils.logging import get_logger, log_backtest_execution

logger = get_logger("ashare.engine.runner")


def run_backtest(
    strategy_cls: Type[bt.Strategy],
    data_df: pd.DataFrame,
    config: BacktestConfig,
    strategy_params: dict | None = None,
    symbol: str | None = None,
) -> tuple[bt.Cerebro, bt.Strategy, dict[str, Any]]:
    """
    Build cerebro, add data and strategy, run, return cerebro, strategy instance, and metrics.

    Parameters
    ----------
    strategy_cls : Type[bt.Strategy]
        Strategy class to use
    data_df : pd.DataFrame
        Price data DataFrame
    config : BacktestConfig
        Backtest configuration
    strategy_params : dict, optional
        Optional dict of strategy params (e.g. short_period=5)
    symbol : str, optional
        Stock symbol name (for logging and data feed identification)
    """
    start_time = datetime.now()
    
    logger.debug(f"Building cerebro with config: initial_cash={config.initial_cash}, commission={config.commission + config.stamp_duty}")
    cerebro = build_cerebro(config)
    
    logger.debug(f"Converting DataFrame to Backtrader feed: {len(data_df)} bars")
    feed = to_backtrader_feed(data_df, name=symbol)
    cerebro.adddata(feed)
    
    logger.debug(f"Adding strategy: {strategy_cls.__name__} with params: {strategy_params}")
    cerebro.addstrategy(strategy_cls, **(strategy_params or {}))
    register_analyzers(cerebro)

    logger.info("Starting backtest execution...")
    results = cerebro.run()
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    strat = results[0]
    metrics = extract_results(cerebro, strat)
    
    # Log execution timing
    log_backtest_execution(logger, start_time, end_time, duration)
    
    logger.debug(f"Backtest completed: final_value={metrics.get('final_value', 0):.2f}, return={metrics.get('rtot', 0) * 100:.2f}%")
    
    return cerebro, strat, metrics
