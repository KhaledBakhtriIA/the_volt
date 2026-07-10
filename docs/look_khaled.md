# LOOK KHALED - System Architecture Reference

**Date:** 2026-03-31  
**Author:** Engineering Team  
**Type:** Technical Reference  
**Audience:** Engineering, QA, DevOps  
**Status:** Batch analytics platform with real-time infrastructure bootstrap and experimental trading components

---

## 1. System Overview & Honest Assessment

**The Volt System** is a **batch data collection and enrichment platform** with experimental scaffolding for stream processing and trade execution. It is production-ready for offline analytics workflows (dataset generation, model training) but **not yet battle-tested for live trading**.

### What This System Does Well
- Multi-source ingest (10 collectors) with graceful fallback
- Schema normalization, statistical quality gates, and financial-domain checks
- Idempotent orchestration with run-state persistence
- Testable (176 passing tests)
- Deployable via Docker

### What This System Cannot Yet Do
- Fully automated broker-connected live decisioning (consumer path is wired; live broker adaptor pending)
- Live broker integration (execution gateway is paper-only)
- Full market microstructure validation (bid/ask integrity, corporate actions)
- Production-grade drift governance (currently threshold-based)

### Core Data Pipeline (Simplified)
```
Collectors (10 sources) → API (FastAPI) → Feature Store (domain + statistical QC, parquet-backed) → Orchestrator → Exports
```

**Current maturity estimate:**
- **Batch data ops (collection → export):** ~85% complete — core pipeline + parquet history proven in use
- **Stream processing (live ingest):** ~65% complete — queue/cache runtime scaffold plus always-on consumer integration implemented
- **Retraining automation:** ~50% complete — drift-based trigger + statistical alpha validation implemented
- **Live execution:** ~45% complete — paper broker + risk models + execution strategies (TWAP) implemented
- **Overall:** 65% complete if you weight trading-relevant features, 85% if you weight data ops

---

## 2. Data Collection & Validation Layer

### 2.1 Collectors (data_api/collectors/)

**10 active sources:**
- `market_collector.py` (OHLCV)
- `stock_market_collector.py` (equity tickers)
- `news_collector.py` (articles)
- `browser_collector.py` (web snapshots)
- `reddit_collector.py` (social)
- `macro_collector.py` (FRED)
- `desktop_collector.py` (local)
- `trading_strategy_collector.py` (signals)
- `trading_mistakes_collector.py` (trade logs)
- `finance_query_stream.py` (streaming config)

**Error handling:** Graceful fallback to empty frames on credential/provider failure. Logged with source context.

### 2.2 API Layer (data_api/app.py)

**Framework:** FastAPI + dependency injection

**Endpoints:**
- `POST /collect/{source}` — Single collector
- `POST /collect/full` — All collectors
- `POST /process/sentiment` — Single-text sentiment scoring
- `GET /datasets/latest` — Latest export
- `GET /health` — Status check
- `GET /paper/pnl` — Paper trading realized PnL snapshot
- `POST /paper/close/{trade_id}` — Close virtual trade at provided exit price

**Input validation:** Pydantic request contracts at FastAPI boundaries with field-level 422 responses on invalid payloads.

### 2.3 Data Quality Validation: What It Does (And Doesn't)

This is the **honest assessment** of the current validation approach:

#### What the System Checks

**Stage 1: Schema (Basic)**
- Required columns present?
- Dataframe is not None/empty?
→ **Fails fast if columns missing**

**Stage 2: Type Coercion (Lossy)**
- Timestamps → UTC datetime (errors → NaT)
- Numerics → float64 (errors → NaN)
- Drops rows with >50% missing fields
- Drops exact duplicates
→ **Cleans obvious corruptions**

**Stage 3: Statistical Outliers (Limited)**
- Computes Z-score across numeric columns
- Flags rows where |Z| > 4.0 on any feature
- Reports outlier_ratio; fails if >15%
→ **Catches gross statistical anomalies**

