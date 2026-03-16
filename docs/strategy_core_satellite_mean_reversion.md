# Core–Satellite Mean Reversion Strategy Definition (Phase 0)

## Reference Context
This strategy definition aligns with the platform layering and research workflow described in `docs/system_architecture.md`.

## 1. Strategy Overview
The Core–Satellite Mean Reversion strategy is designed to **harvest short-term volatility** while preserving a **long-term strategic holding**. The strategy keeps a permanent core position invested and trades a separate satellite sleeve around that core when short-term dislocations appear.

## 2. Portfolio Structure
- **Core position (permanent):** 2000 shares
- **Satellite position (actively traded):** 0–2000 shares
- **Maximum total exposure:** 4000 shares

The portfolio is managed as two logical sleeves:
1. **Core sleeve** for long-term exposure, never sold by this strategy.
2. **Satellite sleeve** for tactical mean-reversion entries and exits.

## 3. Indicators
The strategy uses the following indicators:
- **MA20** (short-term trend anchor)
- **MA120** (long-term regime filter)
- **ATR14** (volatility normalization)
- **Z-score** (dislocation signal)

Z-score definition:

\[
Z = \frac{Price - MA20}{ATR}
\]

Notes:
- ATR is used as a scale normalizer so entry/exit thresholds are comparable across volatility regimes.
- MA120 is used as a trend guardrail to avoid deploying satellite risk in weak long-term conditions.

## 4. Entry Logic
Buy satellite shares when:
- \( Z \leq -1.5 \)
- **AND** \( Price > MA120 \)

Scale-in tiers:
- Add when \( Z \leq -2.0 \)
- Add when \( Z \leq -2.5 \)

Execution unit:
- **Position increment:** 500 shares per entry trigger
- **Maximum satellite size:** 2000 shares

Interpretation:
- Initial entry captures moderate mean-reversion opportunities.
- Deeper negative Z-score levels allow controlled averaging into larger dislocations.

## 5. Exit Logic
Reduce satellite exposure when mean reversion materializes:
- **Sell 500 shares** when \( Z \geq 0.8 \)
- **Close all remaining satellite shares** when \( Z \geq 1.5 \)

Core sleeve behavior:
- The 2000-share core position is not reduced by exit logic.

## 6. Risk Controls
- **Satellite maximum exposure:** 2000 shares
- **Core position never sold** by strategy logic
- **Regime pause rule:** pause new satellite trading if \( Price < MA120 \)

Implementation expectations:
- Enforce hard caps on satellite sizing.
- Prevent accidental overlap between core and satellite accounting.

## 7. Strategy Goals
1. **Harvest short-term volatility** through disciplined mean-reversion execution.
2. **Maintain long-term market exposure** with a permanent core sleeve.
3. **Limit behavioral trading errors** using fixed, pre-declared rules.

## 8. Future Enhancements
Potential extensions after Phase 0 architecture alignment:
- Volatility regime switching
- Volume filters
- Sector momentum filter
