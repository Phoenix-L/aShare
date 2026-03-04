"""Abstract base class for market data providers."""

from abc import ABC, abstractmethod
import pandas as pd


class DataProvider(ABC):
    """Abstract interface for market data providers.
    
    All providers must return DataFrames with the same normalized schema:
    - Index: datetime (sorted ascending)
    - Columns: open, high, low, close, volume, turnover_rate
    """

    @abstractmethod
    def fetch_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV data with turnover_rate.
        
        Parameters
        ----------
        ts_code : str
            Stock code in Tushare format (e.g., "000001.SZ", "600001.SH")
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format
        
        Returns
        -------
        pd.DataFrame
            Indexed by datetime with columns:
            open, high, low, close, volume, turnover_rate
        """
        pass

    @abstractmethod
    def fetch_minute30(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch 30-minute OHLCV data with turnover_rate.
        
        Parameters
        ----------
        ts_code : str
            Stock code in Tushare format (e.g., "000001.SZ", "600001.SH")
        start_date : str
            Start date in YYYY-MM-DD format
        end_date : str
            End date in YYYY-MM-DD format
        
        Returns
        -------
        pd.DataFrame
            Indexed by datetime with columns:
            open, high, low, close, volume, turnover_rate
        """
        pass
