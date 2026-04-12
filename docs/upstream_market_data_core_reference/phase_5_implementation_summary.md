# Phase 5 implementation summary

Upstream reference: copied from [`Phoenix-L/market-data-core`](https://github.com/Phoenix-L/market-data-core) for `aShare` documentation. Content below is derived from that repository’s `README.md` (current phase) and `docs/migration_blueprint.md` (§11).

---

## Current phase (from upstream README)

`market-data-core` is in **Phase 5 (wave 2 expansion + contract tightening)**.

### Implemented and stable for consumers

- Canonical bar schema constants and validation entrypoint.
- CN A-share session anchor helpers and alignment checks.
- Provider registry boundary with compatibility env behavior.
- Storage layout/manifests helpers and dataset inspection APIs.
- Load API boundary (`load_bars`, `load_daily`, `load_30m`, `load_minute_30`).

### Still intentionally deferred (upstream)

- Concrete BaoStock/Tushare SDK adapters.
- Ingest orchestration pipelines.
- Full transform layer (`resample`, `adjust`) implementation.

---

## Phase 5 progress note (from upstream migration_blueprint §11)

### Implemented in Phase 5

- Calendar/session helpers extracted and implemented for CN A-share anchor semantics (`1d`, `30m`) and timezone normalization.
- Validation now includes calendar session alignment checks and missing-30m-anchor diagnostics.
- Storage semantics tightened with layer-aware partition builders, dataset id helper, and typed manifest sidecars.
- Dataset inspection APIs (`list_datasets`, `inspect_dataset`) implemented using manifest discovery.
- Public API boundaries documented as Phase 5 stable in `docs/public_api_draft.md`.

### Deferred to later phases

- Concrete provider adapter extraction parity (BaoStock/Tushare implementation details).
- Ingest orchestration (`ingest_bars`) and transform layer (`resample`, `adjust`) production implementation.
- Holiday-calendar certainty classification beyond best-effort diagnostics.

### Consumer impact notes

- No breaking changes to Phase 4 load API signatures (`load_daily`, `load_30m`, `load_minute_30`).
- Validation is stricter for session misalignment; consumers should ensure intraday timestamps match canonical open anchors.
- Dataset inspection is now manifest-driven; consumer repos should treat manifest fields as primary metadata contract.
