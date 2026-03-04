"""Sanity checks for data loaders and integrations (BaoStock/Tushare providers)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from ashare.data.loaders import load_daily, load_minute_30


@dataclass
class SanityCheckResult:
    """Structured result for a sanity check run."""

    loader_name: str
    passed: bool
    message: str
    df: pd.DataFrame | None = None


def _validate_standard_ohlcv_schema(
    loader_name: str,
    df: pd.DataFrame,
) -> SanityCheckResult:
    """
    Validate a standard OHLCV(+turnover_rate) DataFrame.

    Expected:
    - Datetime index, sorted ascending.
    - Columns: open, high, low, close, volume, turnover_rate.
    """
    if df is None or df.empty:
        return SanityCheckResult(
            loader_name=loader_name,
            passed=False,
            message=f"{loader_name} returned empty DataFrame",
            df=df,
        )

    required = ["open", "high", "low", "close", "volume", "turnover_rate"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        return SanityCheckResult(
            loader_name=loader_name,
            passed=False,
            message=f"{loader_name} missing columns: {missing}",
            df=df,
        )

    # Best-effort datetime index and sortedness checks
    try:
        _ = df.index.to_series().astype("datetime64[ns]")
    except Exception:
        return SanityCheckResult(
            loader_name=loader_name,
            passed=False,
            message=f"{loader_name} index is not datetime-like",
            df=df,
        )

    if not df.index.is_monotonic_increasing:
        return SanityCheckResult(
            loader_name=loader_name,
            passed=False,
            message=f"{loader_name} index is not sorted ascending",
            df=df,
        )

    return SanityCheckResult(
        loader_name=loader_name,
        passed=True,
        message=(
            f"{loader_name} OK: {len(df)} rows "
            f"from {df.index.min()} to {df.index.max()}"
        ),
        df=df,
    )


def run_loader_sanity_check(
    loader_name: str,
    loader_fn: Callable[..., pd.DataFrame],
    *,
    ts_code: str,
    start_date: str,
    end_date: str,
) -> SanityCheckResult:
    """
    Call a loader, perform basic structural checks, and return a structured result.

    This helper is designed for loaders that:
    - Accept ts_code, start_date, end_date (YYYY-MM-DD).
    - Return a DataFrame in the standard OHLCV(+turnover_rate) schema.
    """
    try:
        df = loader_fn(ts_code=ts_code, start_date=start_date, end_date=end_date)
    except Exception as exc:  # pragma: no cover - integration/IO paths
        return SanityCheckResult(
            loader_name=loader_name,
            passed=False,
            message=f"Exception while calling {loader_name}: {exc}",
            df=None,
        )

    return _validate_standard_ohlcv_schema(loader_name, df)


def sanitycheck_daily(
    ts_code: str,
    start_date: str,
    end_date: str,
) -> SanityCheckResult:
    """Sanity check for the daily loader."""
    return run_loader_sanity_check(
        "load_daily",
        load_daily,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
    )


def sanitycheck_minute30(
    ts_code: str,
    start_date: str,
    end_date: str,
) -> SanityCheckResult:
    """Sanity check for the 30-minute loader."""
    return run_loader_sanity_check(
        "load_minute_30",
        load_minute_30,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
    )

