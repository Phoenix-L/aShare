"""Compatibility bridge to market-data-core contracts.

This module is intentionally small and defensive:
- If ``market_data_core`` is available, delegate canonical bar schema/validation to it.
- If not available, keep legacy aShare behavior to preserve runtime compatibility.

TODO(phase5): remove fallback path once market-data-core is mandatory in all environments.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable

import pandas as pd

_FALLBACK_CANONICAL_COLUMNS: tuple[str, ...] = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "turnover_rate",
)


def _first_attr(module: object, names: tuple[str, ...]) -> object | None:
    for name in names:
        value = getattr(module, name, None)
        if value is not None:
            return value
    return None


def _load_mdc_contracts() -> object | None:
    """Best-effort load for market-data-core contract surface."""
    candidates = (
        "market_data_core.contracts.bar",
        "market_data_core.contracts.bars",
        "market_data_core.schema.bar",
        "market_data_core.schema.bars",
    )
    for path in candidates:
        try:
            return importlib.import_module(path)
        except ImportError:
            continue
    return None


def using_market_data_core() -> bool:
    """Return whether market-data-core contract modules are importable."""
    return _load_mdc_contracts() is not None


def canonical_bar_columns() -> tuple[str, ...]:
    """Get canonical OHLCV+turnover columns from market-data-core (or fallback)."""
    module = _load_mdc_contracts()
    if module is None:
        return _FALLBACK_CANONICAL_COLUMNS

    columns = _first_attr(
        module,
        (
            "CANONICAL_BAR_COLUMNS",
            "CANONICAL_COLUMNS",
            "BAR_COLUMNS",
            "REQUIRED_COLUMNS",
        ),
    )
    if columns is None:
        return _FALLBACK_CANONICAL_COLUMNS

    as_tuple = tuple(columns)
    return as_tuple or _FALLBACK_CANONICAL_COLUMNS


def _fallback_validate(df: pd.DataFrame, *, source: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError(f"{source} returned no data")

    required = canonical_bar_columns()
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{source} missing required columns: {', '.join(missing)}")

    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"{source} index must be DatetimeIndex")

    if not df.index.is_monotonic_increasing:
        df = df.sort_index()

    return df


def validate_canonical_frame(df: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Validate a canonical market-data frame.

    Delegates to market-data-core when available, otherwise uses aShare fallback checks.
    """
    module = _load_mdc_contracts()
    if module is None:
        return _fallback_validate(df, source=source)

    validator = _first_attr(
        module,
        (
            "validate_canonical_bar_frame",
            "validate_bar_frame",
            "validate_ohlcv_frame",
        ),
    )
    if validator is None or not callable(validator):
        return _fallback_validate(df, source=source)

    maybe_df = (validator)(df)
    if isinstance(maybe_df, pd.DataFrame):
        validated = maybe_df
    else:
        validated = df

    if not isinstance(validated.index, pd.DatetimeIndex):
        raise ValueError(f"{source} index must be DatetimeIndex")
    if not validated.index.is_monotonic_increasing:
        validated = validated.sort_index()
    return validated
