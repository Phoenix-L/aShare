"""Backtest/event-study harness for regime state machine research.

This is a standalone research script and does NOT alter live strategy logic.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from regime_features import FeatureConfig, compute_regime_features
from regime_rules import TRENDING, classify_regime_states, extract_transition_events


@dataclass(frozen=True)
class LabelConfig:
    breakdown_horizon: int = 15
    displacement_threshold: float = 0.025
    reset_band: float = 0.005
    lead_tolerance_bars: int = 8


def load_ohlcv_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"datetime", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing required columns: {sorted(missing)}")
    return df


def _forward_return(close: pd.Series, horizon: int = 5) -> pd.Series:
    return close.shift(-horizon) / close - 1.0


def _future_breakdown_label(df: pd.DataFrame, cfg: LabelConfig) -> pd.Series:
    distance = df["distance_from_equilibrium"].abs().to_numpy()
    labels = np.zeros(len(df), dtype=int)

    for i in range(len(df)):
        end = min(i + cfg.breakdown_horizon, len(df) - 1)
        if i + 1 > end:
            continue
        future = distance[i + 1 : end + 1]
        sustained = np.mean(future >= cfg.displacement_threshold) >= 0.6
        failed_return = np.all(future > cfg.reset_band)
        labels[i] = int(sustained and failed_return)

    return pd.Series(labels, index=df.index)


def compute_state_behavior_metrics(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["fwd_return_5"] = _forward_return(work["close"], horizon=5)
    out = (
        work.groupby("regime_state", dropna=False)
        .agg(
            avg_forward_return=("fwd_return_5", "mean"),
            avg_snapback_probability=("snapback_rate", "mean"),
            avg_trend_efficiency=("trend_efficiency", "mean"),
            observations=("regime_state", "size"),
        )
        .reset_index()
    )
    return out


def compute_transition_signal_quality(df: pd.DataFrame, cfg: LabelConfig) -> dict[str, float]:
    work = df.copy()
    work["future_breakdown_label"] = _future_breakdown_label(work, cfg=cfg)

    y_true = work["future_breakdown_label"].astype(bool)
    y_pred = work["transition_signal"].astype(bool)

    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    tn = int((~y_true & ~y_pred).sum())

    precision = tp / (tp + fp) if (tp + fp) else np.nan
    recall = tp / (tp + fn) if (tp + fn) else np.nan
    false_alarm_rate = fp / (fp + tn) if (fp + tn) else np.nan

    # Lead time: bars between transition signal and next trending-state confirmation.
    lead_times: list[int] = []
    signal_indices = work.index[work["transition_signal"]].tolist()
    trending_indices = work.index[work["regime_state"] == TRENDING].tolist()

    for si in signal_indices:
        future_trend = [ti for ti in trending_indices if ti >= si]
        if not future_trend:
            continue
        lead = future_trend[0] - si
        if lead <= cfg.lead_tolerance_bars:
            lead_times.append(lead)

    return {
        "precision": float(precision) if not np.isnan(precision) else np.nan,
        "recall": float(recall) if not np.isnan(recall) else np.nan,
        "false_alarm_rate": float(false_alarm_rate) if not np.isnan(false_alarm_rate) else np.nan,
        "avg_lead_time_bars": float(np.mean(lead_times)) if lead_times else np.nan,
        "n_transition_signals": int(y_pred.sum()),
        "n_breakdown_labels": int(y_true.sum()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def run_for_ticker(
    ticker: str,
    input_dir: Path,
    output_dir: Path,
    feature_cfg: FeatureConfig,
    label_cfg: LabelConfig,
) -> tuple[pd.DataFrame, dict[str, float]]:
    source = input_dir / f"{ticker}.csv"
    raw = load_ohlcv_csv(source)

    featured = compute_regime_features(raw, config=feature_cfg)
    classified = classify_regime_states(featured)
    events = extract_transition_events(classified)

    ticker_dir = output_dir / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)

    cols = [
        "datetime",
        "close",
        "equilibrium",
        "distance_from_equilibrium",
        "trend_efficiency",
        "persistence",
        "snapback_rate",
        "regime_state",
        "transition_signal",
    ]
    classified[cols].to_csv(ticker_dir / "regime_state.csv", index=False)
    events.to_csv(ticker_dir / "regime_transition_events.csv", index=False)

    state_metrics = compute_state_behavior_metrics(classified)
    signal_metrics = compute_transition_signal_quality(classified, cfg=label_cfg)
    signal_metrics["ticker"] = ticker
    return state_metrics.assign(ticker=ticker), signal_metrics


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic regime-state-machine research backtest.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["002850.SZ", "000001.SZ", "600519.SH"],
        help="Ticker list. Each ticker should have a matching CSV in --input-dir.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/research/ohlcv"),
        help="Directory containing OHLCV CSV files named <ticker>.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("research/regime_state_machine/outputs"),
        help="Where to write per-ticker regime outputs and aggregate reports.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    feature_cfg = FeatureConfig()
    label_cfg = LabelConfig()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_state_metrics: list[pd.DataFrame] = []
    all_signal_metrics: list[dict[str, float]] = []

    for ticker in args.tickers:
        state_metrics, signal_metrics = run_for_ticker(
            ticker=ticker,
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            feature_cfg=feature_cfg,
            label_cfg=label_cfg,
        )
        all_state_metrics.append(state_metrics)
        all_signal_metrics.append(signal_metrics)

    pd.concat(all_state_metrics, ignore_index=True).to_csv(args.output_dir / "state_behavior_summary.csv", index=False)
    pd.DataFrame(all_signal_metrics).to_csv(args.output_dir / "transition_signal_summary.csv", index=False)

    config_dump = {
        "feature_config": asdict(feature_cfg),
        "label_config": asdict(label_cfg),
    }
    pd.Series(config_dump).to_json(args.output_dir / "config_snapshot.json", indent=2)


if __name__ == "__main__":
    main()
