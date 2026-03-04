"""Analyzer registration and result extraction."""

from typing import Any

import backtrader as bt


def register_analyzers(cerebro: bt.Cerebro) -> None:
    """Add Sharpe, DrawDown, Returns, and Trade analyzers to cerebro."""
    # Configure SharpeRatio analyzer for 30-minute data
    # For 30-minute bars in Chinese market:
    # - Trading hours: 9:30-11:30 (2 hours) + 13:00-15:00 (2 hours) = 4 hours/day
    # - 30-min bars per day: 4 hours * 2 = 8 bars/day
    # - Trading days per year: ~252 days
    # - Total 30-min bars per year: 252 * 8 = 2016 bars
    # Using TimeFrame.Minutes with compression=30 and factor=2016 for proper annualization
    cerebro.addanalyzer(
        bt.analyzers.SharpeRatio,
        _name="sharpe",
        timeframe=bt.TimeFrame.Minutes,  # 30-minute bars
        compression=30,  # 30-minute compression
        annualize=True,
        riskfreerate=0.0,
        factor=2016.0,  # 30-min bars per year (252 trading days * 8 bars/day)
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
    
    # Try different possible key names for Sharpe ratio
    sharpe_value = (
        sharpe_analysis.get("sharperatio")
        or sharpe_analysis.get("sharpeRatio")
        or sharpe_analysis.get("sharpe")
    )
    
    # If still None, try to calculate manually from Returns analyzer as fallback
    if sharpe_value is None:
        try:
            returns_analysis = strat.analyzers.returns.get_analysis()
            rtot = returns_analysis.get("rtot", 0.0)
            rnorm = returns_analysis.get("rnorm", 0.0)
            rnorm100 = returns_analysis.get("rnorm100", 0.0)
            
            # If we have normalized returns, try to calculate Sharpe
            # Sharpe = (mean return - risk free rate) / std(returns)
            # For now, if rnorm is available and non-zero, we can estimate
            # But this is a simplified calculation
            logger.debug(
                f"SharpeRatio is None. Returns analysis: rtot={rtot}, rnorm={rnorm}, rnorm100={rnorm100}"
            )
            
            # Log warning about why it might be None
            logger.warning(
                f"SharpeRatio returned None. This may indicate: "
                f"1) Insufficient variance in portfolio returns (all periods have same return), "
                f"2) Timeframe configuration mismatch, or "
                f"3) Not enough data points for meaningful calculation. "
                f"Analyzer output: {sharpe_analysis}, Returns: {returns_analysis}"
            )
        except Exception as e:
            logger.warning(f"Could not extract returns for Sharpe fallback: {e}")
    
    # Extract number of trades
    num_trades = 0
    try:
        trade_analysis = strat.analyzers.trade.get_analysis()
        num_trades = trade_analysis.get("total", {}).get("total", 0) or 0
    except (AttributeError, KeyError, TypeError):
        # Trade analyzer might not have data or structure is different
        pass
    
    return {
        "final_value": cerebro.broker.getvalue(),
        "rtot": strat.analyzers.returns.get_analysis().get("rtot", 0.0),
        "sharpe": sharpe_value,
        "max_drawdown": strat.analyzers.drawdown.get_analysis()["max"]["drawdown"],
        "max_drawdown_len": strat.analyzers.drawdown.get_analysis()["max"]["len"],
        "num_trades": num_trades,
    }