**Stage 4: Financial Domain Guardrails (Implemented)**
- Stale feed detection per symbol (10+ identical close rows while volume > 1000)
- Market-hour gap detection for stocks (>5 minutes during NY market session)
- Price precision policy for stocks (>6 decimal places flagged)
- Non-positive OHLC price detection
→ **Catches stale feeds, missing intraday intervals, and obvious price-format anomalies**

#### What the System **Does NOT** Check

⚠️ **Partial trading-hour awareness only:**
- Detects large timing gaps for stock data, but does not model session exceptions deeply
- Detects stale close runs, but not all quote staleness patterns

⚠️ **No exchange-level validation:**
- Does not verify split adjustments
- Does not check bid-ask spread sanity
- Does not flag halts, limit-ups, or regulatory events
- Cannot detect synthetic/replayed trades

⚠️ **Z-score threshold is arbitrary:**
- 4.0 chosen for statistical rarity (~99.996% CI)
- In financial data, many legitimate events sit at Z = 3-5 (earnings gaps, splits, halts)
- Misses microstructure noise and stale data that sit within Z = 2-3
- No per-symbol volatility adjustment; treats stable stocks same as crypto

⚠️ **Domain logic remains incomplete:**
- Price precision and non-positive price checks are implemented
- Bid/ask consistency and corporate-action validation are still missing
- Volume sanity is rule-based, not statistically calibrated per venue/symbol

#### Configuration Thresholds

```python
MAX_MISSING_RATIO = 0.20           # 20% of cells can be NaN
MAX_DUPLICATE_RATIO = 0.10         # 10% duplicate rows allowed
MAX_OUTLIER_RATIO = 0.15           # 15% Z-score outliers allowed
OUTLIER_Z_THRESHOLD = 4.0          # Statistical Z-score
```

**These are not validated against domain data.** They should be tuned against historical ingest runs to measure false-positive rejection rates.

### 2.4 Quality Report Output

```python
QualityReport {
  "passed": bool,                    # Master gate (all thresholds met?)
  "total_rows": int,                 # Before cleaning
  "rows_after_cleaning": int,        # Duplicates/null rows removed
  "schema_valid": bool,              # Required columns present?
  "missing_ratio": float,            # NaN cells / total cells
  "duplicate_ratio": float,          # Duplicate rows / total
  "outlier_ratio": float,            # |Z| > 4.0 / total
  "issues": [string, ...]            # Specific failures
}
```

**Decision logic in orchestrator:**
```python
if quality.passed:
    continue_pipeline()
elif strict=True:
    raise DataQualityError(quality.issues)
else:
    proceed_with_warning(quality)
```

### 2.5 Validation Limitations: Honest Risks

**Risk: False negatives in stale detection**
- Current stale rule keys on repeated close + volume threshold
- Some stale patterns can still pass if they do not meet the exact heuristic
- **Mitigation needed:** Multi-field quote freshness logic (bid/ask/last-update triangulation)

**Risk: Microstructure noise**
- Bid-ask bounce, last-sale latency, crossed quotes
- Z-score threshold of 4 will pass through noise spikes at Z = 2-3
- **Mitigation needed:** Per-exchange volatility bands, bid-ask validation

**Risk: Corporate action blindness**
- Stock split data arrives as OHLCV adjustment
- System does not know if adjustment is applied or pending
- May retroactively receive pre-split prices
- **Mitigation needed:** Explicit corporate action tracking, timestamp drift detection

**These gaps do not doom offline analytics.** But they **must** be addressed before live decision-making.

---

## 3. Directory Structure & Responsibilities

