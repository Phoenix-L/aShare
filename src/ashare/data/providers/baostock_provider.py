"""BaoStock data provider implementation."""

import os
import pandas as pd

import baostock as bs

from ashare.data.providers.base import DataProvider


class BaoStockProvider(DataProvider):
    """BaoStock-based data provider.
    
    BaoStock is a free Chinese stock data API that doesn't require authentication tokens.
    However, it requires login/logout session management.
    """

    def __init__(self):
        """Initialize BaoStock session."""
        self._logged_in = False
        self._shares_outstanding_cache: dict[str, float] = {}  # Cache: ts_code -> shares_outstanding
        self._ensure_login()

    def _ensure_login(self) -> None:
        """Ensure BaoStock session is logged in."""
        if not self._logged_in:
            lg = bs.login()
            if lg.error_code != '0':
                raise RuntimeError(
                    f"BaoStock login failed: {lg.error_msg} "
                    f"(error_code: {lg.error_code})"
                )
            self._logged_in = True

    def _normalize_code(self, ts_code: str) -> str:
        """
        Convert Tushare format code to BaoStock format.
        
        Examples:
            "000001.SZ" -> "sz.000001"
            "600001.SH" -> "sh.600001"
        """
        if "." not in ts_code:
            raise ValueError(f"Invalid code format: {ts_code}. Expected format: '000001.SZ' or '600001.SH'")
        
        code, exchange = ts_code.split(".")
        
        if exchange.upper() == "SZ":
            return f"sz.{code}"
        elif exchange.upper() == "SH":
            return f"sh.{code}"
        else:
            raise ValueError(f"Unknown exchange: {exchange}. Expected 'SZ' or 'SH'")

    def _get_shares_outstanding(self, ts_code: str) -> float:
        """
        Fetch shares outstanding (tradable shares) for a stock from BaoStock.
        
        Uses query_profit_data API which provides liqaShare (流通股本 - tradable shares).
        Uses caching to avoid repeated API calls since shares outstanding changes infrequently.
        
        Parameters
        ----------
        ts_code : str
            Stock code in Tushare format (e.g., "000001.SZ")
        
        Returns
        -------
        float
            Shares outstanding (in shares)
        """
        # Check cache first
        if ts_code in self._shares_outstanding_cache:
            return self._shares_outstanding_cache[ts_code]
        
        self._ensure_login()
        bs_code = self._normalize_code(ts_code)
        
        # Query profit data to get shares outstanding
        # BaoStock's query_profit_data provides liqaShare (流通股本) in shares
        # Try latest available quarter (Q4, then Q3, Q2, Q1)
        from datetime import datetime
        current_year = datetime.now().year
        
        data_list = None
        rs = None
        
        for quarter in [4, 3, 2, 1]:
            rs = bs.query_profit_data(code=bs_code, year=current_year, quarter=quarter)
            if rs.error_code == '0':
                # Get the data - only iterate once!
                temp_data_list = []
                while (rs.error_code == '0') & rs.next():
                    temp_data_list.append(rs.get_row_data())
                if temp_data_list:
                    data_list = temp_data_list
                    break
        
        # If current year doesn't have data, try previous year
        if data_list is None:
            prev_year = current_year - 1
            for quarter in [4, 3, 2, 1]:
                rs = bs.query_profit_data(code=bs_code, year=prev_year, quarter=quarter)
                if rs.error_code == '0':
                    temp_data_list = []
                    while (rs.error_code == '0') & rs.next():
                        temp_data_list.append(rs.get_row_data())
                    if temp_data_list:
                        data_list = temp_data_list
                        break
        
        if data_list is None:
            if rs is None:
                raise ValueError(f"BaoStock query_profit_data failed for {ts_code}: No response")
            else:
                raise ValueError(
                    f"BaoStock query_profit_data failed for {ts_code}: {rs.error_msg} "
                    f"(error_code: {rs.error_code})"
                )
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # BaoStock returns liqaShare (流通股本) already in shares (not 万股)
        if "liqaShare" in df.columns:
            liqa_share = pd.to_numeric(df["liqaShare"].iloc[0], errors='coerce')
            if pd.isna(liqa_share) or liqa_share <= 0:
                raise ValueError(f"Invalid liqaShare for {ts_code}: {liqa_share}")
            shares_outstanding = float(liqa_share)
        elif "totalShare" in df.columns:
            # Fallback to totalShare if liqaShare not available
            total_share = pd.to_numeric(df["totalShare"].iloc[0], errors='coerce')
            if pd.isna(total_share) or total_share <= 0:
                raise ValueError(f"Invalid totalShare for {ts_code}: {total_share}")
            shares_outstanding = float(total_share)
        else:
            raise ValueError(f"No shares outstanding data available for {ts_code}")
        
        # Cache the result
        self._shares_outstanding_cache[ts_code] = shares_outstanding
        
        return shares_outstanding

    def fetch_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV data from BaoStock.
        
        Calculates turnover_rate correctly as: (volume / shares_outstanding) * 100
        Shares outstanding is fetched from BaoStock's stock basic info API and cached.
        
        Returns normalized DataFrame with datetime index and columns:
        open, high, low, close, volume, turnover_rate
        """
        self._ensure_login()
        
        bs_code = self._normalize_code(ts_code)
        
        # BaoStock expects YYYY-MM-DD format (already matches our input)
        rs = bs.query_history_k_data_plus(
            bs_code,
            fields="date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 3 = no adjustment
        )
        
        if rs.error_code != '0':
            raise ValueError(
                f"BaoStock query failed for {ts_code}: {rs.error_msg} "
                f"(error_code: {rs.error_code})"
            )
        
        # Convert to DataFrame
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            raise ValueError(f"No daily data returned for {ts_code}")
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # Normalize schema
        df.rename(columns={
            "date": "datetime",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }, inplace=True)
        
        # Convert types
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        
        # Calculate turnover_rate correctly: (volume / shares_outstanding) * 100
        # Turnover rate (换手率) = (Trading Volume / Total Shares Outstanding) × 100%
        try:
            shares_outstanding = self._get_shares_outstanding(ts_code)
            # volume is already in shares, shares_outstanding is in shares
            # Result is percentage (e.g., 2.5 means 2.5%)
            df["turnover_rate"] = (df["volume"] / shares_outstanding) * 100
            df["turnover_rate"] = df["turnover_rate"].fillna(0.0)
        except Exception as e:
            # If we can't get shares outstanding, log warning and set to 0
            import warnings
            warnings.warn(
                f"Could not fetch shares outstanding for {ts_code}: {e}. "
                f"Setting turnover_rate to 0.0"
            )
            df["turnover_rate"] = 0.0
        
        # Select final columns
        df = df[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "turnover_rate",
            ]
        ]
        
        df.sort_index(inplace=True)
        
        return df

    def fetch_minute30(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch 30-minute OHLCV data from BaoStock.
        
        Note: BaoStock provides minute data, but turnover_rate needs to be
        approximated or fetched from daily data and mapped to minutes.
        
        Returns normalized DataFrame with datetime index and columns:
        open, high, low, close, volume, turnover_rate
        """
        self._ensure_login()
        
        bs_code = self._normalize_code(ts_code)
        
        # BaoStock minute data query
        rs = bs.query_history_k_data_plus(
            bs_code,
            fields="date,time,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="30",  # 30-minute frequency
            adjustflag="3"  # 3 = no adjustment
        )
        
        if rs.error_code != '0':
            raise ValueError(
                f"BaoStock query failed for {ts_code}: {rs.error_msg} "
                f"(error_code: {rs.error_code})"
            )
        
        # Convert to DataFrame
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            raise ValueError(f"No 30-minute data returned for {ts_code}")
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # Parse datetime from time field (BaoStock time format: YYYYMMDDHHMMSSSSS with milliseconds)
        # The time field already contains full datetime information
        # Format: %Y%m%d%H%M%S%f where %f is microseconds (but BaoStock gives milliseconds)
        # We'll parse it flexibly by handling the milliseconds part
        def parse_baostock_time(time_str: str) -> pd.Timestamp:
            """Parse BaoStock time string (YYYYMMDDHHMMSSSSS format)."""
            if len(time_str) == 17:
                # Format: YYYYMMDDHHMMSSSSS (17 digits with milliseconds)
                return pd.to_datetime(time_str[:14], format="%Y%m%d%H%M%S")
            elif len(time_str) == 14:
                # Format: YYYYMMDDHHMMSS (14 digits without milliseconds)
                return pd.to_datetime(time_str, format="%Y%m%d%H%M%S")
            else:
                # Fallback: let pandas infer
                return pd.to_datetime(time_str)
        
        df["datetime"] = df["time"].apply(parse_baostock_time)
        
        # Normalize schema
        df.rename(columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume",
        }, inplace=True)
        
        # Convert types
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.set_index("datetime", inplace=True)
        
        # For turnover_rate, fetch daily data and map to minutes
        try:
            df_daily = self.fetch_daily(ts_code, start_date, end_date)
            df_daily_turnover = df_daily[["turnover_rate"]].copy()
            df_daily_turnover.index = df_daily_turnover.index.normalize()
            
            # Map daily turnover_rate to minute bars
            df["turnover_rate"] = df.index.normalize().map(df_daily_turnover["turnover_rate"])
            df["turnover_rate"] = df["turnover_rate"].ffill()
        except Exception:
            # If daily fetch fails, calculate approximate from amount
            if "amount" in df.columns:
                df["amount"] = pd.to_numeric(df["amount"], errors='coerce')
                df["turnover_rate"] = (df["amount"] / df["volume"]) / df["close"] * 100
                df["turnover_rate"] = df["turnover_rate"].fillna(0.0)
            else:
                df["turnover_rate"] = 0.0
        
        # Select final columns
        df = df[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "turnover_rate",
            ]
        ]
        
        df.sort_index(inplace=True)
        
        return df

    def __del__(self):
        """Cleanup: logout from BaoStock on provider destruction."""
        if self._logged_in:
            try:
                bs.logout()
            except Exception:
                pass  # Ignore errors during cleanup
