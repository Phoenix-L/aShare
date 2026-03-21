from pathlib import Path

import pytest

from ashare.experiment.spec import load_experiment_spec


def test_load_experiment_spec_parses_expected_structure(tmp_path: Path) -> None:
    spec_file = tmp_path / "demo.yaml"
    spec_file.write_text(
        """
experiment_name: demo_exp
strategy: mid_freq_ma
symbols:
  - 600519.SH
date_range:
  start: 2024-01-01
  end: 2024-12-31
parameters:
  short_period: 5
grid_search:
  long_period:
    - 20
    - 30
execution:
  initial_cash: 200000
  commission: 0.0005
""".strip(),
        encoding="utf-8",
    )

    spec = load_experiment_spec(spec_file)

    assert spec["name"] == "demo_exp"
    assert spec["strategy"] == "mid_freq_ma"
    assert spec["symbols"] == ["600519.SH"]
    assert spec["start"] == "2024-01-01"
    assert spec["end"] == "2024-12-31"
    assert spec["parameters"] == {"short_period": 5}
    assert spec["grid"] == {"long_period": [20, 30]}
    assert spec["execution"] == {"initial_cash": 200000, "commission": 0.0005}


def test_load_experiment_spec_requires_fields(tmp_path: Path) -> None:
    spec_file = tmp_path / "bad.yaml"
    spec_file.write_text("experiment_name: missing_fields", encoding="utf-8")

    with pytest.raises(ValueError, match="Missing required field"):
        load_experiment_spec(spec_file)


def test_load_experiment_spec_supports_template_aliases(tmp_path: Path) -> None:
    spec_file = tmp_path / "shock_reversion_intraday_template.yaml"
    spec_file.write_text(
        """
strategy: shock_reversion_intraday
symbols:
  - 002850.SZ
start: 2025-07-01
end: 2026-02-28
parameters:
  trade_unit: 500
params:
  excursion_lookback_bars:
    - 8
    - 12
  excursion_threshold:
    - 0.03
    - 0.05
""".strip(),
        encoding="utf-8",
    )

    spec = load_experiment_spec(spec_file)

    assert spec["name"] == "shock_reversion_intraday_template"
    assert spec["start"] == "2025-07-01"
    assert spec["end"] == "2026-02-28"
    assert spec["parameters"] == {"trade_unit": 500}
    assert spec["grid"] == {
        "excursion_lookback_bars": [8, 12],
        "excursion_threshold": [0.03, 0.05],
    }