```
the_volt_system/
├── core/
│   ├── config.py
│   └── contract.py
│
├── src/brain/                         [PRODUCTION: Pure math & logic]
│   ├── features.py                    Rolling calcs
│   ├── trading_math.py                [NEW] Kelly, Alpha Edge, Drawdown calcs
│   └── __init__.py
│
├── data_api/                          [PRODUCTION: Batch collection pipeline]
│   ├── app.py                         FastAPI entrypoint
│   ├── collectors/                    10 data source modules
│   ├── processors/                    Sentiment + technical indicators
│   ├── jobs/                          Batch orchestration (pipeline, run_production, retention)
│   ├── config/settings.py             Environment-driven config
│   ├── storage/file_store.py          Timestamped file management
│   ├── exceptions.py                  Context-aware exception hierarchy
│   └── data/{raw,processed,exports,refined}/
│
├── src/canonical/                     [EXPERIMENTAL: Stream + execution scaffolding]
│   ├── orchestrator.py                [STABLE] Idempotent step runner
│   ├── feature_store_engine.py        [STABLE] Validation + QC
│   ├── model_registry.py              [STABLE] SQLite model registry + approval gate support
│   ├── prediction_error_monitor.py    [STABLE] Rolling MAE/RMSE/directional error tracking
│   ├── reliability.py                 [STABLE] Retry + circuit breaker
│   ├── healing_ledger.py              [STABLE] Audit trail
│   ├── supervisor.py                  Health scoring
│   ├── stream_worker.py               [EXPERIMENTAL] Stream processing scaffold
│   ├── realtime_runtime.py            [EXPERIMENTAL] Tick schema + queue/cache/decision loop + always-on consumer runtime
│   ├── risk_management.py             [STABLE] Portfolio Risk Model (Kill-switch, Kelly sizing)
│   ├── execution_strategy.py          [STABLE] Execution Strategies (Market, TWAP)
│   ├── execution_gateway.py           [STABLE] Trade execution gateway (Risk-integrated)
│   ├── meta_controller.py             [EXPERIMENTAL] Self-healing orchestration
│   ├── learning_loop.py               [PARTIAL] Drift-based retraining trigger
│   ├── drift_detector.py              [PARTIAL] KS + PSI drift monitor
│   ├── paper_broker.py                [PARTIAL] SQLite paper trading ledger
│   └── predictive_models.py           Model abstractions
│
├── tests/
│   └── 176 passing tests (collectors, processors, pipeline, reliability, drift, paper broker, API validation, settings, exceptions, realtime runtime, trading math, risk, execution strategy)
│
└── documentation/
    └── Architecture, policy, performance docs
```

**Legend:**
- `[STABLE]` — Battle-tested, used in production export jobs
- `[EXPERIMENTAL]` — Scaffolding, not yet integrated with live infrastructure

---

## 4. Stream Processing & Retraining (Experimental, Partially Validated)

### 4.1 Stream Worker Scaffolding (stream_worker.py, learning_loop.py)

**Current state:** Configuration templates exist. No live event queue infrastructure.

**Components:**
- `stream_worker.py` — Consumer stub for real-time data
- `learning_loop.py` — Drift-aware retraining trigger (threshold based)
- `meta_controller.py` — Self-healing orchestration wrapper

### 4.2 Drift-Based Retraining Trigger (Implemented, Needs Hardening)

**Current trigger logic (learning_loop.py):**
```python
drift_result = detector.detect(batch_df)
if number_of_drifted_features >= 3:
    trigger_model_retraining()
```

**What improved:**
- Retraining no longer depends on file count under normal operation
- Drift detection uses KS two-sample test + PSI per numeric feature
- Trigger requires at least 3 drifted features
- Drift summary is logged before retraining

**Residual risks:**
1. Thresholds are static and not strategy-specific
2. Reference baseline quality determines trigger quality
3. Drift does not yet include live prediction error feedback

**Status:** Suitable for controlled batch retraining workflows, not sufficient alone for live-capital governance.

### 4.3 Model Hot-Swap Concurrency (Implemented in Orchestrator)

**Current implementation (model_registry.py, orchestrator.py):**
```python
loaded = joblib.load(file_path)
with self._model_lock:
    self._active_models[model_name] = (version_uuid, loaded)
```

**Predict pinning pattern:**
```python
with self._model_lock:
    model = self._active_models[model_name][1]
result = model.predict(X)
```

**Status:** Concurrency hazard reduced for in-process swaps; still requires broker/runtime-level controls for live deployment.

---

## 5. Batch Pipeline Flow (Collection → Export)

### 5.1 Collection Phase

**Entry Points:**
- `POST /collect/full` → `data_api.jobs.pipeline.py`
- `python -m data_api.jobs.run_production` (CLI, notebook-free)

