"""Analyzer registration and result extraction."""

from __future__ import annotations

from typing import Any

import backtrader as bt


_SHARPE_NONE_WARNED_KEYS: set[tuple[str, int, str]] = set()


def _maybe_log_sharpe_none(
    *,
    logger,
    sharpe_analysis: dict[str, Any],
    returns_analysis: dict[str, Any],
    num_trades: int,
    total_return: float,
    strategy_name: str,
) -> None:
    """
    Sharpe=None is common for short/flat runs; keep logs concise and deduped.

    Policy:
    - Always log full analyzer payloads at DEBUG.
    - Emit at most one INFO line per (strategy, num_trades, sign(total_return)) to avoid spam in experiments.
    """
    logger.debug("SharpeRatio is None. sharpe=%s returns=%s", sharpe_analysis, returns_analysis)

    from ashare.utils.logging import get_log_context

    ctx = get_log_context()
    experiment_name = ctx.get("experiment_name", "")
    run_id = ctx.get("run_id", "")
    symbol = ctx.get("symbol", "")

    # Collapse continuous returns into a coarse bucket so dedupe works across many param sets.
    return_bucket = "pos" if total_return > 0 else ("neg" if total_return < 0 else "zero")
    key = (experiment_name, symbol, strategy_name, int(num_trades), return_bucket)
    if key in _SHARPE_NONE_WARNED_KEYS:
        return
    _SHARPE_NONE_WARNED_KEYS.add(key)

    # Keep this short and searchable; do not dump large dicts at INFO.
    logger.info(
        "sharpe_none experiment_name=%s run_id=%s symbol=%s strategy=%s num_trades=%s total_return=%.6f",
        experiment_name,
        run_id,
        symbol,
        strategy_name,
        num_trades,
        total_return,
    )


def register_analyzers(cerebro: bt.Cerebro) -> None:
    """
    Add Sharpe, DrawDown, Returns, and Trade analyzers to cerebro.
    
    SharpeRatio is configured to use daily portfolio returns for calculation,
    even when the underlying data is 30-minute bars. This ensures consistent
    Sharpe ratio calculation regardless of data frequency.
    
    For 30-minute data, Backtrader will automatically aggregate portfolio values
    to daily intervals before calculating the Sharpe ratio.
    """
    # Configure SharpeRatio analyzer to use daily returns
    # This works for both daily and 30-minute data:
    # - For daily data: Uses daily returns directly
    # - For 30-minute data: Aggregates portfolio values to daily, then calculates Sharpe
    # - factor=252.0: Trading days per year for annualization
    # - riskfreerate=0.03: 3% annual risk-free rate (typical for Chinese market)
    cerebro.addanalyzer(
        bt.analyzers.SharpeRatio,
        _name="sharpe",
        timeframe=bt.TimeFrame.Days,  # Use daily timeframe for Sharpe calculation
        compression=1,  # 1 day compression
        annualize=True,
        riskfreerate=0.03,  # 3% annual risk-free rate
        factor=252.0,  # Trading days per year for annualization
    )
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trade")


def extract_results(cerebro: bt.Cerebro, strat: bt.Strategy) -> dict[str, Any]:
    """Extract analyzer results from the first strategy after cerebro.run()."""
    from ashare.utils.logging import get_logger
    
    logger = get_logger("ashare.engine.analyzers")
    
    sharpe_analysis = strat.analyzers.sharpe.get_analysis()
    
    # Debug: log what the analyzer returns
    logger.debug(f"SharpeRatio analyzer output: {sharpe_analysis}")
    
    returns_analysis = {}
    try:
        returns_analysis = strat.analyzers.returns.get_analysis()
    except Exception as e:
        logger.debug("Could not read returns analyzer: %s", e)

    # Extract number of trades early (used for Sharpe=None noise policy)
    num_trades = 0
    try:
        trade_analysis = strat.analyzers.trade.get_analysis()
        num_trades = trade_analysis.get("total", {}).get("total", 0) or 0
    except (AttributeError, KeyError, TypeError):
        pass

    total_return = returns_analysis.get("rtot", 0.0) if isinstance(returns_analysis, dict) else 0.0

    # Try different possible key names for Sharpe ratio
    sharpe_value = (
        sharpe_analysis.get("sharperatio")
        or sharpe_analysis.get("sharpeRatio")
        or sharpe_analysis.get("sharpe")
    )
    
    # If still None, log once (deduped) and keep payload at DEBUG.
    if sharpe_value is None:
        try:
            _maybe_log_sharpe_none(
                logger=logger,
                sharpe_analysis=sharpe_analysis if isinstance(sharpe_analysis, dict) else {"sharpe": sharpe_analysis},
                returns_analysis=returns_analysis if isinstance(returns_analysis, dict) else {"returns": returns_analysis},
                num_trades=num_trades,
                total_return=float(total_return or 0.0),
                strategy_name=str(getattr(strat, "__class__", type(strat)).__name__),
            )
        except Exception as e:
            logger.debug("Sharpe=None logging failed: %s", e)

    return {
        "final_value": cerebro.broker.getvalue(),
        "rtot": total_return,
        "total_return": total_return,
        "sharpe": sharpe_value,
        "max_drawdown": strat.analyzers.drawdown.get_analysis()["max"]["drawdown"],
        "max_drawdown_len": strat.analyzers.drawdown.get_analysis()["max"]["len"],
        "num_trades": num_trades,
    }
