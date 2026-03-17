"""Config loading from env / files."""

from pathlib import Path
from typing import Any

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


def _coerce_yaml_scalar(value: str) -> Any:
    raw = value.strip()
    lower = raw.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def load_strategy_config(config_path: str | Path) -> dict[str, Any]:
    """Load simple strategy YAML configuration without external dependencies."""
    payload: dict[str, Any] = {}
    current_list_key: str | None = None

    for line in Path(config_path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            if current_list_key is None:
                continue
            payload.setdefault(current_list_key, []).append(_coerce_yaml_scalar(stripped[2:]))
            continue

        current_list_key = None
        if ":" not in stripped:
            continue

        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value = raw_value.strip()

        if value == "":
            payload[key] = []
            current_list_key = key
        else:
            payload[key] = _coerce_yaml_scalar(value)

    return payload
