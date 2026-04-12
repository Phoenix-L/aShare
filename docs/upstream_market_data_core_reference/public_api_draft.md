# Public API Draft (updated through Phase 5)

## Goals
- Keep API surface small and stable.
- Return pandas DataFrames for bar data APIs.
- Keep metadata/storage inspection APIs filesystem-agnostic for consumer repos.

Namespace shown as `market_data_core`.

---

## 1) Stable load APIs (implemented)

```python
from market_data_core.access import load_bars, load_daily, load_30m, load_minute_30
```

```python
def load_bars(
    symbol: str,
    start: str,
    end: str,
    frequency: str,
    adjustment: str = "raw",
    source_preference: str = "canonical",
    provider: str | None = None,
    use_cache: bool = True,
    data_root: str | None = None,
) -> pd.DataFrame:
    """Load canonical bars with strict validation."""
```

Compatibility wrappers:
- `load_daily(...)` → `frequency="1d"`
- `load_30m(...)` → `frequency="30m"`
- `load_minute_30(...)` compatibility alias for `aShare` migration path

---

## 2) Stable validation APIs (implemented)

```python
from market_data_core.validation import validate_bars
```

```python
def validate_bars(
    df: pd.DataFrame,
    frequency: str,
    market: str = "cn_equity",
    strict: bool = True,
) -> "ValidationReport":
    """Validate schema, invariants, and CN A-share session alignment."""
```

`ValidationReport` fields:
- `ok: bool`
- `errors: list[str]`
- `warnings: list[str]`
- `stats: dict[str, int | float]`

---

## 3) Stable dataset metadata APIs (implemented)

```python
from market_data_core.access import list_datasets, inspect_dataset
```

```python
def list_datasets(data_root: str | None = None) -> list[str]:
    """List dataset ids discovered from storage manifests."""
```

```python
def inspect_dataset(dataset_id: str, data_root: str | None = None) -> dict[str, object]:
    """Return latest manifest payload for dataset id."""
```

---

## 4) Stable calendar/session APIs (implemented)

```python
from market_data_core.calendar import session_open_anchors, is_session_aligned
```

```python
def session_open_anchors(trading_day: date, frequency: str) -> tuple[datetime, ...]:
    """Return canonical CN A-share open anchors."""
```

---

## 5) Deferred APIs

Still draft/deferred:
- `ingest.ingest_bars`
- `transform.resample_bars`
- `transform.apply_adjustment`

These remain out of stable surface until implemented with full contract tests.

---

## 6) Stability policy

- APIs listed above as implemented are Phase 5 stable for consumer repos.
- New parameters must be additive with safe defaults.
- Breaking changes require explicit migration notes and compatibility strategy.
