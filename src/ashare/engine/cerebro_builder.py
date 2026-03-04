"""Cerebro setup: broker cash, commission, slippage."""

import backtrader as bt

from ashare.config.settings import BacktestConfig


def build_cerebro(config: BacktestConfig) -> bt.Cerebro:
    """Build a Cerebro instance with broker settings; no data or strategy attached."""
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(config.initial_cash)
    cerebro.broker.setcommission(**config.to_broker_kwargs())
    cerebro.broker.set_slippage_perc(config.slippage_perc)
    return cerebro