**Steps:**
1. Instantiate 10 collectors with shared auth
2. Parallel collect from all sources
3. Normalize outputs via `collector_contract.py`
4. Concatenate into single DataFrame
5. Write raw CSV/Parquet to `data/raw/`

**Output:** `raw_{timestamp}.csv`

### 5.2 Feature Store & Validation

**Entry:** Raw DataFrame → `orchestrator.preprocess_features(raw_df, strict=True)`

**Chain:**
```
Raw DataFrame
    ↓
[1] Schema Check: Required columns?
    ↓
[2] Type Coercion: datetime, numeric (errors → NaN/NaT)
    ↓
[3] Deduplication & Row Cleanup
    ↓
[4] Financial Domain Guardrails
    ↓
[5] Outlier Detection (Z-score)
    ↓
[6] QualityReport + Parquet batch append
    ↓
Cleaned DataFrame + QualityReport
```

**If `quality.passed = True` → Continue to processors**  
**If `quality.passed = False` and `strict=True` → Abort and raise error**

### 5.3 Processor Phase (Optional)

**Modules:**
- `sentiment.py` — VADER sentiment scoring
- `technical_indicators.py` — RSI, MACD, Bollinger bands

**Conditional:** Only applied if config flags enabled.

### 5.4 Orchestration & Export

**Engine:** `orchestrator.py`

**Pattern:** Idempotent step markers with persisted run state.

```python
run_state = {
  "run_id": "export_20260331T143000Z",
  "steps": {
    "step_1_data": {"status": "COMPLETED", "result": {...}},
    "step_2_process": {"status": "COMPLETED", "result": {...}},
    ...
    "step_7_export": {"status": "COMPLETED", ...}
  }
}
```

**Key property:** If step already COMPLETED, return cached result. If fails, don't update state → can retry safely.

**Outputs:**
- `exports/{run_id}/report.json` — Metrics, summary
- `exports/{run_id}/models.json` — Model metadata
- `exports/{run_id}/run.log` — Execution log
- `model_registry.db` — SQLite registry

---

## 6. Stable Control Plane Components (Proven Patterns)

### 6.1 Orchestration & Reliability

| Module | Purpose | Status |
|--------|---------|--------|
| `orchestrator.py` | Idempotent step execution, run state persistence | STABLE |
| `model_registry.py` | SQLite-backed model versioning | STABLE |
| `healing_ledger.py` | Audit trail for self-healing actions | STABLE |
| `reliability.py` | Retry policies, circuit breakers | STABLE |
| `supervisor.py` | Health scoring (NORMAL/DEGRADED/HALT) | STABLE |

### 6.2 Validation & Feature Engineering

| Module | Purpose | Status |
|--------|---------|--------|
| `feature_store_engine.py` | Schema validation, financial guardrails, outlier detection, parquet persistence | STABLE (with caveats) |
| `feature_engineer.py` | Feature generation | STABLE |
| `predictive_models.py` | Model abstractions | STABLE | 
| `xgb_optuna_pipeline.py` | Training utilities | STABLE |

**Code is testable and passes 164 tests.**

---

## 7. Testing & Quality Assurance

### 7.1 Test Coverage

**164 tests passing:**
- `test_app.py` – API contracts
- `test_collectors.py` – Multi-source collection
- `test_feature_store_engine.py` – Validation & QC (important to review)
- `test_pipeline_*.py` – End-to-end batch workflows
- `test_reliability.py` – Retry, circuit breaker, supervisor
- `test_processors.py` – Sentiment, technical indicators
- `test_drift_detector.py` – KS/PSI + leakage checks
- `test_paper_broker.py` – paper execution + pnl + close lifecycle
- `test_api_validation.py` – strict input contract validation (422/200 behavior)
- `test_settings.py` – frozen settings + env loading
- `test_exceptions_hierarchy.py` – context-aware exception behaviors
- `test_prediction_error_monitor.py` – rolling model error summary and degradation detection
- `test_model_approval_gate.py` – human approval enforcement before model activation
- `test_realtime_feature_cache.py` – low-latency cache state and feature vector behavior
- `test_realtime_decision_loop.py` – tick consumer loop scoring + settlement path
- `test_realtime_runtime_service.py` – always-on realtime consumer lifecycle

