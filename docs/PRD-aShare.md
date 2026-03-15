# PRD
## Personal A-Share Algorithmic Trading System

Version: v1.0
Owner: Hai Tian
Project: **aShare Quant Research Platform**

---

# 1. Product Overview

## 1.1 Product Vision

Build a **personal quantitative research and trading laboratory for the Chinese A-share market** that allows an individual investor to:

* rapidly prototype trading strategies
* evaluate strategies using realistic market data and constraints
* iterate strategies efficiently through automated backtesting

The system initially focuses on **one strategy, one instrument, and one market** to maximize research clarity and execution discipline.

The platform prioritizes:

* **fast research iteration**
* **transparent performance evaluation**
* **modular extensibility**

At the current stage, the system functions as a **quantitative research infrastructure**, not a live trading platform.

---

# 2. Target Users

Primary user:

**Individual quantitative trader**

User characteristics:

* comfortable with Python programming
* familiar with command-line workflows
* focuses on strategy research and hypothesis testing
* operates independently without institutional infrastructure

User goals:

* discover profitable trading strategies
* validate ideas quickly
* evaluate risk and return characteristics
* track and refine strategy experiments

---

# 3. Product Scope

## 3.1 In Scope (Phase 1)

Core research capabilities:

* market data ingestion
* historical backtesting
* strategy development framework
* performance evaluation metrics
* experiment iteration

---

## 3.2 Out of Scope (Phase 1)

The following features are intentionally excluded in the first phase:

* live order execution
* broker API integration
* distributed computation
* cloud infrastructure deployment

These may be considered in later phases.

---

# 4. System Goals

The system should enable the user to:

### G1 — Rapid Strategy Development

Develop and test new strategies with minimal setup.

### G2 — Reproducible Backtests

Ensure backtest results are deterministic and reproducible.

### G3 — Strategy Comparison

Evaluate multiple parameter variations of a strategy.

### G4 — Research Efficiency

Minimize friction between **idea → experiment → insight**.

### G5 — Architecture Longevity

Maintain an architecture capable of evolving into a more advanced trading platform.

---

# 5. Functional Requirements

## 5.1 Data Layer

Supported data providers:

* BaoStock
* Tushare

Supported data types:

* Daily OHLCV
* Intraday OHLCV
* Liquidity metrics (turnover_rate)

Capabilities:

* unified data schema
* provider abstraction layer
* symbol normalization
* API error handling

Future extensions:

* local historical data cache
* Parquet-based storage
* data integrity checks

---

## 5.2 Strategy Framework

The system must support:

* modular strategy files
* parameterized strategies
* strategy registry
* CLI-based execution

Example usage:

```
ashare backtest \
--symbol 600519.SH \
--strategy mid_freq_ma \
--start 2024-01-01 \
--end 2025-01-01
```

Strategies must support:

* technical indicators
* signal generation
* position sizing
* market constraints

---

## 5.3 Backtesting Engine

The system must provide:

* backtesting orchestration
* configurable capital
* realistic transaction cost model
* slippage modeling
* analyzer integration

Engine responsibilities:

* initialize simulation environment
* attach strategies and analyzers
* execute simulation
* extract performance metrics

---

## 5.4 Market Constraints

The system must incorporate A-share market rules such as:

* 100-share lot size
* stamp duty on sell orders
* T+1 settlement restrictions (future)
* daily price limit rules (future)

---

## 5.5 Performance Metrics

The system must produce core metrics:

* total return
* Sharpe ratio
* maximum drawdown
* trade statistics

Recommended additional metrics:

* win rate
* profit factor
* annualized volatility
* turnover ratio

---

## 5.6 Output and Reporting

Each backtest run should produce:

Console output:

* summary performance metrics

Artifacts:

```
outputs/
    equity_curve.csv
    trades.csv
    metrics.json
    plot.png
```

Logging:

```
logs/
    run_YYYYMMDD.log
```

---

# 6. Non-Functional Requirements

## 6.1 Performance

Backtests should complete within seconds for:

* single instrument
* <5 years of historical data
* minute or daily resolution

---

## 6.2 Reliability

The system must:

* fail fast when data is invalid
* validate CLI parameters
* log run metadata

---

## 6.3 Maintainability

Architecture must remain:

* modular
* testable
* extensible

---

# 7. User Workflow

Typical research workflow:

```
Idea
 ↓
Implement strategy
 ↓
Run backtest
 ↓
Analyze results
 ↓
Adjust parameters
 ↓
Run next experiment
```

The CLI serves as the primary interface.

---

# 8. Architecture Alignment

This PRD aligns with the system architecture layers:

| PRD Domain        | Architecture Layer |
| ----------------- | ------------------ |
| CLI Interface     | CLI                |
| Config Management | Configuration      |
| Data Ingestion    | Data Layer         |
| Strategy Logic    | Strategy Layer     |
| Simulation        | Backtest Engine    |
| Market Rules      | Constraints        |
| Metrics           | Analyzer Layer     |

This layered architecture ensures clear responsibility boundaries.

---

# 9. Future Roadmap

## Phase 1 — Research Infrastructure

Focus:

* stable backtesting
* reliable market data
* strategy experimentation

---

## Phase 2 — AI-Assisted Research

Introduce AI to enhance research capabilities:

* pattern discovery from historical data
* strategy parameter optimization
* feature discovery
* automated experiment analysis

AI will assist **research**, not replace human decision-making.

---

## Phase 3 — Advanced Research Platform

Potential extensions:

* multi-symbol portfolio simulation
* strategy batch testing
* experiment tracking
* walk-forward validation
* research report generation

---

# 10. Success Metrics

The platform is successful if it enables:

* ≥10 strategies implemented
* reproducible backtests
* reliable performance metrics
* efficient research workflow

---

# 11. Risks

### Data Quality Risk

External data provider APIs may change or become unreliable.

### Strategy Overfitting

Backtests may overfit historical data without proper validation.

### Metric Misinterpretation

Incorrect performance metrics could lead to misleading conclusions.

---
