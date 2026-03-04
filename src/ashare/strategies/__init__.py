"""Strategy modules and registry for CLI lookup."""

from ashare.strategies.mid_freq_ma import MidFreqMA

STRATEGY_REGISTRY: dict[str, type] = {
    "mid_freq_ma": MidFreqMA,
}


def get_strategy_class(name: str):
    """Resolve strategy name to strategy class. Raises KeyError if unknown."""
    if name not in STRATEGY_REGISTRY:
        raise KeyError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[name]