**Test execution:**
```bash
pytest -v                    # All tests
pytest tests/test_feature_store_engine.py -v   # Focus on validation
```

### 7.2 Validation Test Patterns

**Schema rejection:**
```python
# Missing required column → DataQualityError
with pytest.raises(DataQualityError):
    engine.process(df_missing_columns, strict=True)
```

**Outlier flagging:**
```python
# High outlier ratio → quality.passed = False
quality = engine.process(df_with_outliers, strict=False)
assert quality.passed == False
assert quality.outlier_ratio > 0.15
```

**Idempotency:**
```python
# Running same step twice returns cached result
result1 = orchestrator._run_step_once(run_state, "step_1", fn)
result2 = orchestrator._run_step_once(run_state, "step_1", fn)
assert result1 == result2
```

---

## 8. Configuration & Deployment

### 8.1 Environment Variables

**Core:**
- `DATA_API_PORT` — Server port (default 8001)
- `DATA_API_EXPORTS_ROOT` — Export directory
- `DATA_API_ARCHIVE_ROOT` — Archival directory

**Collectors:**
- `ENABLE_BROWSER_COLLECTOR`, `ENABLE_REDDIT_COLLECTOR`, `ENABLE_MACRO_COLLECTOR`
- `FRED_API_KEY` — FRED credentials
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` — Reddit OAuth

**Feature Store (Quality Thresholds):**
- `DATA_API_MAX_MISSING_RATIO` — Default 0.20
- `DATA_API_MAX_OUTLIER_RATIO` — Default 0.15
- `DATA_API_OUTLIER_Z_THRESHOLD` — Default 4.0

**Job Behavior:**
- `DATA_API_RETENTION_DRY_RUN` — Test mode
- `DATA_API_RETENTION_ARCHIVE_DAYS` — Archive threshold (default 30)
- `DATA_API_RETENTION_DELETE_DAYS` — Deletion threshold (default 90)

### 8.2 Docker Deployment

```bash
# Build and run
DATA_API_PORT=8001 docker-compose up -d

# Check logs
docker-compose logs volt-data-api

# Health check
curl http://localhost:8001/health
```

### 8.3 Data Retention Policy

**Job:** `data_api/jobs/data_retention.py`

**Modes:**
- `dry-run` — Audit deletions (no changes)
- `archive` — Move old files
- `prune` — Delete archived files past retention window

**Policy:**
- Keep 30 days in active storage
- Archive 30-90 days
- Purge >90 days

---

## 9. Maturity Assessment & Known Limitations

### 9.1 Production-Ready Components

- **data_api/** → Stable batch pipeline (collection + export)
- **src/canonical/orchestrator.py** → Idempotent step runner (proven)
- **src/canonical/feature_store_engine.py** → Validation engine (proven)
- **src/canonical/model_registry.py** → Model versioning (proven)
- **data_api/exceptions.py** → Typed exception hierarchy with context payloads
- **data_api/config/settings.py** → Immutable runtime settings (`frozen=True`)
- **tests/** → 164 tests, all passing

### 9.2 Experimental Components (Partial / Unvalidated)

- **src/canonical/stream_worker.py** → Buffer/flush worker exists; primary realtime path now scaffolded via queue/cache runtime module
- **src/canonical/learning_loop.py** → Drift-based trigger implemented; governance still basic
- **src/canonical/drift_detector.py** → Statistical drift implemented; no strategy-aware calibration
- **src/canonical/execution_gateway.py** → Order contracts only, no live broker
- **src/canonical/paper_broker.py** → Simulated fills only, no external venue execution

### 9.3 Data Validation Assessment

**What system DOES check:**
- Schema validation (required columns present)
- Type coercion (timestamps→UTC, numerics→float64)
- Missing ratio (NaN cells / total cells)
- Duplicate ratio (duplicate rows / total rows)
- Outlier ratio (|Z-score| > 4.0)
- Stale feed runs (repeat close + active volume)
- Stock market-hour gaps
- Precision violations and non-positive prices

**What system DOES NOT check:**
- Quote freshness from exchange heartbeat/sequence data
- Bid-ask spreads or inverted quotes
- Stock splits or corporate actions
- Market halts or trading suspensions
- Volume anomalies (vs. baseline)
- Data source sanity (wrong ticker in response, swapped columns)

### 9.4 Retraining Risk Assessment

**Current trigger (PARTIALLY VALIDATED):**
```
if drifted_features >= 3:
    trigger_retrain()
