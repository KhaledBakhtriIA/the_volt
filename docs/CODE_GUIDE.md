# CODE GUIDE

Comprehensive project analysis for `the_volt_system`.

Date: 2026-03-31
Scope: Full workspace analysis of code, tests, notebooks, config, and documentation files.

---

## 1. Project Overview

This workspace currently has two major systems living side-by-side:

1. `data_api/`:
- A runnable FastAPI-based local data ingestion and feature engineering service.
- Collects market and news data, computes sentiment and technical indicators, and exports training-ready datasets.

2. `src/canonical/`:
- A "control-plane" reference implementation with canonical orchestrator/supervisor/reliability modules.
- Focused on resilience patterns (retry, circuit breaker, health supervision, model registry, healing ledger).

There are also two very large notebooks that contain many iterative versions of logic:
- `AutoData_Analyst_v1_aymen.ipynb`
- `AutoData_Analyst_v1_aymen.backup_before_polish.ipynb`

The `tests/` suite validates the API and core components and currently passes (164 tests).

---

## 2. Root-Level File Inventory and Purpose

### `requirements.txt`
Purpose:
- Notebook/analytics dependency set (pandas, scikit-learn, xgboost, lightgbm, plotting stack).

Notes:
- Distinct from `data_api/requirements.txt`.
- Intended for notebook workflows and model experimentation.

### `pytest.ini`
Purpose:
- Test discovery/config profile for `pytest`.

Key behavior:
- Discovers tests under `tests/`.
- Uses strict marker mode and short traceback format.

### `.gitignore`
Purpose:
- Avoid checking local editor state and generated runtime datasets/logs into git.

Ignored:
- `.cursor/`, `.vscode/`, `__pycache__/`, `data_api/data/`, `data_api/logs/`.

### `IMPLEMENTATION_WORKLOG.md` (root)
Purpose:
- Historical implementation plan/checklist document.

Important:
- Contains older planning status and does not reflect all latest completed work.

### `AutoData_Analyst_v1_aymen.ipynb`
Purpose:
- Primary large notebook with end-to-end analytics and many iterative phases.

Observed structure:
- Very large multi-hundred-cell notebook.
- Mixed outputs include stdout/stderr, images, and historical error traces.
- Contains forecasting, segmentation, anomaly detection, and orchestrator-like logic in evolved forms.

### `AutoData_Analyst_v1_aymen.backup_before_polish.ipynb`
Purpose:
- Backup snapshot of notebook before polishing cleanup.

Observed structure:
- Also very large and includes historical errors in outputs.
- Useful for diffing architecture evolution and troubleshooting regressions.

---

## 3. Runtime Service (`data_api/`)

## 3.1 Package-level files

### `data_api/__init__.py`
Purpose:
- Package entrypoint marker with explicit export surface (`__all__`).

### `data_api/README.md`
Purpose:
- Operator quickstart for setup/run/collection/export commands.

Describes:
- venv setup
- uvicorn launch command
- one-shot batch run
- Kaggle dataset prep command
- endpoint list

### `data_api/requirements.txt`
Purpose:
- Runtime dependencies for API and tests.

Includes:
- API stack (`fastapi`, `uvicorn`, `pydantic`)
- data and source adapters (`pandas`, `yfinance`, `feedparser`, `nltk`, `pyarrow`, `requests`)
- test stack (`pytest`, `pytest-cov`, `pytest-asyncio`, `httpx`)

### `data_api/exceptions.py`
Purpose:
- Central exception hierarchy.

Classes:
- `VoltBaseError`: base domain exception with context payload.
- `VoltSystemException`: backward-compatible alias layer.
- `DataCollectionError`: data source failures.
- `FileStoreError`: persistence failures.
- `ValidationError`: boundary/input validation failures.
- `ProcessingError`: transformation/processing failures.

Interactions:
- Imported by collectors and storage code to raise domain-specific errors.
- Directly tested in `tests/test_exceptions.py`.

---

## 3.2 API entrypoint

### `data_api/app.py`
Purpose:
- FastAPI application and endpoint contracts.

Main components:
- `settings = get_settings()` creates runtime config.
- Module-level dependency instances:
  - `market_collector`
  - `news_collector`
  - `sentiment_processor`
  - `raw_store`, `processed_store`, `export_store`
- `AppDependencies` dataclass bundles these for DI.
- `get_dependencies()` provides DI object via FastAPI `Depends`.

