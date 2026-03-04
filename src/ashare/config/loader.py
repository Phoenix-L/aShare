"""Config loading from env / files (later YAML)."""

from pathlib import Path

from dotenv import load_dotenv

from ashare.config.settings import BacktestConfig

# Load .env from project root (aShare/)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_PROJECT_ROOT / ".env")


def load_backtest_config(
    initial_cash: float | None = None,
    commission: float | None = None,
    stamp_duty: float | None = None,
    slippage_perc: float | None = None,
) -> BacktestConfig:
    """Load backtest config; override with explicit args if provided."""
    defaults = BacktestConfig()
    return BacktestConfig(
        initial_cash=initial_cash if initial_cash is not None else defaults.initial_cash,
        commission=commission if commission is not None else defaults.commission,
        stamp_duty=stamp_duty if stamp_duty is not None else defaults.stamp_duty,
        slippage_perc=slippage_perc if slippage_perc is not None else defaults.slippage_perc,
    )