```

**Remaining problem:**
Model error monitoring now exists, but retraining and activation policies are not yet fully coupled to streaming SLO/latency governance.

**What should trigger retrain:**
- Prediction error on hold-out set increases >10%
- Feature distributions shift (KS test p < 0.05)
- Population stability index (PSI) > threshold
- Explicit user signal or schedule

**Current gate status:** Prediction-error monitoring, approval policy, and always-on consumer runtime are implemented; remaining blocker is broker-grade execution and risk governance.

---

## 10. Roadmap: Path to Safe Live Trading

**Current state:** Batch analytics platform with experimental trading scaffolding.

### 10.1 Completed in Current Update

1. Domain-aware validation in `feature_store_engine.py` (stale feed, market gaps, precision, non-positive price)
2. Drift detector module with KS + PSI and drift-based retraining trigger
3. Model UUID tracking and lock-based hot-swap in orchestrator
4. Paper broker and API endpoints for PnL and close operations
5. Parquet-backed offline feature store with history loading
6. Prediction error monitoring with rolling MAE/RMSE/directional-accuracy degradation summaries
7. Human approval gate support for model activation (`REQUIRE_HUMAN_APPROVAL`)
8. Real-time infrastructure bootstrap: Redpanda + Redis + realtime runtime scaffold
9. Alpha validation math (Kelly, Expectancy edge)
10. Portfolio Risk Model (Global drawdown kill-switch, dynamic sizing)
11. Execution Strategies (TWAP order slicing)

### 10.2 Short-term (Week 3-4)

4. **Calibrate drift thresholds and alerts**
    - Validate KS/PSI cutoffs against historical drift windows
    - Add alert severity levels and suppressions

5. **Validate feature contract** (core/contract.py)
   - Finalize BASE_IDENTIFIERS, REQUIRED_FEATURES
   - Add dtype enforcement
   - Document provenance (where each feature comes from)

6. **Integrate paper broker with strategy execution path**
    - Route order intents through `execution_gateway.py` into paper broker
    - Persist strategy/model identifiers for post-trade attribution

### 10.3 Medium-term (Week 5-8)

7. **Online feature serving and version lookup**
    - Add low-latency online store (Redis/Feast-style) for inference paths
    - Feature versioning with lookup by `(feature_name, version, timestamp)`
    - Backfill tooling for historical features

8. **Real-time stream processing hardening**
    - Apply same validation gates as batch in streaming path
    - Add stream lag/throughput/freshness telemetry and SLOs
    - Promote scaffolded Redis feature cache to production serving mode

9. **Live execution integration**
   - Wire execution_gateway.py to actual broker API
   - Add pre-trade checks (position limits, max loss)
   - Full audit trail (order_id → feature_version → model_version)

### 10.4 Long-term (Month 2+)

10. **End-to-end autonomous operation**
    - Live data → real-time feature → prediction → order → execution
    - Fully observable (logs, metrics, traces)
    - Rollback procedures for model/strategy failures

---

## 11. Reference: Data Validation Implementation

### 11.1 Current Flow (feature_store_engine.py)

```python
def process(df, dataset, strict=True):
    # 1. Schema check
    schema_valid, issues = self._validate_schema(df)
    if not schema_valid and strict:
        raise DataQualityError(f"Schema failed: {issues}")
    
    # 2. Type coercion
    df = self._coerce_types(df)
    
    # 3. Financial domain checks
    issues.extend(_validate_financial_domain(df, asset_type))

    # 4. Cleaning
    df_clean = self._clean(df)
    rows_before = len(df)
    rows_after = len(df_clean)
    
    # 5. Outlier detection
    outlier_ratio = self._detect_outlier_ratio(df_clean)
    
    # 6. Quality report + parquet append
    report = QualityReport(
        total_rows=rows_before,
        rows_after_cleaning=rows_after,
        outlier_ratio=outlier_ratio,
        missing_ratio=...,
        duplicate_ratio=...,
        passed=(all thresholds met),
        issues=[...],
    )
    
    return df_clean, report
