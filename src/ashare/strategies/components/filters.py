"""Reusable filter helpers for strategy modules."""


def passes_trend_filter(close: float, ma_value: float, enabled: bool) -> bool:
    """Return whether trend filter passes for a long-only entry."""
    if not enabled:
        return True
    return close > ma_value


def passes_atr_filter(atr_ratio: float, threshold: float, enabled: bool) -> bool:
    """Return whether an ATR-ratio-based volatility filter passes."""
    if not enabled:
        return True
    return atr_ratio >= threshold


# Backward-compatible alias for historical ART typo.
passes_art_filter = passes_atr_filter
