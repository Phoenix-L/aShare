"""Orchestrate: load data, attach strategy, run backtest, return results."""

from datetime import datetime
import json
import statistics
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
from ashare.strategies.shock_reversion_intraday import ShockReversionIntradayStrategy
from ashare.strategies.validation import validate_strategy_params
from ashare.utils.logging import get_logger, log_backtest_execution, reset_log_context, set_log_context

logger = get_logger("ashare.engine.runner")


def _safe_avg(values: list[float]) -> float:
    """Return average or 0.0 when no values are present."""
    return sum(values) / len(values) if values else 0.0




def _resolve_strategy_name(strategy_cls: Type[bt.Strategy]) -> str | None:
    """Return the registry name for strategies that require explicit param validation."""
    strategy_map = {
        "core_satellite": CoreSatelliteMeanReversion,
        "mean_reversion": MeanReversion,
        "mean_reversion_advanced": MeanReversionAdvanced,
        "shock_reversion_intraday": ShockReversionIntradayStrategy,
    }
    for name, candidate in strategy_map.items():
        if issubclass(strategy_cls, candidate):
            return name
    return None


def _validate_strategy_history_requirements(
    strategy_cls: Type[bt.Strategy],
    data_df: pd.DataFrame,
    strategy_params: dict[str, Any],
) -> None:
    """Fail fast when a strategy declares unmet history requirements."""
    validator = getattr(strategy_cls, "validate_data_history", None)
    if callable(validator):
        validator(data_df, strategy_params)


def _build_diagnostics_summary(
    diagnostics: list[dict[str, Any]],
    completed_trades: list[dict[str, Any]] | None = None,
    strategy: bt.Strategy | None = None,
) -> dict[str, Any]:
    """Aggregate per-bar and per-trade diagnostics into high-level metrics."""
    uses_trend_filter = bool(getattr(strategy, "uses_trend_filter", True))
    uses_atr_filter = bool(getattr(strategy, "uses_atr_filter", False))
    uses_shock_score_filter = any(
        "blocked_by_shock_score" in item or "shock_score_filter_enabled" in item
        for item in diagnostics
    )

    summary: dict[str, Any] = {
        "total_bars": len(diagnostics),
        "entry_signals": 0,
        "executed_trades": 0,
        "blocked_by_multiple": 0,
    }
    if uses_trend_filter:
        summary["blocked_by_trend"] = 0
    if uses_atr_filter:
        summary["blocked_by_atr"] = 0
        summary["blocked_by_art"] = 0
    if uses_shock_score_filter:
        summary["blocked_by_shock_score"] = 0

    for item in diagnostics:
        if not item.get("entry_signal", False):
            continue

        summary["entry_signals"] += 1
        if item.get("executed", False):
            summary["executed_trades"] += 1
            continue

        blocked_by = set(item.get("blocked_by", []))
        active_blocks = 0
        if uses_trend_filter and "trend_filter" in blocked_by:
            summary["blocked_by_trend"] += 1
            active_blocks += 1
        if uses_atr_filter and ("atr_filter" in blocked_by or "art_filter" in blocked_by):
            summary["blocked_by_atr"] += 1
            summary["blocked_by_art"] += 1
            active_blocks += 1
        if uses_shock_score_filter and item.get("blocked_by_shock_score", False):
            summary["blocked_by_shock_score"] += 1
            active_blocks += 1
        if uses_trend_filter or uses_atr_filter:
            if active_blocks >= 2:
                summary["blocked_by_multiple"] += 1
        elif blocked_by:
            summary["blocked_by_multiple"] += 1

    completed_trades = list(completed_trades or [])
    mfe_values = [float(trade.get("mfe_pct", trade.get("max_favorable_excursion", 0.0))) for trade in completed_trades]
    mae_values = [float(trade.get("mae_pct", trade.get("max_adverse_excursion", 0.0))) for trade in completed_trades]
    pnl_values = [float(trade.get("pnl_pct", 0.0)) for trade in completed_trades]
    etd_values = [max(0.0, float(trade.get("etd", 0.0))) for trade in completed_trades]

    avg_mfe = _safe_avg(mfe_values)
    avg_mae = _safe_avg(mae_values)
    avg_pnl = _safe_avg(pnl_values)
    avg_etd = _safe_avg(etd_values)
    summary["avg_mfe"] = avg_mfe
    summary["avg_mae"] = avg_mae
    summary["avg_pnl"] = avg_pnl
    summary["avg_etd"] = avg_etd
    summary["median_etd"] = statistics.median(etd_values) if etd_values else 0.0
    summary["max_etd"] = max(etd_values) if etd_values else 0.0
    summary["mfe_pnl_gap"] = avg_mfe - avg_pnl
    summary["etd_pnl_gap"] = avg_etd
    summary["pnl_capture_ratio"] = avg_pnl / avg_mfe if avg_mfe > 0 else 0.0

    exit_reasons = ["recovery", "take_profit", "stop_loss", "max_hold"]
    win_rate_by_exit_reason: dict[str, float] = {}
    avg_holding_bars_by_exit_reason: dict[str, float] = {}
    for reason in exit_reasons:
        subset = [trade for trade in completed_trades if trade.get("exit_reason") == reason]
        win_rate_by_exit_reason[reason] = (
            sum(1 for trade in subset if float(trade.get("pnl_pct", 0.0)) > 0) / len(subset)
            if subset else 0.0
        )
        avg_holding_bars_by_exit_reason[reason] = _safe_avg(
            [float(trade.get("holding_bars", 0.0)) for trade in subset]
        )

    summary["win_rate_by_exit_reason"] = win_rate_by_exit_reason
    summary["avg_holding_bars_by_exit_reason"] = avg_holding_bars_by_exit_reason
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
    strategy_name = _resolve_strategy_name(strategy_cls)
    if strategy_name is not None:
        strategy_params = validate_strategy_params(strategy_name, strategy_params)
    _validate_strategy_history_requirements(strategy_cls, data_df, strategy_params)
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
            completed_trades = getattr(strat, "completed_trades", None)
            diagnostics_summary = _build_diagnostics_summary(
                diagnostics,
                completed_trades=completed_trades,
                strategy=strat,
            )
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

            log_lines = [
                "Diagnostics summary:",
                f"Signals: {diagnostics_summary['entry_signals']}",
                f"Executed: {diagnostics_summary['executed_trades']}",
            ]
            if "blocked_by_trend" in diagnostics_summary:
                log_lines.append(f"Blocked by trend: {diagnostics_summary['blocked_by_trend']}")
            if "blocked_by_atr" in diagnostics_summary:
                log_lines.append(f"Blocked by ATR: {diagnostics_summary['blocked_by_atr']}")
            if "blocked_by_multiple" in diagnostics_summary:
                log_lines.append(f"Blocked by multiple: {diagnostics_summary['blocked_by_multiple']}")
            logger.info("\n".join(log_lines))

        log_backtest_execution(logger, start_time, end_time, duration)

        logger.debug(
            f"Backtest completed: final_value={metrics.get('final_value', 0):.2f}, return={metrics.get('rtot', 0) * 100:.2f}%"
        )

        return cerebro, strat, metrics
    finally:
        reset_log_context(ctx_token)
