# `market-data-core` Architecture

## Scope boundary

Owns:
- provider adapters
- canonical schema and validation
- cleaning/normalization
- calendar/session logic
- resampling and adjustment transforms
- storage/access APIs
- dataset inspection

Must not own:
- Backtrader integration
- strategy/signal logic
- experiment orchestration
- strategy diagnostics/reports
- regime detection and research workflow glue

---

## Target package boundaries

## `core/`
**Owns**
- Shared domain primitives: enums, IDs, typed config objects, result/report dataclasses.
- Error hierarchy (`ContractError`, `ProviderError`, `ValidationError`).

**Must not own**
- Provider SDK calls.
- Any storage or dataframe transformation implementation.

---

## `schema/`
**Owns**
- Canonical column definitions and schema versioning.
- Contract-level validators for required fields, types, uniqueness, ordering, invariants.

**Must not own**
- Provider-specific normalization.
- Calendar holiday resolution implementation details (delegates to `calendar/`).

---

## `providers/`
**Owns**
- Provider interface/ABC.
- Provider registry/factory.
- Concrete adapters (`baostock`, `tushare`) converting vendor payload to canonical dataframe.
- Provider auth/client helpers (e.g., tushare token client), once decoupled from repo-specific path logic.

**Must not own**
- Cache persistence.
- Strategy/research behavior.

---

## `ingest/`
**Owns**
- End-to-end fetch-normalize-validate-persist orchestration.
- Idempotent ingest execution and ingest result summaries.

**Must not own**
- Backtesting runtime operations.
- Research folder exports.

---

## `clean/`
**Owns**
- Deterministic data cleaning primitives (dtype normalization, duplicate handling policy, column standardization).

**Must not own**
- Inference-heavy/strategy-specific feature engineering.

---

## `calendar/`
**Owns**
- Session definitions, timestamp anchor policy, frequency session grids.
- Trading-day/session alignment checks.

**Must not own**
- Provider transport logic.

---

## `transform/`
**Owns**
- Session-aware resampling.
- Adjustment transforms (`raw/qfq/hfq`) and optional materialization helpers.

**Must not own**
- Strategy indicators/signals.

---

## `storage/`
**Owns**
- Physical persistence layout and read/write adapters.
- Manifest writing/reading.
- Partition routing.

**Must not own**
- Vendor API calls.
- Strategy/runtime concerns.

---

## `validation/`
**Owns**
- Public validation entrypoints and reports combining `schema/` + `calendar/` checks.
- Strict/permissive validation modes.

**Must not own**
- Data fetching or storage side effects.

---

## `access/`
**Owns**
- User-facing load/query APIs.
- Dataset inspection/listing APIs.
- Compatibility wrappers for legacy loader names during migration.

**Must not own**
- CLI formatting concerns.

---

## `cli/`
**Owns**
- Minimal operational commands for ingest/load/inspect intended for data platform operations.

**Must not own**
- aShare experiment or strategy workflows.

---

## Dependency direction (enforced)

Allowed high-level dependency flow:

`providers -> clean -> schema/calendar -> validation -> storage -> ingest/access -> cli`

Rules:
1. Lower layers cannot import higher layers.
2. `providers` must not import `storage`.
3. `access` may depend on `storage`, `validation`, `transform`, but not vice versa.
4. `cli` is outermost adapter only.

---

## Migration-aligned implementation priorities

Create first (non-placeholder):
1. `schema/`, `providers/`, `storage/`, `validation/`, `access/`

Create as light placeholders initially:
2. `clean/`, `calendar/`, `transform/`, `ingest/`, `cli/`

This sequencing supports extracting current `aShare` loader/provider/cache stack first without overbuilding.

---

## Phase 5 boundary hardening notes

Public/stable entry modules at this stage:
- `market_data_core.access`
- `market_data_core.validation`
- `market_data_core.calendar`
- `market_data_core.storage`
- `market_data_core.providers` (registry/boundary, not full adapter parity yet)

Still internal/unstable:
- `ingest/*` implementation details,
- `transform/*` implementation details,
- provider SDK client specifics pending final extraction.
