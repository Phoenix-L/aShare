# shock_reversion_intraday

Event-driven intraday mean-reversion strategy for downside shock events.

## Core Idea

1. Detect a downside shock from close-vs-anchor excursion.
2. Enter and optionally ladder when continuation conditions pass.
3. Exit via anchor-based recovery or explicit risk controls.

## What’s Special

- Separate scoring paths: `entry_shock_score` vs `add_shock_score`.
- Ladder is constrained by **price + score + time spacing**.
- Recovery exit is anchor-based (**not** entry-price based).

## Documentation map

- [strategy.md](./strategy.md) — trading logic and parameter semantics
- [architecture.md](./architecture.md) — component and data flow
- [usage.md](./usage.md) — experiment execution and output interpretation
- [research/shock_strength_model.md](./research/shock_strength_model.md) — scoring model formulas