Request models:
- `CollectMarketRequest`
  - fields: `symbols`, `interval`, `lookback_days`
  - validators enforce non-empty symbols, valid interval set, lookback range.
- `CollectNewsRequest`, `ProcessSentimentRequest`, and source-specific request contracts for browser/reddit/macro/desktop/stock/trading collectors.

Endpoints:
1. `GET /health`
- Returns service liveness payload.

2. `POST /collect/market`
- Uses `MarketCollector.fetch(...)`.
- Saves to raw store (`market_*.csv`/parquet optional).

3. `POST /collect/news`
- Uses `NewsCollector.fetch(...)`.
- Applies `SentimentProcessor.score_news(...)`.
- Saves both raw and scored datasets.

4. `POST /collect/full`
- Delegates to `run_full_collection(...)` with injected dependencies.

5. `POST /process/sentiment`
- Validated single-text sentiment scoring endpoint.

5. `GET /datasets/latest`
- Uses `FileStore.latest_file(...)` on each store and returns latest paths.

Inter-file dependencies:
- imports collectors, processors, settings, pipeline, and storage modules.
- tested heavily by `tests/test_app.py`.

Design notes:
- DI is explicit via `AppDependencies` and cached provider (`@lru_cache(maxsize=1)`).
- Legacy-compatible globals still exist for backward compatibility in selected tests and startup wiring.

---

## 3.3 Config subsystem

### `data_api/config/__init__.py`
Purpose:
- Package marker.

### `data_api/config/settings.py`
Purpose:
- Runtime settings model and environment parsing.

Functions/classes:
- `_split_csv_env(name, default)`:
  - Parses CSV env vars into clean lists.
- `Settings` dataclass:
  - Host/port/interval/lookback and symbol lists (crypto/stock/macro).
  - Computes and creates `raw_dir`, `processed_dir`, `export_dir` in `__post_init__`.
- `get_settings()`:
  - Factory returning `Settings()`.

Interactions:
- used by `data_api/app.py`, `jobs/run_once.py`, `jobs/prepare_kaggle_dataset.py`.
- controls default symbols consumed by market collection.

Operational impact:
- Environment-driven behavior allows local customization without code edits.

---

## 3.4 Collectors subsystem

### `data_api/collectors/__init__.py`
Purpose:
- Package export surface for collectors and collector-contract helpers.

### `data_api/collectors/market_collector.py`
Purpose:
- Market OHLCV collector with Yahoo-first and Binance fallback.

Class:
- `MarketCollector`

Key methods:
1. `_fetch_binance(symbol, interval, lookback_days)`
- Accepts only `-USD` symbols for crypto mapping to Binance `USDT` pairs.
- Calls Binance klines API.
- Returns normalized DataFrame with timestamp/open/high/low/close/volume/symbol/fetched_at_utc.

2. `fetch(symbols, interval='1h', lookback_days=30)`
- Validates symbols list; raises `DataCollectionError` when invalid.
- Tries `yfinance.Ticker(...).history(...)` per symbol.
- Catches specific source failures and logs warning.
- Falls back to Binance for unavailable Yahoo symbol histories.
- Concatenates all frames and normalizes timestamps/sorting.

Interactions:
- used by API endpoint `/collect/market` and full pipeline job.
- tested in `tests/test_collectors.py`.

Resilience behavior:
- Avoids total pipeline failure when Yahoo is unavailable for crypto via Binance fallback.

### `data_api/collectors/news_collector.py`
Purpose:
- RSS news ingestion pipeline.

Constants:
- `DEFAULT_RSS_FEEDS` default source map (`coindesk`, `cointelegraph`, `bitcoinmagazine`).

Class:
- `NewsCollector`

Method:
- `fetch(feeds=None, limit_per_feed=50)`
  - Iterates feeds, parses entries with `feedparser.parse`.
  - Normalizes fields (`source`, `title`, `summary`, `link`, `published`, `fetched_at_utc`).
  - Converts `published` to UTC datetime and filters invalid rows.
  - Sorts descending by publish date.

Interactions:
- used by `/collect/news` and full collection pipeline.
- tested in `tests/test_collectors.py`.

Known nuance:
- date parsing can emit a warning when format inference is ambiguous (seen in test warnings).

---

## 3.5 Processing subsystem

### `data_api/processors/__init__.py`
Purpose:
- Package export surface (`SentimentProcessor`, `TechnicalIndicatorProcessor`).

### `data_api/processors/sentiment.py`
Purpose:
- VADER sentiment scoring for news content.