```

### 11.2 Configuration Thresholds (Unvalidated)

| Threshold | Default | Status |
|-----------|---------|--------|
| max_missing_ratio | 0.20 | Not validated against historical data |
| max_duplicate_ratio | 0.10 | Not validated against ingest logs |
| max_outlier_ratio | 0.15 | Not validated against domain events |
| outlier_z_threshold | 4.0 | Statistical; not financial |

**Action required before production:** Tune these against 6+ months of real data to measure false-positive rejection rates.

### 11.3 Quality Metrics Explanation

**missing_ratio:** NaN cells / total cells  
→ Detects network failures, API timeouts  
→ Does NOT detect stale data

**duplicate_ratio:** Duplicate rows / total rows  
→ Detects retry storms, kafka redelivery  
→ Does NOT detect synthetic data injection

**outlier_ratio:** (|Z| > 4.0) rows / total rows  
→ Detects gross statistical anomalies  
→ Does NOT detect earnings gaps, splits, halts (which are legitimate)

**schema_valid:** All required_columns present  
→ Detects partial ingest failures  
→ Does NOT detect wrong data in right columns

---

## 12. Quick Start

### 12.1 Run Batch Collection & Export

```bash
# Activate environment
. .venv/Scripts/activate

# Trigger full collection pipeline
python -m data_api.jobs.run_production

# Check output
ls data_api/data/exports/
cat data_api/data/exports/latest/report.json
```

### 12.2 Run Tests

```bash
# All tests
pytest -v

# Feature store validation only
pytest tests/test_feature_store_engine.py -v

# Pipeline integration
pytest tests/test_pipeline_feature_store_harmony.py -v

# Input validation contracts
pytest tests/test_api_validation.py -v
```

### 12.3 Run API Server

```bash
# Start FastAPI server on port 8001
DATA_API_PORT=8001 python -m uvicorn data_api.app:app --reload

# Trigger collection via HTTP
curl -X POST http://localhost:8001/collect/full

# Check latest export
curl http://localhost:8001/datasets/latest
```

### 12.4 Paper Broker Endpoints

```bash
# Read current realized PnL from open virtual pairs
curl http://localhost:8001/paper/pnl

# Close a paper trade
curl -X POST http://localhost:8001/paper/close/<trade_id> \
    -H "Content-Type: application/json" \
    -d '{"exit_price": 105.25}'
```

---

## 13. Conclusion

**Honest assessment:**

This is a **solid batch analytics platform** with clear separation of concerns:
- Collection layer works well
- Validation layer is basic but functional
- Orchestration is idempotent and reliable
- Tests are comprehensive and useful

**What it is NOT (yet):**
- A production trading system
- Safe for live capital without additional engineering
- Complete or automatic in any domain

**What prevents live trading:**
1. Exchange microstructure validation is incomplete (bid/ask, halts, corp actions)
2. Drift governance is statistical but not yet strategy-calibrated
3. Execution gateway has no live broker integration
4. Stream processing runtime is now wired, but still lacks latency SLO instrumentation
5. Full order-to-fill reconciliation with external venue IDs

**Path forward:**
- Extend domain validation to exchange-aware checks
- Couple drift to model-performance degradation metrics
- Keep lock-based model swaps and add runtime audit hooks
- Expand paper trading into full strategy simulation loop
- Wire execution gateway to broker API
- Only then consider live capital

**The core engineering is solid.** The newer components (stream, execution, learning loop) are scaffolding that needs validation before deployment. This distinction is important.

If those gaps are closed in the next roadmap cycle, the system can evolve from a high-quality data/analytics platform into a fully governed end-to-end decision engine.
