"""Compatibility bridge to market-data-core stable APIs.

This module intentionally provides narrow wrappers:
- Prefer `market_data_core` Phase 5 stable surfaces (`access`, `validation`, `calendar`).
- Keep conservative local fallbacks where the upstream package is unavailable.
"""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable
from datetime import date, datetime

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


def _load_mdc_access() -> object | None:
    try:
        return importlib.import_module("market_data_core.access")
    except ImportError:
        return None


def _load_mdc_validation() -> object | None:
    try:
        return importlib.import_module("market_data_core.validation")
    except ImportError:
        return None


def _load_mdc_calendar() -> object | None:
    try:
        return importlib.import_module("market_data_core.calendar")
    except ImportError:
        return None


def using_market_data_core() -> bool:
    """Return whether any market-data-core stable module is importable."""
    return any(
        (
            _load_mdc_contracts() is not None,
            _load_mdc_access() is not None,
            _load_mdc_validation() is not None,
            _load_mdc_calendar() is not None,
        )
    )


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


def _call_with_supported_kwargs(fn: Callable[..., object], kwargs: dict[str, object]) -> object:
    signature = inspect.signature(fn)
    accepted: dict[str, object] = {}
    for name, value in kwargs.items():
        if name in signature.parameters:
            accepted[name] = value
    return fn(**accepted)


def validate_canonical_frame(df: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Validate a canonical market-data frame.

    Delegates to market-data-core when available, otherwise uses aShare fallback checks.
    """
    validation_module = _load_mdc_validation()
    if validation_module is not None:
        validate_bars = getattr(validation_module, "validate_bars", None)
        if callable(validate_bars):
            result = _call_with_supported_kwargs(
                validate_bars,
                {
                    "df": df,
                    "frequency": source_frequency(source),
                    "market": "cn_equity",
                    "strict": True,
                },
            )
            report_ok = getattr(result, "ok", True)
            report_errors = getattr(result, "errors", [])
            if report_ok is False:
                raise ValueError(f"{source} failed market-data-core validation: {report_errors}")

    contracts_module = _load_mdc_contracts()
    validator = None
    if contracts_module is not None:
        validator = _first_attr(
            contracts_module,
            (
                "validate_canonical_bar_frame",
                "validate_bar_frame",
                "validate_ohlcv_frame",
            ),
        )

    if validator is None or not callable(validator):
        validated = _fallback_validate(df, source=source)
    else:
        maybe_df = validator(df)
        validated = maybe_df if isinstance(maybe_df, pd.DataFrame) else df

    if not isinstance(validated.index, pd.DatetimeIndex):
        raise ValueError(f"{source} index must be DatetimeIndex")
    if not validated.index.is_monotonic_increasing:
        validated = validated.sort_index()
    return validated


def source_frequency(source: str) -> str:
    if "minute" in source or "30" in source:
        return "30m"
    return "1d"


def load_daily_from_core(
    *,
    symbol: str,
    start: str,
    end: str,
    use_cache: bool = True,
) -> pd.DataFrame | None:
    """Best-effort delegate to `market_data_core.access.load_daily`."""
    module = _load_mdc_access()
    if module is None:
        return None
    fn = getattr(module, "load_daily", None)
    if not callable(fn):
        return None
    loaded = _call_with_supported_kwargs(
        fn,
        {"symbol": symbol, "start": start, "end": end, "use_cache": use_cache},
    )
    if not isinstance(loaded, pd.DataFrame):
        raise ValueError("market_data_core.access.load_daily did not return DataFrame")
    return loaded


def load_30m_from_core(
    *,
    symbol: str,
    start: str,
    end: str,
    use_cache: bool = True,
) -> pd.DataFrame | None:
    """Best-effort delegate to `market_data_core.access.load_30m/load_minute_30`."""
    module = _load_mdc_access()
    if module is None:
        return None

    fn = _first_attr(module, ("load_30m", "load_minute_30"))
    if not callable(fn):
        return None

    loaded = _call_with_supported_kwargs(
        fn,
        {"symbol": symbol, "start": start, "end": end, "use_cache": use_cache},
    )
    if not isinstance(loaded, pd.DataFrame):
        raise ValueError("market_data_core.access intraday loader did not return DataFrame")
    return loaded


def list_datasets_from_core(*, data_root: str | None = None) -> list[str] | None:
    module = _load_mdc_access()
    if module is None:
        return None
    fn = getattr(module, "list_datasets", None)
    if not callable(fn):
        return None
    result = _call_with_supported_kwargs(fn, {"data_root": data_root})
    return list(result)


def inspect_dataset_from_core(
    dataset_id: str,
    *,
    data_root: str | None = None,
) -> dict[str, object] | None:
    module = _load_mdc_access()
    if module is None:
        return None
    fn = getattr(module, "inspect_dataset", None)
    if not callable(fn):
        return None
    result = _call_with_supported_kwargs(fn, {"dataset_id": dataset_id, "data_root": data_root})
    return dict(result)


def session_open_anchors_from_core(
    *,
    trading_day: date,
    frequency: str,
) -> tuple[datetime, ...] | None:
    module = _load_mdc_calendar()
    if module is None:
        return None
    fn = getattr(module, "session_open_anchors", None)
    if not callable(fn):
        return None
    result = _call_with_supported_kwargs(fn, {"trading_day": trading_day, "frequency": frequency})
    return tuple(result)


def is_session_aligned_from_core(*, timestamp: datetime, frequency: str) -> bool | None:
    module = _load_mdc_calendar()
    if module is None:
        return None
    fn = getattr(module, "is_session_aligned", None)
    if not callable(fn):
        return None
    result = _call_with_supported_kwargs(fn, {"timestamp": timestamp, "frequency": frequency})
    return bool(result)
