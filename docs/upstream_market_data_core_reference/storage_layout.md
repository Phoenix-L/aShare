# Storage Layout and Persistence Conventions

## Purpose
Define stable dataset layout for shared use across `market-data-core` and consumer repositories.

---

## 1) Storage layers

Three logical layers:

1. `raw/`
   - Provider-native or near-native extracts.
   - Used for traceability and reprocessing.
2. `canonical/`
   - Contract-compliant normalized bars (authoritative serving layer for Phase 1).
3. `curated/`
   - Derived datasets (adjusted, repaired, resampled feature-ready bars).

Rule: consumers should read from `canonical/` unless they explicitly need curated outputs.

---

## 2) Preferred file format

- Primary format: **Parquet**.
- Compression: `zstd` (preferred) or `snappy` fallback.
- Engine: `pyarrow`.

Reason:
- Columnar efficiency, interoperable across pandas/polars/spark.

---

## 3) Shared data root assumptions

Data root is externalized via environment/config:
- Preferred env: `MARKET_DATA_ROOT`
- Compatibility aliases (temporary): `ASHARE_CACHE_DIR`

Default (if unset): repository-local `.data/market_data` for development only.

Core package must not hard-code source-repo-relative paths.

---

## 4) Partitioning strategy

Canonical baseline partitioning:

`canonical/market=<market>/freq=<freq>/symbol=<symbol>/year=<yyyy>/part-*.parquet`

Example:
`canonical/market=cn_equity/freq=30m/symbol=000001.SZ/year=2026/part-000.parquet`

Rationale:
- Symbol-first locality for research loaders.
- Year partition to bound file sizes and append windows.

Daily datasets may also support coarser files per symbol-year.

---

## 5) Naming conventions

- Market ids: `cn_equity`.
- Frequency ids: `1d`, `30m`.
- Adjustment tag in curated datasets: `adj=<raw|qfq|hfq>`.
- Provider provenance field kept in metadata (`provider`, `provider_mix`).

---

## 6) Manifest and metadata expectations

Each dataset slice should expose machine-readable metadata (manifest file or metadata table), including:
- `dataset_id`
- `market`
- `frequency`
- `adjustment_mode`
- `schema_version`
- `timezone`
- `timestamp_anchor`
- `min_timestamp`
- `max_timestamp`
- `symbol_count`
- `row_count`
- `created_at_utc`
- `producer_version`

At minimum in Phase 1: per-write JSON sidecar manifest is acceptable.

---

## 7) Access patterns for consumer repos

Consumer repos should:
1. Depend on `market-data-core` access/load APIs rather than reading storage paths directly.
2. Pass `data_root` override only when non-default roots are required.
3. Treat layout as semi-internal; only documented dataset ids and APIs are contract-stable.

This allows layout evolution without breaking downstream systems.

---

## 8) Write semantics

- Writes are append-safe by partition.
- Rewrites should be explicit (`replace_partition=True`) and logged in manifests.
- Validation is mandatory before canonical writes.

---

## 9) Deferred/open decisions

- Whether to adopt Delta/Iceberg in later phases.
- Small-file compaction policy and schedule.
- Dataset catalog backend (filesystem manifests vs sqlite vs external metastore).

---

## 10) Phase 5 implementation notes

Implemented now in `market-data-core`:
- storage layout path builders for `raw/canonical/curated`,
- curated adjustment partition marker (`adj=<mode>`),
- dataset id helper (`<market>_<freq>_<adjustment>`),
- JSON sidecar manifest helpers (`build/write/read`),
- dataset listing and inspection APIs based on manifest discovery.

Current behavior:
- manifest payload is the contract carrier for dataset metadata at read/inspect boundaries,
- `inspect_dataset` returns the latest matching manifest by file modification time.