Class:
- `SentimentProcessor`

Methods:
1. `__init__`
- Eager-loads VADER analyzer to fail fast at startup.

2. `_get_analyzer()`
- Lazy-loads NLTK VADER lexicon and analyzer on first call.
- Reuses cached analyzer thereafter.

3. `score_news(news_df)`
- Returns early on empty DataFrame.
- Builds combined text from `title + summary`.
- Computes VADER scores and appends columns:
  - `sentiment_neg`
  - `sentiment_neu`
  - `sentiment_pos`
  - `sentiment_compound`

Interactions:
- used by `/collect/news` and full pipeline.
- tested in `tests/test_processors.py`.

### `data_api/processors/technical_indicators.py`
Purpose:
- Technical feature engineering for market prices.

Class:
- `TechnicalIndicatorProcessor`

Static methods:
- `rsi(series, period=14)`
- `macd(series, fast=12, slow=26, signal=9)`
- `bollinger_bands(series, period=20, num_std=2.0)`
- `add_indicators_to_df(df, price_col='close')`

`add_indicators_to_df` behavior:
- groups data by `symbol`.
- computes indicators where enough points exist (>20 rows).
- otherwise sets indicator fields to `None` for short series.

Interactions:
- called in `jobs/pipeline.py` during training export building.

---

## 3.6 Storage subsystem

### `data_api/storage/__init__.py`
Purpose:
- Package export surface (`FileStore`).

### `data_api/storage/file_store.py`
Purpose:
- Dataset persistence abstraction.

Class:
- `FileStore`

Methods:
1. `__init__(base_dir)`
- ensures directory exists.

2. `_build_unique_path(prefix, extension)`
- builds microsecond-resolution file paths.
- adds numeric suffix fallback if collision still occurs.

3. `save(df, prefix)`
- validates `df is not None`; raises `ValidationError` otherwise.
- optional parquet preference via `DATA_API_PREFER_PARQUET=true`.
- parquet failure logs warning and falls back to csv.
- csv failure raises `FileStoreError`.

4. `latest_file(prefix)`
- returns newest matching file by mtime or `None`.

Interactions:
- used by API endpoints and jobs pipeline.
- heavily tested in `tests/test_storage.py`.

Design impact:
- collision-safe naming solved rapid successive save overwrite risk.

---

## 3.7 Jobs subsystem

### `data_api/jobs/__init__.py`
Purpose:
- Package export surface for batch entrypoint (`run_full_collection`).

### `data_api/jobs/pipeline.py`
Purpose:
- Batch collection orchestration and export dataset assembly.

Functions:
1. `_build_training_export(market_df, news_sentiment_df)`
- validates market input non-empty.
- parses timestamps and enriches market data with technical indicators.
- aggregates daily news sentiment stats.
- merges market and daily sentiment on floored day.
- fills missing sentiment/news counts.
- returns sorted merged dataset.

2. `run_full_collection(settings, ...optional deps...)`
- supports dependency injection for collectors/processors/stores.
- defaults to constructing runtime dependencies when omitted.
- builds symbols list from config (crypto + stock + macro).
- collects market/news, scores sentiment, builds export.
- persists available outputs and returns summary dict with row counts and file paths.

Interactions:
- invoked by API `/collect/full` and `jobs/run_once.py`.

### `data_api/jobs/run_once.py`
Purpose:
- command-line one-shot runner for full collection.

Flow:
- get settings -> run full collection -> print result dictionary.

### `data_api/jobs/prepare_kaggle_dataset.py`
Purpose:
- create stable Kaggle upload CSV path.

Flow:
- locate latest `training_export` file.
- if missing, trigger `run_full_collection` once.
- write stable output `data_api/data/kaggle/volt_training_dataset.csv`.
- copy csv directly or convert parquet->csv when needed.

Interactions:
- used as post-processing/export utility.

---

## 4. Canonical Control Plane (`src/canonical/`)

### `src/__init__.py`
Purpose:
- Source package marker.

### `src/canonical/__init__.py`
Purpose:
- Canonical exports for control-plane classes.

Exports:
- `AnalysisOrchestrator`
- `RealTimeDataExtractor`
- `PipelineSupervisor`
- `MetaControllerV2`
- `NeuroplasticityLoop`

### `src/canonical/reliability.py`
Purpose:
- Shared resilience primitives.

Components:
- `RetryPolicy` dataclass
- `CircuitBreakerOpen` exception
- `CircuitBreaker` class with open/close recovery timing
- `retry_call(fn, policy, breaker)` exponential backoff + jitter

