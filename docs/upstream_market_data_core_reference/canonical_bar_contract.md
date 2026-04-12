# Canonical Bar Contract (`market-data-core`)

## Purpose
This document defines the canonical OHLCV bar schema that all provider adapters must output before data is exposed through public load APIs.

Scope in Phase 1:
- China A-share daily bars.
- China A-share intraday bars (starting with 30-minute).

---

## 1) Required columns

| Column | Type | Meaning | Nulls |
|---|---|---|---|
| `symbol` | `string` | Canonical instrument identifier (`000001.SZ`, `600000.SH`). | Not allowed |
| `timestamp` | `datetime64[ns, Asia/Shanghai]` | **Bar open time** in exchange-local timezone. | Not allowed |
| `open` | `float64` | First traded price in bar interval. | Not allowed |
| `high` | `float64` | Maximum traded price in bar interval. | Not allowed |
| `low` | `float64` | Minimum traded price in bar interval. | Not allowed |
| `close` | `float64` | Last traded price in bar interval. | Not allowed |
| `volume` | `float64` | Traded volume for interval; unit is provider-normalized to shares where available. | Not allowed |

### Required for Phase 1 A-share compatibility
| Column | Type | Meaning | Nulls |
|---|---|---|---|
| `turnover_rate` | `float64` | Turnover rate as percent points per bar/day, following current provider semantics from aShare. | Allowed when provider cannot supply/derive |

Notes:
- Keep `turnover_rate` in the canonical contract now to preserve current loader behavior.
- A future major version may move it to an optional extension contract.

---

## 2) Optional columns

Optional fields may exist but must not break consumers expecting the required set.

| Column | Type | Meaning |
|---|---|---|
| `amount` | `float64` | Traded amount/turnover value in currency. |
| `vwap` | `float64` | Volume-weighted average price for bar. |
| `trade_count` | `Int64` | Number of trades in bar. |
| `provider` | `string` | Source provider id (`baostock`, `tushare`). |
| `frequency` | `string` | Frequency label (`1d`, `30m`, etc.) for auditability. |

Rule: optional columns must be additive and never alter required-column semantics.

---

## 3) Key, uniqueness, and ordering rules

1. Primary key is `(symbol, timestamp)`.
2. Data MUST be unique by key; duplicates are invalid.
3. Sort order MUST be ascending by `timestamp` within each `symbol`.
4. For single-symbol load APIs, output must be globally sorted by `timestamp` ascending.
5. Multi-symbol dataframes (if supported later) must be sorted by `(symbol, timestamp)`.

---

## 4) Invariants

For every row:
1. `low <= min(open, close)`.
2. `high >= max(open, close)`.
3. `high >= low`.
4. `volume >= 0`.
5. If non-null, `turnover_rate >= 0`.

For a continuous symbol/frequency series:
6. Timestamps must lie on valid calendar session anchors (see `docs/calendar_policy.md`).
7. No timestamps outside session windows for the market/frequency.

---

## 5) Null policy

- Required columns: no nulls except `turnover_rate` (temporary compatibility exception).
- Optional columns: nulls allowed.
- Rows violating required-null policy must fail strict validation.
- Non-strict validation may retain rows but must emit issue reports.

---

## 6) Symbol conventions

Phase 1 canonical symbol format:
- `NNNNNN.SZ` for Shenzhen listings.
- `NNNNNN.SH` for Shanghai listings.

Rules:
1. Symbols are uppercase.
2. Providers may accept other input forms, but adapters must normalize output to canonical form.
3. Canonical storage paths and manifests use canonical symbols only.

Out of scope for now:
- BJ exchange, indices, ETFs with alternate symbol conventions (to be added explicitly later).

---

## 7) Market conventions

- Initial market scope: CN A-share cash equities.
- Price fields are unadjusted raw prices in canonical layer.
- Corporate-action-adjusted views are separate derived datasets (see `docs/adjustment_policy.md`).

---

## 8) Frequency conventions

Allowed frequency ids in Phase 1:
- `1d` (daily)
- `30m` (intraday research baseline)

Rules:
1. Frequency id is part of dataset identity.
2. Timestamp anchor is **bar open** for all frequencies.
3. Daily bar timestamp uses local trading date at `09:30:00+08:00` as canonical open anchor.
4. Intraday bars must align to exchange session grid (including lunch-break discontinuity).

---

## 9) Metadata expectations

Each persisted dataset (file group/table) must include metadata fields (file-level manifest or sidecar):
- `dataset_id` (e.g., `cn_equity_1d_raw`)
- `market` (`cn_equity`)
- `frequency` (`1d`/`30m`)
- `timezone` (`Asia/Shanghai`)
- `timestamp_anchor` (`open`)
- `adjustment` (`raw`)
- `provider` or `provider_mix`
- `created_at_utc`
- `schema_version` (start at `1`)

---

## 10) Validation levels

- **Strict** (default for write path): enforce all required columns, uniqueness, ordering, invariants.
- **Permissive** (read-repair/debug only): permit limited null/ordering repair; must report all repairs.

This keeps extraction deterministic and prevents silent schema drift during migration.
