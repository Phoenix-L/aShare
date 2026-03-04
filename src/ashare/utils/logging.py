"""Structured logging setup and helpers for aShare backtesting."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

# Project root (3 levels up from this file: utils -> ashare -> src -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOGS_DIR = _PROJECT_ROOT / "logs"

# Ensure logs directory exists
_LOGS_DIR.mkdir(exist_ok=True)


def setup_logging(level: str | int = None) -> None:
    """
    Configure structured logging for aShare.
    
    Sets up:
    - File handler: logs/ashare_YYYYMMDD.log (daily rotation)
    - Console handler: INFO+ to console
    - Structured format: [LEVEL] timestamp | component | message key=value ...
    
    Parameters
    ----------
    level : str | int, optional
        Logging level (default: INFO). Can be 'DEBUG', 'INFO', 'WARNING', 'ERROR'
        or logging.DEBUG, logging.INFO, etc.
    """
    root_logger = logging.getLogger("ashare")
    
    # Check if logging is already configured (has handlers)
    if root_logger.handlers:
        return  # Already configured, skip
    
    if level is None:
        level = os.getenv("ASHARE_LOG_LEVEL", "INFO")
    
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="[%(levelname)s] %(asctime)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    root_logger.setLevel(level)
    
    # File handler: daily log file
    today = datetime.now().strftime("%Y%m%d")
    log_file = _LOGS_DIR / f"ashare_{today}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler: INFO+ to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a component.
    
    Parameters
    ----------
    name : str
        Logger name (typically module name, e.g., 'ashare.cli' or 'ashare.engine.runner')
    
    Returns
    -------
    logging.Logger
        Configured logger instance
    """
    return logging.getLogger(name)


def log_backtest_start(
    logger: logging.Logger,
    symbol: str,
    strategy: str,
    start_date: str,
    end_date: str,
    config: Any,
) -> None:
    """
    Log structured backtest start information.
    
    Parameters
    ----------
    logger : logging.Logger
        Logger instance
    symbol : str
        Stock symbol
    strategy : str
        Strategy name
    start_date : str
        Start date (YYYY-MM-DD)
    end_date : str
        End date (YYYY-MM-DD)
    config : Any
        BacktestConfig instance
    """
    logger.info(
        f"backtest_start symbol={symbol} strategy={strategy} "
        f"start_date={start_date} end_date={end_date} "
        f"initial_cash={config.initial_cash:.2f} "
        f"commission={config.commission} stamp_duty={config.stamp_duty} "
        f"slippage_perc={config.slippage_perc}"
    )


def log_data_loaded(
    logger: logging.Logger,
    symbol: str,
    num_bars: int,
    start_date: str,
    end_date: str,
    data_start: str | None = None,
    data_end: str | None = None,
) -> None:
    """
    Log structured data loading information.
    
    Parameters
    ----------
    logger : logging.Logger
        Logger instance
    symbol : str
        Stock symbol
    num_bars : int
        Number of data bars loaded
    start_date : str
        Requested start date
    end_date : str
        Requested end date
    data_start : str, optional
        Actual data start datetime
    data_end : str, optional
        Actual data end datetime
    """
    msg = (
        f"data_loaded symbol={symbol} num_bars={num_bars} "
        f"requested_start={start_date} requested_end={end_date}"
    )
    if data_start and data_end:
        msg += f" actual_start={data_start} actual_end={data_end}"
    logger.info(msg)


def log_backtest_execution(
    logger: logging.Logger,
    start_time: datetime,
    end_time: datetime,
    duration_seconds: float,
) -> None:
    """
    Log backtest execution timing.
    
    Parameters
    ----------
    logger : logging.Logger
        Logger instance
    start_time : datetime
        Backtest start time
    end_time : datetime
        Backtest end time
    duration_seconds : float
        Execution duration in seconds
    """
    logger.info(
        f"backtest_execution start_time={start_time.isoformat()} "
        f"end_time={end_time.isoformat()} duration_seconds={duration_seconds:.2f}"
    )