Behavior:
- central reliability helper used by real-time extractor.

### `src/canonical/realtime_extractor.py`
Purpose:
- Real-time extraction adapter with retry and circuit breaker integration.

Components:
- `RealTimeRecord` dataclass
- `RealTimeDataExtractor`

Flow:
- `_fetch_symbol` currently deterministic fallback stub (hash-based synthetic values).
- `get_live_stock_data(symbols)` wraps fetch via `retry_call` and returns DataFrame.

Dependency graph:
- depends on `reliability.py` primitives.

### `src/canonical/supervisor.py`
Purpose:
- Pipeline health and escalation supervisor.

Components:
- `EscalationConfig` dataclass
- `PipelineSupervisor`

Core logic:
- tracks last-update timestamps per model.
- computes health score by stale threshold.
- escalation transitions:
  - `HALT` when score below halt threshold.
  - `DEGRADED` when score stays low for configured sustain period.
  - `NORMAL` when healthy.

### `src/canonical/meta_controller.py`
Purpose:
- Canonical self-healing policy controller + persistent event recording.

Class:
- `MetaControllerV2`

Core capabilities:
- detect underperformers/anomalies from model score map.
- choose action (retrain/deactivate) depending on criticality.
- verify healing outcome.
- persist each action in healing ledger with action metadata.
- produce system health summary with intervention flag.

Dependency graph:
- depends on `healing_ledger.py` for persistence.

### `src/canonical/healing_ledger.py`
Purpose:
- SQLite append/replay store for healing events.

Class:
- `HealingLedger`

Behavior:
- initializes `healing_events` table.
- records events via `INSERT OR REPLACE`.
- exposes `count()` helper.

### `src/canonical/model_registry.py`
Purpose:
- SQLite model version registry and active version management.

Class:
- `ModelRegistry`

Behavior:
- maintains `model_registry` table with unique `(model_name, version_tag)`.
- `register(...)` supports immediate activation or pending state when human approval is required.
- `active_version(model_name)` fetches current active record.
- `rollback_to_version(...)` reassigns active version.
- `approve_version(...)` activates pending versions with approver audit fields.

### `src/canonical/orchestrator.py`
Purpose:
- Canonical orchestrator with idempotent step markers and export flow.

Class:
- `AnalysisOrchestrator`

Key features:
- run state persistence in `exports/runs/{run_id}.json`.
- `_run_step_once(...)` to avoid rerunning completed steps.
- `export_only(...)` writes report/models/log files and registers models in registry.
- `record_prediction(...)` and `record_outcome(...)` expose model error monitoring hooks.
- model activation honors approval-aware registry state.
- `run_complete_analysis(...)` executes 7-step sample flow:
  - data
  - process
  - forecast
  - segment
  - metrics
  - visuals
  - export

Dependency graph:
- depends on `model_registry.py`.
- depends on `prediction_error_monitor.py` for realized-outcome degradation summaries.
- structured to be restart-safe via persisted run state.

### `src/canonical/realtime_runtime.py`
Purpose:
- Real-time infrastructure scaffold for tick normalization, queue transport, low-latency cache, and decision loop wiring.

Components:
- `TickEvent` validated schema.
- `InMemoryTickQueue` test/dev consumer-producer adapter.
- `KafkaTickProducer` durable tick publisher wrapper.
- `RedisFeatureCache` latest/rolling tick cache with in-memory fallback.
- `RealTimeDecisionLoop` consume -> feature build -> predict -> settle pattern.

---

## 5. Test Suite (`tests/`)

Overall status:
- 164 tests passing (latest run in this workspace context).

### `tests/__init__.py`
Purpose:
- test package marker.

### `tests/conftest.py`
Purpose:
- shared fixtures and reusable test data.

Fixtures include:
- temporary directories
- sample market DataFrame
- sample news list
- mock settings and service mocks

### `tests/test_exceptions.py`
Coverage:
- inheritance correctness for custom exception tree
- message preservation
- specific and parent exception catchability

### `tests/test_collectors.py`
Coverage:
- market collector success/fallback/invalid input behavior
- Binance fallback edge cases
- news collector feed parsing behavior and edge handling

### `tests/test_processors.py`
Coverage:
- sentiment processor initialization and scoring behavior
- empty/missing-field handling
- score column shape/type checks

