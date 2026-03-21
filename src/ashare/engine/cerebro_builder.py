"""Cerebro setup: broker cash, commission, slippage."""

import backtrader as bt

from ashare.config.settings import BacktestConfig
from ashare.engine.broker import UnrestrictedMarginBroker


def build_cerebro(config: BacktestConfig) -> bt.Cerebro:
    """Build a Cerebro instance with broker settings; no data or strategy attached."""
    cerebro = bt.Cerebro()
    broker = UnrestrictedMarginBroker()
    broker.setcash(config.initial_cash)
    broker.setcommission(**config.to_broker_kwargs())
    broker.set_slippage_perc(config.slippage_perc)
    cerebro.setbroker(broker)
    return cerebro
