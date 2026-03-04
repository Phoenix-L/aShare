"""Data provider factory and registry."""

import os
from typing import TYPE_CHECKING

from ashare.data.providers.base import DataProvider

if TYPE_CHECKING:
    pass

# Environment variable to control which provider to use
_PROVIDER_ENV = "ASHARE_DATA_PROVIDER"

# Default provider (BaoStock is free, no token required)
_DEFAULT_PROVIDER = "baostock"

# Singleton provider instance (lazy initialization)
_provider_instance: DataProvider | None = None


def get_provider() -> DataProvider:
    """
    Get the configured data provider instance.
    
    Provider selection:
    - Set ASHARE_DATA_PROVIDER environment variable to "baostock" or "tushare"
    - Defaults to "baostock" if not set
    
    Returns
    -------
    DataProvider
        Configured provider instance (singleton)
    """
    global _provider_instance
    
    if _provider_instance is None:
        provider_name = os.getenv(_PROVIDER_ENV, _DEFAULT_PROVIDER).lower()
        
        if provider_name == "baostock":
            from ashare.data.providers.baostock_provider import BaoStockProvider
            _provider_instance = BaoStockProvider()
        elif provider_name == "tushare":
            from ashare.data.providers.tushare_provider import TushareProvider
            _provider_instance = TushareProvider()
        else:
            raise ValueError(
                f"Unknown data provider: {provider_name}. "
                f"Expected 'baostock' or 'tushare'. "
                f"Set {_PROVIDER_ENV} environment variable to choose."
            )
    
    return _provider_instance


def reset_provider() -> None:
    """Reset the provider singleton (useful for testing or switching providers)."""
    global _provider_instance
    _provider_instance = None