### `tests/test_storage.py`
Coverage:
- save behavior (csv/parquet fallback)
- file naming uniqueness and integrity
- latest-file selection and prefix filtering

### `tests/test_app.py`
Coverage:
- all API endpoints using `TestClient`
- status contract checks
- request parameter handling
- latest dataset path endpoint behavior
- mocked error-path assertions

Design note:
- test suite now includes approval-gate, prediction-error monitor, and realtime runtime coverage.

---

## 6. Existing Documentation Analysis (`documentation/`)

These docs mostly describe notebook/control-plane maturity and roadmap plans. They are useful context, but some are snapshot-in-time and may drift from current code reality.

### `documentation/SYSTEM_DOCUMENTATION.md`
- High-level architecture and model inventory extracted from notebook.

### `documentation/SYSTEM_ARCHITECTURE_VISUAL.md`
- Mermaid architecture diagrams for notebook system phases and model layers.

### `documentation/SYSTEM_PERFORMANCE_DEEP_ANALYSIS.md`
- Log/output-driven KPI analysis for notebook stability and remaining work estimates.

### `documentation/the start of the volt.md`
- State analysis after notebook polishing and control-plane assessment.

### `documentation/the volt 0.2.md`
- Notebook control-plane consolidation status and cleanup notes.

### `documentation/VOLT_CONTROL_PLANE_IMPLEMENTATION_BLUEPRINT.md`
- Detailed production hardening blueprint and phased plan.

### `documentation/VOLT_CONTROL_PLANE_BACKLOG.md`
- Backlogized stories/tasks/tests/DoD derived from blueprint.

### `documentation/CODE_ANALYSIS_REPORT.md`
- Earlier rules-based code review report (contains historical findings; several items have since been implemented).

### `documentation/IMPLEMENTATION_WORKLOG.md`
- Dated implementation log of setup and incremental changes.

---

## 7. Notebook Deep Notes

Because both notebooks are extremely large and iterative, they are best treated as historical research environments rather than single-source production code.

### `AutoData_Analyst_v1_aymen.ipynb`
Observed properties:
- very large notebook with hundreds of code cells.
- many persisted outputs including images and logs.
- mix of mature architecture sections and iterative experimentation blocks.

Implications:
- execution-order sensitivity risk.
- duplicate class/function definitions likely across phases.
- difficult to guarantee reproducible clean run without strict restart and environment pinning protocol.

### `AutoData_Analyst_v1_aymen.backup_before_polish.ipynb`
Observed properties:
- backup variant with similar structure and heavy historical outputs.
- includes more persisted error traces from pre-polish state.

Implications:
- useful as forensic baseline.
- should not be runtime source of truth for operational pipeline.

---

## 8. End-to-End Interaction Map

## 8.1 Primary API flow

1. Client calls endpoint in `data_api/app.py`.
2. Request payload validated by Pydantic models.
3. Endpoint uses injected dependencies (`AppDependencies`).
4. Collector/processor modules produce DataFrames.
5. `FileStore` persists artifacts.
6. Endpoint returns status + row counts + file paths.

## 8.2 Full collection flow (`POST /collect/full`)

1. `app.collect_full()` -> `jobs.pipeline.run_full_collection(settings)`
2. `MarketCollector.fetch(...)` for symbol universe
3. `NewsCollector.fetch(...)`
4. `SentimentProcessor.score_news(...)`
5. `_build_training_export(...)`
6. `FileStore.save(...)` for market/news/scored/export outputs
7. Return summary payload

## 8.3 Feature engineering flow

1. Market rows normalized and timestamped.
2. Technical indicators appended per symbol (`RSI`, `MACD`, `Bollinger`).
3. News sentiment aggregated daily.
4. Daily sentiment merged onto market rows by day.

## 8.4 Export flow

1. Batch run creates latest export file.
2. `prepare_kaggle_dataset.py` copies/converts latest export to stable Kaggle filename.

## 8.5 Canonical control-plane flow (separate subsystem)

1. `AnalysisOrchestrator` manages step states and export artifacts.
2. `ModelRegistry` tracks active model versions.
3. `PipelineSupervisor` computes health and escalation mode.
4. `MetaControllerV2` plans healing actions and records events.
5. `HealingLedger` stores healing events for audit/replay.
6. `RealTimeDataExtractor` uses centralized retry + circuit breaker primitives.
7. `RealTimeDecisionLoop` consumes normalized ticks, builds cached features, and records predictions for realized-outcome monitoring.

---

## 9. Current Strengths, Risks, and Drift Points

