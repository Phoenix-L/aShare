"""Minute and daily data loaders for A-shares."""

import pandas as pd

from ashare.data.tushare_client import get_pro

def load_minute_30(
    ts_code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Load 30-minute OHLCV data and attach turnover_rate from daily_basic.

    Returns
    -------
    pandas.DataFrame
        Indexed by datetime with columns:
        open, high, low, close, volume, turnover_rate
    """

    pro = get_pro()

    start_ts = f"{start_date} 09:30:00"
    end_ts = f"{end_date} 15:00:00"

    # ---------------------------------
    # 1️⃣ Load minute data
    # ---------------------------------
    df = pro.stk_mins(
        ts_code=ts_code,
        start_time=start_ts,
        end_time=end_ts,
        freq="30min",
    )

    if df is None or df.empty:
        raise ValueError(f"No minute data for {ts_code}")

    # ---------------------------------
    # 2️⃣ Normalize minute schema
    # ---------------------------------
    rename_map = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "vol": "volume",
    }

    if "trade_time" in df.columns:
        rename_map["trade_time"] = "datetime"
    elif "tradetime" in df.columns:
        rename_map["tradetime"] = "datetime"

    df = df.rename(columns=rename_map)

    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    df.sort_index(inplace=True)

    # ---------------------------------
    # 3️⃣ Load turnover_rate
    # ---------------------------------
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")

    df_basic = pro.daily_basic(
        ts_code=ts_code,
        start_date=start,
        end_date=end,
        fields="ts_code,trade_date,turnover_rate"
    )

    if df_basic.empty:
        raise ValueError(f"No daily_basic data for {ts_code}")

    df_basic["trade_date"] = pd.to_datetime(df_basic["trade_date"], format="%Y%m%d")

    df_basic = df_basic.set_index("trade_date")["turnover_rate"]

    # ---------------------------------
    # 4️⃣ Map turnover_rate to minute bars
    # ---------------------------------
    df["turnover_rate"] = df.index.normalize().map(df_basic)

    # fill missing values (non-trading minutes etc.)
    df["turnover_rate"] = df["turnover_rate"].fillna(method="ffill")

    # ---------------------------------
    # 5️⃣ Final schema
    # ---------------------------------
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

    return df


def load_daily(
    ts_code: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Load daily OHLCV data and merge turnover_rate from daily_basic.

    Returns
    -------
    pandas.DataFrame
        Indexed by datetime with columns:
        open, high, low, close, volume, turnover_rate
    """
    pro = get_pro()
    
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")

    # -------------------------------
    # 1️⃣ Load price data
    # -------------------------------
    df_price = pro.daily(
        ts_code=ts_code,
        start_date=start,
        end_date=end
    )

    if df_price.empty:
        raise ValueError(f"No daily price data for {ts_code}")
        
    # -------------------------------
    # 2️⃣ Load turnover data
    # -------------------------------
    df_basic = pro.daily_basic(
        ts_code=ts_code,
        start_date=start,
        end_date=end,
        fields="ts_code,trade_date,turnover_rate"
    )

    # -------------------------------
    # 3️⃣ Merge datasets
    # -------------------------------
    df = pd.merge(
        df_price,
        df_basic[["trade_date", "turnover_rate"]],
        on="trade_date",
        how="left"
    )

    # -------------------------------
    # 4️⃣ Normalize columns
    # -------------------------------
    df.rename(columns={
        "trade_date": "datetime",
        "vol": "volume"
    }, inplace=True)

    # -------------------------------
    # 5️⃣ Convert datetime
    # -------------------------------
    df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d")

    df.set_index("datetime", inplace=True)

    # -------------------------------
    # 6️⃣ Select required fields
    # -------------------------------
    df = df[
        [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover_rate"
        ]
    ]

    # -------------------------------
    # 7️⃣ Sort chronologically
    # -------------------------------
    df.sort_index(inplace=True)

    return df
    
