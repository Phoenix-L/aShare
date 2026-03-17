"""Reusable filter helpers for strategy modules."""


def passes_trend_filter(close: float, ma_value: float, enabled: bool) -> bool:
    """Return whether trend filter passes for a long-only entry."""
    if not enabled:
        return True
    return close > ma_value


def passes_art_filter(art_value: float, threshold: float, enabled: bool) -> bool:
    """Return whether ART-based volatility filter passes."""
    if not enabled:
        return True
    return art_value >= threshold
