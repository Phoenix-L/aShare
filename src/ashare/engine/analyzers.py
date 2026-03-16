"""Analyzer registration and result extraction."""

from typing import Any

import backtrader as bt


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
    
    total_return = strat.analyzers.returns.get_analysis().get("rtot", 0.0)

    return {
        "final_value": cerebro.broker.getvalue(),
        "rtot": total_return,
        "total_return": total_return,
        "sharpe": sharpe_value,
        "max_drawdown": strat.analyzers.drawdown.get_analysis()["max"]["drawdown"],
        "max_drawdown_len": strat.analyzers.drawdown.get_analysis()["max"]["len"],
        "num_trades": num_trades,
    }