Strengths:
1. API pipeline is modular and test-covered.
2. Domain exceptions and validation boundaries are in place.
3. Storage is collision-safe and resilient.
4. Canonical modules encode reliability patterns clearly.

Risks:
1. Notebook remains too large and iterative for deterministic production execution.
2. Documentation snapshots include historical findings now partially outdated.
3. Realtime consumer path is wired, but broker-grade execution controls and latency telemetry are still pending.

Drift points to watch:
1. test patch style (`patch('data_api.app.market_collector')`) assumes module globals.
2. notebooks may contain alternate class definitions that conflict with canonical modules.
3. roadmap docs (blueprint/backlog) can diverge from implemented state if not periodically reconciled.

---

## 10. File-by-File Quick Index

Root:
- `.gitignore`: local/generated ignore policy.
- `requirements.txt`: notebook analytics dependencies.
- `pytest.ini`: test runner config.
- `IMPLEMENTATION_WORKLOG.md`: historical implementation plan.
- `AutoData_Analyst_v1_aymen.ipynb`: primary notebook.
- `AutoData_Analyst_v1_aymen.backup_before_polish.ipynb`: backup notebook.

`data_api/`:
- `__init__.py`: package marker.
- `README.md`: setup/run docs.
- `requirements.txt`: service + test dependencies.
- `exceptions.py`: domain exception hierarchy.
- `app.py`: FastAPI app and endpoints.

`data_api/config/`:
- `__init__.py`: package marker.
- `settings.py`: environment-driven settings.

`data_api/collectors/`:
- `__init__.py`: package marker.
- `market_collector.py`: Yahoo + Binance market ingestion.
- `news_collector.py`: RSS news ingestion.

`data_api/processors/`:
- `__init__.py`: package marker.
- `sentiment.py`: VADER sentiment scoring.
- `technical_indicators.py`: RSI/MACD/Bollinger features.

`data_api/storage/`:
- `__init__.py`: package marker.
- `file_store.py`: resilient file persistence and latest file lookup.

`data_api/jobs/`:
- `__init__.py`: package marker.
- `pipeline.py`: full batch collection + export assembly.
- `run_once.py`: one-shot CLI run.
- `prepare_kaggle_dataset.py`: stable Kaggle CSV export.

`src/`:
- `__init__.py`: package marker.

`src/canonical/`:
- `__init__.py`: canonical exports.
- `reliability.py`: retry/circuit breaker.
- `realtime_extractor.py`: real-time extraction wrapper.
- `realtime_runtime.py`: queue/cache/decision loop realtime scaffold.
- `supervisor.py`: health and escalation supervisor.
- `meta_controller.py`: self-healing controller.
- `healing_ledger.py`: healing event DB.
- `model_registry.py`: model version DB.
- `prediction_error_monitor.py`: realized prediction error tracking.
- `orchestrator.py`: idempotent orchestrator and export flow.

`tests/`:
- `__init__.py`: package marker.
- `conftest.py`: fixtures.
- `test_exceptions.py`: exception tests.
- `test_collectors.py`: collector tests.
- `test_processors.py`: processor tests.
- `test_storage.py`: storage tests.
- `test_app.py`: API endpoint tests.

`documentation/`:
- `SYSTEM_DOCUMENTATION.md`
- `SYSTEM_ARCHITECTURE_VISUAL.md`
- `SYSTEM_PERFORMANCE_DEEP_ANALYSIS.md`
- `the start of the volt.md`
- `the volt 0.2.md`
- `VOLT_CONTROL_PLANE_IMPLEMENTATION_BLUEPRINT.md`
- `VOLT_CONTROL_PLANE_BACKLOG.md`
- `CODE_ANALYSIS_REPORT.md`
- `IMPLEMENTATION_WORKLOG.md`
- `CODE_GUIDE.md` (this file)

---

## 11. Practical Onboarding Sequence

If a new engineer joins this project, this is the safest order to understand it:

1. Read `data_api/README.md` and run tests.
2. Inspect `data_api/app.py` endpoint contracts and request validators.
3. Follow data flow through `collectors` -> `processors` -> `storage` -> `jobs/pipeline.py`.
4. Review `tests/` to understand expected behavior boundaries.
5. Read `src/canonical/` as the reliability/control-plane reference layer.
6. Treat notebooks as research history and mining source, not strict runtime source.
7. Use backlog/blueprint docs only after aligning them with current implemented code.

---

End of guide.
