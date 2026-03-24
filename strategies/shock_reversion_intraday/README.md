# shock_reversion_intraday

Event-driven intraday mean-reversion strategy for downside shock events.

This strategy detects downside excursions from a rolling close anchor, optionally gates entries by shock score, supports multi-leg ladder adds, and exits through a shared execution engine.

## Documentation map

- [strategy.md](./strategy.md) — trading logic and parameter semantics
- [architecture.md](./architecture.md) — component and data flow
- [usage.md](./usage.md) — experiment execution and output interpretation
- [research/shock_strength_model.md](./research/shock_strength_model.md) — scoring model formulas
