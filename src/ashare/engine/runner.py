"""Orchestrate: load data, attach strategy, run backtest, return results."""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Type

import backtrader as bt
import pandas as pd

from ashare.config.settings import BacktestConfig
from ashare.engine.analyzers import extract_results, register_analyzers
from ashare.engine.cerebro_builder import build_cerebro
from ashare.data.normalizers import to_backtrader_feed
from ashare.strategies.core_satellite_mean_reversion import CoreSatelliteMeanReversion
from ashare.strategies.mean_reversion import MeanReversion
from ashare.strategies.mean_reversion_advanced import MeanReversionAdvanced
from ashare.utils.logging import get_logger, log_backtest_execution, reset_log_context, set_log_context

logger = get_logger("ashare.engine.runner")


def _build_diagnostics_summary(diagnostics: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate per-bar diagnostics into high-level signal/execution counts."""
    summary = {
        "total_bars": len(diagnostics),
        "entry_signals": 0,
        "executed_trades": 0,
        "blocked_by_trend": 0,
        "blocked_by_atr": 0,
        "blocked_by_art": 0,
        "blocked_by_excursion": 0,
        "blocked_by_multiple": 0,
    }

    for item in diagnostics:
        if not item.get("entry_signal", False):
            continue

        summary["entry_signals"] += 1
        if item.get("executed", False):
            summary["executed_trades"] += 1
            continue

        blocked_by = set(item.get("blocked_by", []))
        has_trend = "trend_filter" in blocked_by
        has_atr = "atr_filter" in blocked_by or "art_filter" in blocked_by
        has_excursion = "excursion_filter" in blocked_by
        if has_trend:
            summary["blocked_by_trend"] += 1
        if has_atr:
            summary["blocked_by_atr"] += 1
            summary["blocked_by_art"] += 1
        if has_excursion:
            summary["blocked_by_excursion"] += 1
        if sum((has_trend, has_atr, has_excursion)) >= 2:
            summary["blocked_by_multiple"] += 1

    return summary


def run_backtest(
    strategy_cls: Type[bt.Strategy],
    data_df: pd.DataFrame,
    config: BacktestConfig,
    strategy_params: dict | None = None,
    symbol: str | None = None,
    experiment_name: str | None = None,
    run_id: str | None = None,
    output_dir: Path | None = None,
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
    experiment_name : str, optional
        Experiment name for log correlation (if applicable)
    run_id : str, optional
        Run identifier within an experiment for log correlation (if applicable)
    """
    start_time = datetime.now()

    ctx_token = set_log_context(symbol=symbol, experiment_name=experiment_name, run_id=run_id)

    logger.debug(f"Building cerebro with config: initial_cash={config.initial_cash}, commission={config.commission + config.stamp_duty}")
    cerebro = build_cerebro(config)

    logger.debug(f"Converting DataFrame to Backtrader feed: {len(data_df)} bars")
    feed = to_backtrader_feed(data_df, name=symbol)
    cerebro.adddata(feed)

    # Only enable daily MA/trend computation when the strategy uses it.
    # This avoids affecting strategies that don't need daily closes and
    # prevents resampling-related edge cases in Backtrader.
    needs_daily_ma = issubclass(
        strategy_cls,
        (
            MeanReversionAdvanced,
            MeanReversion,
            CoreSatelliteMeanReversion,
        ),
    )
    if needs_daily_ma:
        # Add a daily-resampled view of the same feed so strategies can compute
        # moving averages in units of "trading days" rather than intraday bars.
        #
        # Note: this relies on `to_backtrader_feed()` setting correct timeframe/
        # compression for the primary feed.
        cerebro.resampledata(feed, timeframe=bt.TimeFrame.Days, compression=1)

    strategy_params = dict(strategy_params or {})
    logger.debug(f"Adding strategy: {strategy_cls.__name__} with params: {strategy_params}")
    cerebro.addstrategy(strategy_cls, **strategy_params)
    register_analyzers(cerebro)

    logger.debug("Starting backtest execution...")
    try:
        results = cerebro.run()
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        strat = results[0]
        metrics = extract_results(cerebro, strat)

        diagnostics = getattr(strat, "diagnostics", None)
        if diagnostics is not None:
            diagnostics_summary = _build_diagnostics_summary(diagnostics)
            metrics["diagnostics_summary"] = diagnostics_summary

            target_dir = output_dir
            if target_dir is None and experiment_name is not None and run_id is not None:
                target_dir = Path("outputs") / experiment_name / run_id
            elif target_dir is None and run_id is not None:
                target_dir = Path("outputs") / run_id

            if target_dir is not None:
                target_dir.mkdir(parents=True, exist_ok=True)
                (target_dir / "diagnostics.json").write_text(
                    json.dumps(diagnostics, indent=2),
                    encoding="utf-8",
                )
                (target_dir / "diagnostics_summary.json").write_text(
                    json.dumps(diagnostics_summary, indent=2),
                    encoding="utf-8",
                )

            logger.info(
                "Diagnostics summary:\nSignals: %s\nExecuted: %s\nBlocked by trend: %s\nBlocked by ATR: %s\nBlocked by excursion: %s",
                diagnostics_summary["entry_signals"],
                diagnostics_summary["executed_trades"],
                diagnostics_summary["blocked_by_trend"],
                diagnostics_summary["blocked_by_atr"],
                diagnostics_summary["blocked_by_excursion"],
            )

        log_backtest_execution(logger, start_time, end_time, duration)

        logger.debug(
            f"Backtest completed: final_value={metrics.get('final_value', 0):.2f}, return={metrics.get('rtot', 0) * 100:.2f}%"
        )

        return cerebro, strat, metrics
    finally:
        reset_log_context(ctx_token)
