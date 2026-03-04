"""Base strategy / params interface (optional common base for all strategies)."""

import backtrader as bt


class BaseStrategy(bt.Strategy):
    """Base class for ashare strategies; no broker/data wiring, just optional shared helpers."""

    pass
