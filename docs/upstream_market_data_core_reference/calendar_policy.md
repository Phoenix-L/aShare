# Calendar and Timestamp Policy

## Purpose
Define deterministic time semantics for canonical market bars in `market-data-core`.

Primary scope: CN A-share (SSE/SZSE) daily and 30-minute bars.

---

## 1) Timezone policy

1. Canonical timezone is `Asia/Shanghai`.
2. All `timestamp` values in canonical data are timezone-aware and normalized to `Asia/Shanghai`.
3. API inputs may be date-only strings or timezone-naive datetimes; loaders normalize them to exchange-local boundaries.
4. UTC conversion is allowed only at API boundaries; storage remains exchange-local for clarity.

---

## 2) Timestamp anchor semantics

Canonical rule: `timestamp` represents **bar open time**.

Examples:
- Daily bar for 2026-04-10 → `2026-04-10 09:30:00+08:00`.
- 30m bar covering 10:00–10:30 → timestamp `10:00:00+08:00`.

Reason:
- Aligns with current aShare DataFrame orientation and avoids ambiguity in session-end handling.

---

## 3) CN A-share session structure

Expected continuous auction sessions:
- Morning: `09:30` to `11:30`
- Afternoon: `13:00` to `15:00`

Lunch break:
- No trading interval from `11:30` to `13:00`.
- No bars should be generated with open timestamps inside the break.

Pre-open/auction nuances are out of scope in Phase 1 canonical bars.

---

## 4) Intraday boundary expectations

For 30-minute bars, valid bar-open anchors are:
- `09:30`, `10:00`, `10:30`, `11:00`, `13:00`, `13:30`, `14:00`, `14:30`

Expected bar count per full trading day for `30m`: **8 bars**.

Invalid examples:
- `12:00` (lunch break)
- `15:00` as a 30m bar open

---

## 5) Holiday and non-trading-day assumptions

1. Trading calendar is exchange session calendar (SSE/SZSE business days).
2. No bars are expected for weekends and exchange holidays.
3. Canonical validation checks for impossible timestamps; exact holiday-calendar source abstraction may be pluggable.
4. If no formal calendar package is configured, provider-observed dates are accepted but flagged for calendar certainty level.

---

## 6) Missing bar policy

Missing bars are classified, not silently filled:
1. **Expected absence**: non-trading day or suspended symbol.
2. **Unexpected gap**: missing interval within an active session day.

Policy:
- Canonical raw storage does **not** forward-fill missing bars.
- Validation emits gap diagnostics.
- Optional repair/fill utilities can live in transform layer and must produce derived datasets.

---

## 7) Session alignment expectations

- All intraday bars must align to canonical session anchors for the frequency.
- Provider data with off-grid timestamps must be normalized or rejected.
- Daily and intraday datasets must share the same timezone and symbol conventions to allow deterministic joins.

---

## 8) 30m research-bar notes

1. 30m is a first-class Phase 1 frequency because it is used by existing research/backtest flows.
2. Resampling from finer bars to 30m must preserve lunch break discontinuity.
3. Any aggregation to daily from 30m must happen via explicit transform APIs, not engine-runtime side effects.
4. Future frequencies (`1m`, `5m`, `60m`) can be added once session-anchor grids are defined in this policy.

---

## 9) Deferred/open decisions

- Whether to store all timestamps physically in UTC while exposing exchange-local views.
- Whether to include call auction periods in canonical intraday datasets.
- How to encode half-day/special session events (rare in CN A-share but should be modelled explicitly if needed).

---

## 10) Phase 5 implementation notes

Implemented now in `market-data-core`:
- canonical 30m open-anchor set (`09:30, 10:00, 10:30, 11:00, 13:00, 13:30, 14:00, 14:30`),
- canonical daily open anchor (`09:30`),
- timezone coercion helper to `Asia/Shanghai`,
- session alignment checks used by `validate_bars(...)`,
- best-effort missing 30m anchor diagnostics per day.

Limitations retained intentionally:
- no exchange-holiday package integration yet,
- missing-bar checks are warning-oriented diagnostics and do not infer suspension vs holiday.
