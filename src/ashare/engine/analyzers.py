"""Analyzer registration and result extraction."""

from typing import Any

import backtrader as bt


def register_analyzers(cerebro: bt.Cerebro) -> None:
    """Add Sharpe, DrawDown, and Returns analyzers to cerebro."""
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")


def extract_results(cerebro: bt.Cerebro, strat: bt.Strategy) -> dict[str, Any]:
    """Extract analyzer results from the first strategy after cerebro.run()."""
    return {
        "final_value": cerebro.broker.getvalue(),
        "rtot": strat.analyzers.returns.get_analysis().get("rtot", 0.0),
        "sharpe": strat.analyzers.sharpe.get_analysis().get("sharperatio"),
        "max_drawdown": strat.analyzers.drawdown.get_analysis()["max"]["drawdown"],
        "max_drawdown_len": strat.analyzers.drawdown.get_analysis()["max"]["len"],
    }