def log_backtest_metrics(
    logger: logging.Logger,
    symbol: str,
    strategy: str,
    num_trades: int,
    metrics: dict[str, Any],
) -> None:
    """
    Log structured backtest metrics.
    
    Parameters
    ----------
    logger : logging.Logger
        Logger instance
    symbol : str
        Stock symbol
    strategy : str
        Strategy name
    num_trades : int
        Number of trades executed
    metrics : dict
        Metrics dictionary with keys: final_value, rtot, sharpe, max_drawdown, etc.
    """
    sharpe_str = f"{metrics.get('sharpe', 0):.4f}" if metrics.get('sharpe') is not None else "N/A"
    
    logger.info(
        f"backtest_complete symbol={symbol} strategy={strategy} "
        f"num_trades={num_trades} "
        f"final_value={metrics.get('final_value', 0):.2f} "
        f"total_return={metrics.get('rtot', 0) * 100:.2f}% "
        f"sharpe_ratio={sharpe_str} "
        f"max_drawdown={metrics.get('max_drawdown', 0):.2f}% "
        f"max_drawdown_len={metrics.get('max_drawdown_len', 0)}"
    )


def log_buy_order(
    logger: logging.Logger,
    symbol: str,
    strategy: str,
    datetime: str,
    price: float,
    size: int,
    value: float,
    cash_before: float,
    cash_after: float,
    reason: str | None = None,
) -> None:
    """
    Log structured buy order execution.
    
    Parameters
    ----------
    logger : logging.Logger
        Logger instance
    symbol : str
        Stock symbol
    strategy : str
        Strategy name
    datetime : str
        Order execution datetime
    price : float
        Execution price per share
    size : int
        Number of shares bought
    value : float
        Total value of the order (price * size + commission)
    cash_before : float
        Cash before the order
    cash_after : float
        Cash after the order
    reason : str, optional
        Reason for the buy (e.g., "crossover signal", "turnover filter")
    """
    msg = (
        f"buy_executed symbol={symbol} strategy={strategy} datetime={datetime} "
        f"price={price:.2f} size={size} value={value:.2f} "
        f"cash_before={cash_before:.2f} cash_after={cash_after:.2f}"
    )
    if reason:
        msg += f" reason={reason}"
    logger.info(msg)


def log_sell_order(
    logger: logging.Logger,
    symbol: str,
    strategy: str,
    datetime: str,
    price: float,
    size: int,
    value: float,
    cash_before: float,
    cash_after: float,
    pnl: float | None = None,
    pnl_pct: float | None = None,
    reason: str | None = None,
) -> None:
    """
    Log structured sell order execution.
    
    Parameters
    ----------
    logger : logging.Logger
        Logger instance
    symbol : str
        Stock symbol
    strategy : str
        Strategy name
    datetime : str
        Order execution datetime
    price : float
        Execution price per share
    size : int
        Number of shares sold
    value : float
        Total value received (price * size - commission)
    cash_before : float
        Cash before the order
    cash_after : float
        Cash after the order
    pnl : float, optional
        Profit/loss in absolute terms
    pnl_pct : float, optional
        Profit/loss as percentage
    reason : str, optional
        Reason for the sell (e.g., "crossover signal", "stop loss")
    """
    msg = (
        f"sell_executed symbol={symbol} strategy={strategy} datetime={datetime} "
        f"price={price:.2f} size={size} value={value:.2f} "
        f"cash_before={cash_before:.2f} cash_after={cash_after:.2f}"
    )
    if pnl is not None:
        msg += f" pnl={pnl:.2f}"
    if pnl_pct is not None:
        msg += f" pnl_pct={pnl_pct:.2f}%"
    if reason:
        msg += f" reason={reason}"
    logger.info(msg)
