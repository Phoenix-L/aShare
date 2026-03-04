"""Tushare API config, token handling, and connection."""

import os
from pathlib import Path

import tushare as ts
from dotenv import load_dotenv

# Load .env from project root when module is loaded
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")

_TOKEN_ENV = "TUSHARE_TOKEN"


def get_pro() -> ts.pro_api:
    """Return Tushare pro_api instance; token must be set via TUSHARE_TOKEN env or ts.set_token."""
    token = os.getenv(_TOKEN_ENV)
    if not token:
        raise RuntimeError(
            f"{_TOKEN_ENV} environment variable not set. "
            "Copy .env.example to .env and set your Tushare token."
        )
    ts.set_token(token)
    return ts.pro_api()
