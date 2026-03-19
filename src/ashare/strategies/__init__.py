"""Strategy modules and registry for CLI lookup."""

from ashare.strategies.core_satellite_mean_reversion import CoreSatelliteMeanReversion
from ashare.strategies.mid_freq_ma import MidFreqMA
from ashare.strategies.mean_reversion import MeanReversion
from ashare.strategies.mean_reversion_advanced import MeanReversionAdvanced
from ashare.strategies.shock_reversion_intraday import ShockReversionIntradayStrategy

STRATEGY_REGISTRY: dict[str, type] = {
    "mid_freq_ma": MidFreqMA,
    "core_satellite": CoreSatelliteMeanReversion,
    "mean_reversion": MeanReversion,
    "mean_reversion_advanced": MeanReversionAdvanced,
    "shock_reversion_intraday": ShockReversionIntradayStrategy,
}


def get_strategy_class(name: str):
    """Resolve strategy name to strategy class. Raises KeyError if unknown."""
    if name not in STRATEGY_REGISTRY:
        raise KeyError(f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[name]
