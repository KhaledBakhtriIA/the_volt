# The Volt 3

## 3.1) Complete Project Deep Diagnosis (Continuation, 2026-03-28)

This section documents the latest full-project diagnosis pass after Docker setup work. Scope is project code/config only (`data_api/`, `src/`, `tests/`, `documentation/`) and excludes unrelated editor-extension binaries under `.cursor/`.

### Diagnosis execution summary

- Functional validation:
	- `python -m pytest -q`
	- `python -m pytest --maxfail=1 -q`
- Static/syntax sanity:
	- `python -m compileall data_api src tests`
- Dependency integrity:
	- `python -m pip check`
- Container/deployment checks:
	- `docker compose config`
	- `docker info`
	- `docker ps`
	- `curl http://localhost:8000/health`
- Code-smell and hygiene scans:
	- bare `except:` patterns
	- `TODO|FIXME|HACK|XXX`
	- notebook `!pip install` patterns
- Storage/repo inventory:
	- extension distribution (project-only)
	- data footprint under `data_api/data`

### Verified health snapshot (latest)

- Tests: `115 passed, 1 warning` (stable across reruns).
- Compile pass: no syntax errors in `data_api/`, `src/`, `tests/`.
- Dependency check: `No broken requirements found`.
- Runtime warning still present in tests:
	- `data_api/collectors/news_collector.py` (`pd.to_datetime` format inference warning).

### Deployment/runtime findings

- `docker compose config` is valid, but prints deprecation warning:
	- `docker-compose.yml` uses `version: "3.8"` (obsolete in current Compose).
- Docker daemon availability was inconsistent across checks:
	- some checks returned `Docker Desktop is unable to start`.
	- compose file itself remains syntactically valid.
- API health endpoint availability was terminal-session dependent:
	- in one session, `curl http://localhost:8000/health` failed to connect.
	- in user terminal context, `/health` was reachable.

### Documentation and config defects found

- `DOCKER_SETUP.md` includes two incorrect commands:
	- uses invalid form `docker-compose -e DATA_API_PORT=8001 up -d`.
	- references `docker-compose logs volta-data-api` (service name typo; should be `volt-data-api`).
- `docker-compose.yml` should remove obsolete `version` key to eliminate warning noise.

### Code hygiene findings (project scope)

- No bare `except:` blocks found in project source scan.
- No notebook `!pip install` matches found in on-disk `.ipynb` files during latest scan.
- Remaining high-volume editor diagnostics are largely notebook-cell/language-server context noise and not reflected as active project source failures.

### Repository composition (project-only, latest)

- `.py`: `49`
- `.csv`: `22`
- `.md`: `16`
- `.txt`: `3`
- `.ipynb`: `2`
- config/support: `.ini`, `.dockerignore`, `.example`, `.env`, `.gitignore`, `.yml`

### Data footprint (latest)

- Total under `data_api/data`: `646.98 MB`
- `data_api/data/raw`: `638.36 MB`
- `data_api/data/processed`: `0.25 MB`
- `data_api/data/exports`: `7.87 MB`
- File count under `data_api/data`: `22`

### Updated risk register

- `P0` Runtime reproducibility gap:
	- Docker Desktop/daemon availability is inconsistent during verification sessions.
- `P1` Compose deprecation noise:
	- obsolete `version` key in `docker-compose.yml`.
- `P1` Documentation drift:
	- incorrect Docker command examples in `DOCKER_SETUP.md` can mislead operations.
- `P2` Data retention pressure:
	- raw data remains the dominant storage driver (> 98% of `data_api/data`).

### Action list from this diagnosis

1. Remove `version:` from `docker-compose.yml`.
2. Correct Docker command examples in `DOCKER_SETUP.md`.
3. Tighten date parsing path in `data_api/collectors/news_collector.py` to eliminate warning and enforce deterministic parse behavior.
4. Keep retention/archival policy for `data_api/data/raw` as an explicit scheduled operation.

### 3.1 Action Execution Status (Implemented, 2026-03-28)

- Completed: removed obsolete Compose `version` key.
	- `docker-compose.yml`
- Completed: fixed Docker troubleshooting command examples.
	- `DOCKER_SETUP.md`
- Completed: replaced warning-prone vectorized parse with deterministic mixed-shape timestamp parser.
	- `data_api/collectors/news_collector.py`
- Completed: added retention and archival automation + explicit daily schedule policy.
	- `data_api/jobs/data_retention.py`
	- `documentation/DATA_RETENTION_POLICY.md`
	- `data_api/README.md`
	- `.env.example`

### Post-fix validation evidence

- Test suite after fixes: `115 passed in 11.62s` (warning removed).
- Compose validation after fixes: `docker compose config` passes without deprecation warning.
- Editor diagnostics on modified files: no errors.
- Retention module preview run: successful JSON summary with no runtime errors.

## 3.2) What We Have Now vs What We Will Have After Notebook Extraction (Kaggle-Trained Path)

This section answers: "What do we have now?" and "What will we have when we extract the system from the notebook after it is trained in Kaggle?"

### Direct answer

- What we have now:
	- A production-capable data collection and feature pipeline (`data_api`) with stable tests and operational basics (Docker + retention policy), plus a notebook-centric training workflow.
- What we will have after extraction:
	- A fully code-first ML system where training outputs from Kaggle are packaged as versioned model artifacts and served/retrained by reproducible jobs, without requiring notebook execution in production.

### Current state (now)

- Data/feature pipeline is already operational:
	- Multi-source collectors, processors, and export flow are implemented and test-covered.
	- 1M-row dataset generation has been validated.
- Operational baseline exists:
	- Dockerized service setup exists and validates.
	- Data retention/archival automation exists with documented schedule policy.
- Quality baseline exists:
	- `115` tests pass.
	- Key warning/deprecation items from 3.1 were fixed.
- Current limitation:
	- Training logic and experimentation are still centered on notebook workflow (`AutoData_Analyst_v1_aymen.ipynb`).
	- Model promotion path from Kaggle training run to deployed API artifact is not yet fully formalized as a production pipeline.

### Target state (after extraction from notebook)

- Training-to-production chain becomes explicit and repeatable:
	- Kaggle training run produces export bundle:
		- model file(s)
		- preprocessing artifacts (encoders/scalers)
		- feature schema/column contract
		- run metadata (metrics, params, dataset fingerprint, commit id)
	- Bundle is validated and registered into model registry.
	- API loads model artifact by version (not from notebook state).
- Notebook role changes:
	- Notebook remains for R&D only.
	- Production paths (`jobs`, `api`, scheduled runs) never depend on notebook kernel state.
- Operational maturity increases:
	- Deterministic retraining and promotion gates (offline metrics thresholds).
	- Rollback-ready model versioning and lineage.
	- Clear separation between `research` and `production` code paths.

### Side-by-side comparison

- Execution model:
	- Now: Hybrid, with notebook still influencing training flow.
	- After extraction: Code-first pipeline with notebook-independent runtime.
- Artifact management:
	- Now: Datasets and exports are versioned by file naming; model artifacts/process are less formalized.
	- After extraction: Formal model package, schema contract, and versioned registry entries.
- Deployment coupling:
	- Now: Data API is deployable; model lifecycle still partly manual.
	- After extraction: Model lifecycle is deployable and automatable end-to-end.
- Reproducibility:
	- Now: Good for data collection; partial for training/promotion.
	- After extraction: Full reproducibility across train, validate, promote, and serve.
- Risk profile:
	- Now: Main risk is handoff friction from Kaggle notebook output to runtime service.
	- After extraction: Main risk shifts to model drift/monitoring, which is operationally manageable.

### What must be added to reach target state

1. Define and enforce a model artifact contract (files, metadata, schema JSON).
2. Add a `train_export` and `register_model` production job (CLI/job module) for non-notebook execution.
3. Add API inference loading by explicit `model_version` with safe fallback/rollback.
4. Add validation gates before promotion (minimum accuracy/F1/MAE thresholds as applicable).
5. Add model-run documentation template (training dataset id, feature list, metrics, limitations).

### Definition of done for extraction

- A Kaggle-trained model can be exported once and deployed without opening the notebook.
- A new machine can reproduce train->register->serve using only repo code + env config.
- Promotion/rollback between model versions is one command/workflow.
- Monitoring dashboards/logs can identify model version and dataset lineage per prediction batch.

### Business impact of extraction

- Faster and safer deployment of trained models.
- Lower operational risk from notebook/state drift.
- Stronger auditability for decisions based on model outputs.
- Clear scaling path from experimentation to reliable production execution.

## 0.2) Complete Project Deep Diagnosis (2026-03-28)

This section is a full-project diagnosis pass executed after recent data/API integrations.

### Diagnosis method

- Full repository test run:
	- `python -m pytest tests/ -q`
- Workspace diagnostics scan:
	- editor problems via `get_errors`
- Code smell scan:
	- bare-except pattern search (`except:`)
	- debug artifact search (`pdb.set_trace`, `breakpoint(`)
	- TODO/FIXME/HACK markers
- Deployment-readiness checks:
	- Dockerfile presence
	- CI workflow presence
	- `.env.example` presence
- Repository inventory and storage-volume audit:
	- file count by extension
	- raw dataset footprint

### Verified health snapshot

- Test status: `115 passed, 1 warning`
- Runtime warning observed in tests:
	- `data_api/collectors/news_collector.py` date parsing warning (`pd.to_datetime` format inference)
- Editor problems:
	- `1337` problems listed, overwhelmingly notebook-cell hygiene/lint noise (`!pip install` instead of `%pip install`) and optional notebook imports unresolved in the current kernel.
- Python code smell checks:
	- No project-level `except:` bare blocks found in `data_api/`, `src/`, `tests/`.
	- No `pdb.set_trace` / `breakpoint(` artifacts detected.

### Deployment readiness status (current)

- Missing `Dockerfile`.
- Missing CI workflows under `.github/workflows/`.
- Missing `.env.example` for env contract handoff.

Conclusion: code quality and tests are strong, but production packaging/automation remains incomplete.

### Repository composition (current)

- Total files (excluding `.venv`, `.git`, caches): `93`
- Extension distribution:
	- `.py`: `49`
	- `.csv`: `22`
	- `.md`: `15`
	- `.txt`: `3`
	- `.ipynb`: `2`

### Data footprint (current)

- Raw CSV files under `data_api/data/raw`: `13`
- Raw CSV total size: `669,363,903` bytes
- Largest/most recent artifacts include:
	- `trading_dataset_1m_20260328_120524_974881.csv` (`393,196,378` bytes)
	- `trading_dataset_1m_live_20260328_123014_791386.csv` (`155,094,163` bytes)
	- `news_large_test_20260328_113618_848051.csv` (`113,377,302` bytes)

### Architecture diagnosis by subsystem

#### A) `data_api/` operational data service

- API endpoints implemented and wired in `data_api/app.py`:
	- `GET /health`
	- `POST /collect/market`
	- `POST /collect/news`
	- `POST /collect/browser`
	- `POST /collect/reddit`
	- `POST /collect/macro`
	- `POST /collect/desktop`
	- `POST /collect/stock-market`
	- `POST /collect/trading-strategy`
	- `POST /collect/trading-mistakes`
	- `POST /collect/full`
	- `POST /stream/finance-query/config`
	- `GET /datasets/latest`

- Collector resilience posture:
	- Market collection uses provider chain: Yahoo -> FCS -> Binance (tertiary crypto fallback).
	- News collection supports RSS baseline + optional TokenInsight provider sentiment fields.
	- Optional collectors (browser/reddit/macro/desktop/vision) are feature-flagged.

- Pipeline (`data_api/jobs/pipeline.py`):
	- Central full-run orchestration with dependency injection.
	- Persists per-source outputs + merged training export.
	- Produces stable run summary metadata and row counts.

- Storage (`data_api/storage/file_store.py`):
	- Unique timestamped artifact naming with microsecond collision defense.
	- Parquet preference fallback to CSV supported.

#### B) `src/canonical/` control-plane reference modules

- `orchestrator.py`:
	- Idempotent step markers (`_run_step_once`) persisted by run state JSON.
	- `export_only(...)` fully implemented with artifact writes and model registry registration.
- `supervisor.py`:
	- Health scoring and escalation policy (`NORMAL`, `DEGRADED`, `HALT`).
- `reliability.py`:
	- Retry policy with exponential backoff + jitter.
	- Circuit breaker support with open/close behavior.
- `meta_controller.py`:
	- Underperformance/anomaly detection + self-healing workflow.
	- Healing events persisted via ledger.
- `model_registry.py` and `healing_ledger.py`:
	- SQLite-backed versioning/audit persistence for model lifecycle and interventions.

#### C) Test system

- Coverage structure:
	- API contracts: `tests/test_app.py`
	- Collector behaviors: `tests/test_collectors.py`, `tests/test_hybrid_collectors.py`, `tests/test_browser_collector.py`, `tests/test_trading_collectors.py`
	- Pipeline wiring: `tests/test_pipeline_browser.py`, `tests/test_run_production.py`
	- Processing/storage/errors: `tests/test_processors.py`, `tests/test_storage.py`, `tests/test_exceptions.py`
- Current verdict: all suites passing with one known non-fatal warning.

### Risk register (current)

- `P0` Operational packaging gap:
	- No Docker/CI/env-template limits reproducible deployment.
- `P1` Notebook hygiene noise:
	- Notebook cells trigger many editor diagnostics and can mask true new issues.
- `P1` External provider variability:
	- Live provider requests (Yahoo/FCS/Reddit/feeds) can intermittently fail; current code gracefully degrades but this affects row volume consistency per run.
- `P2` Artifact growth:
	- Raw data folder already > 600 MB; retention policy is not yet formalized.

### Recommended next hardening sequence

1. Add `Dockerfile` + minimal `docker-compose.yml` for API service.
2. Add GitHub Actions CI (`pytest`, basic lint/static checks).
3. Add `.env.example` covering all `DATA_API_*` keys (including FCS/TokenInsight/Finance Query).
4. Add data retention script/policy for `data_api/data/raw` and `processed`.
5. Optionally normalize notebook `%pip` and isolate notebook-only dependencies to reduce IDE noise.

### Complete file inventory snapshot (project contents)

- `.gitignore`
- `AutoData_Analyst_v1_aymen.backup_before_polish.ipynb`
- `AutoData_Analyst_v1_aymen.ipynb`
- `data_api/__init__.py`
- `data_api/app.py`
- `data_api/collectors/__init__.py`
- `data_api/collectors/browser_collector.py`
- `data_api/collectors/collector_contract.py`
- `data_api/collectors/desktop_collector.py`
- `data_api/collectors/finance_query_stream.py`
- `data_api/collectors/macro_collector.py`
- `data_api/collectors/market_collector.py`
- `data_api/collectors/news_collector.py`
- `data_api/collectors/reddit_collector.py`
- `data_api/collectors/stock_market_collector.py`
- `data_api/collectors/trading_mistakes_collector.py`
- `data_api/collectors/trading_strategy_collector.py`
- `data_api/collectors/vision_extractor.py`
- `data_api/config/__init__.py`
- `data_api/config/settings.py`
- `data_api/data/exports/training_export_20260327_174252.csv`
- `data_api/data/exports/training_export_20260327_175536.csv`
- `data_api/data/exports/training_export_20260327_180100.csv`
- `data_api/data/kaggle/volt_training_dataset.csv`
- `data_api/data/processed/news_scored_20260327_173729.csv`
- `data_api/data/processed/news_scored_20260327_173848.csv`
- `data_api/data/processed/news_scored_20260327_174252.csv`
- `data_api/data/processed/news_scored_20260327_175536.csv`
- `data_api/data/processed/news_scored_20260327_180100.csv`
- `data_api/data/raw/market_20260327_174252.csv`
- `data_api/data/raw/market_20260327_175536.csv`
- `data_api/data/raw/market_20260327_180100.csv`
- `data_api/data/raw/market_large_test_20260328_113741_728828.csv`
- `data_api/data/raw/market_large_test_20260328_113810_637917.csv`
- `data_api/data/raw/news_20260327_173729.csv`
- `data_api/data/raw/news_20260327_173848.csv`
- `data_api/data/raw/news_20260327_174252.csv`
- `data_api/data/raw/news_20260327_175536.csv`
- `data_api/data/raw/news_20260327_180100.csv`
- `data_api/data/raw/news_large_test_20260328_113618_848051.csv`
- `data_api/data/raw/trading_dataset_1m_20260328_120524_974881.csv`
- `data_api/data/raw/trading_dataset_1m_live_20260328_123014_791386.csv`
- `data_api/exceptions.py`
- `data_api/jobs/__init__.py`
- `data_api/jobs/pipeline.py`
- `data_api/jobs/prepare_kaggle_dataset.py`
- `data_api/jobs/run_once.py`
- `data_api/jobs/run_production.py`
- `data_api/processors/__init__.py`
- `data_api/processors/sentiment.py`
- `data_api/processors/technical_indicators.py`
- `data_api/README.md`
- `data_api/requirements.txt`
- `data_api/storage/__init__.py`
- `data_api/storage/file_store.py`
- `documentation/CODE_ANALYSIS_REPORT.md`
- `documentation/CODE_GUIDE.md`
- `documentation/HYBRID_COLLECTOR_ROADMAP.md`
- `documentation/IMPLEMENTATION_WORKLOG.md`
- `documentation/NOTEBOOK_PRODUCTION_POLICY.md`
- `documentation/SYSTEM_ARCHITECTURE_VISUAL.md`
- `documentation/SYSTEM_DOCUMENTATION.md`
- `documentation/SYSTEM_PERFORMANCE_DEEP_ANALYSIS.md`
- `documentation/the start of the volt.md`
- `documentation/the volt 0.2.md`
- `documentation/the volt 3.md`
- `documentation/VOLT_CONTROL_PLANE_BACKLOG.md`
- `documentation/VOLT_CONTROL_PLANE_IMPLEMENTATION_BLUEPRINT.md`
- `IMPLEMENTATION_WORKLOG.md`
- `large_collect_result.txt`
- `pytest.ini`
- `requirements.txt`
- `src/__init__.py`
- `src/canonical/__init__.py`
- `src/canonical/healing_ledger.py`
- `src/canonical/meta_controller.py`
- `src/canonical/model_registry.py`
- `src/canonical/orchestrator.py`
- `src/canonical/realtime_extractor.py`
- `src/canonical/reliability.py`
- `src/canonical/supervisor.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_app.py`
- `tests/test_browser_collector.py`
- `tests/test_collectors.py`
- `tests/test_exceptions.py`
- `tests/test_hybrid_collectors.py`
- `tests/test_pipeline_browser.py`
- `tests/test_processors.py`
- `tests/test_run_production.py`
- `tests/test_storage.py`
- `tests/test_trading_collectors.py`

## 0.1) Provider Stack Update (2026-03-28)

- Market data strategy updated to Yahoo-first with FCS fallback for forex/crypto gaps.
	- `data_api/collectors/market_collector.py`
	- Added `_fetch_fcs(...)`, symbol normalization (`BTC-USD` -> `BTC/USD`, `EURUSD=X` -> `EUR/USD`), and fallback chain:
		- Yahoo Finance -> FCS -> Binance (tertiary crypto fallback)
- News layer upgraded with optional TokenInsight crypto sentiment feed.
	- `data_api/collectors/news_collector.py`
	- Added optional constructor flags + keys and provider fields:
		- `provider_sentiment`
		- `provider_sentiment_label`
- Runtime configuration expanded for requested no-cost redundancy stack.
	- `data_api/config/settings.py`
	- Added:
		- `DATA_API_FCS_API_KEY`
		- `DATA_API_TOKENINSIGHT_ENABLED`
		- `DATA_API_TOKENINSIGHT_API_KEY`
		- `DATA_API_FINANCE_QUERY_STREAM_ENABLED`
		- `DATA_API_FINANCE_QUERY_WS_URL`
		- `DATA_API_FINANCE_QUERY_CHANNELS`
- Added optional Finance Query streaming helper and endpoint for client-side realtime configuration.
	- `data_api/collectors/finance_query_stream.py`
	- `POST /stream/finance-query/config` in `data_api/app.py`

- Test coverage updated to validate new behavior.
	- `tests/test_collectors.py`
	- `tests/test_app.py`

## 0) Latest Implementation Update (2026-03-28)

This section records what was implemented immediately before this update. Nothing below was removed; this is a prepend-only changelog block.

### What was added

- Hybrid collectors:
	- `data_api/collectors/browser_collector.py`
	- `data_api/collectors/reddit_collector.py`
	- `data_api/collectors/macro_collector.py`
	- `data_api/collectors/desktop_collector.py`
	- `data_api/collectors/vision_extractor.py`
- Collector package exports updated:
	- `data_api/collectors/__init__.py`
- Runtime settings expanded for all source layers and feature flags:
	- `data_api/config/settings.py`
- Full pipeline wiring for all source families:
	- `data_api/jobs/pipeline.py`
- API expanded with direct collector endpoints:
	- `data_api/app.py`
- Requirements and runbook updated:
	- `data_api/requirements.txt`
	- `data_api/README.md`

### New API endpoints

- `POST /collect/browser`
- `POST /collect/reddit`
- `POST /collect/macro`
- `POST /collect/desktop`

### Pipeline behavior now

- `run_full_collection(...)` supports optional Browser, Reddit, Macro, and Desktop layers via settings flags.
- Result payload now includes:
	- `browser_rows`
	- `reddit_rows`
	- `macro_rows`
	- `desktop_rows`
- Raw source artifacts are saved when available:
	- `browser_*`
	- `reddit_*`
	- `macro_*`
	- `desktop_*`

### Data contract and resilience posture

- Uniform collector interface is enforced via contract helpers in:
	- `data_api/collectors/collector_contract.py`
- New collectors are implemented with optional-dependency safeguards.
- Missing credentials/runtimes return empty DataFrames and log warnings instead of crashing the pipeline.

### Tests added/updated

- Added:
	- `tests/test_browser_collector.py`
	- `tests/test_hybrid_collectors.py`
	- `tests/test_pipeline_browser.py`
- Updated:
	- `tests/test_app.py`

Latest validation run:

- `102 passed, 1 warning`

---

## 1) Executive Deep Scan

This document is a full technical dossier for the current `the_volt_system` workspace.
Scope includes:

- Every tracked folder and file in the repository (54 files).
- API architecture, runtime contracts, and local operation.
- Data collection and processing algorithms.
- Canonical control-plane modules in `src/canonical`.
- Test coverage map and diagnostics.
- Notebook state and production boundary policy.

Current state summary:

- API and control-plane code are structurally coherent and test-backed.
- Prior high-priority hardening fixes are already applied (DI-first app wiring, narrower exception handling, notebook-free production entrypoint).
- Biggest remaining quality noise comes from notebook lint diagnostics (`!pip install` in cells, optional imports not present in current kernel).

---

## 2) Repository Topology

Top-level directories and purpose:

- `data_api/`: operational API service and ingestion/processing pipeline.
- `src/canonical/`: reference control-plane and reliability modules.
- `tests/`: pytest suite for API, collectors, processors, storage, exceptions, and production jobs.
- `documentation/`: architecture, reports, worklogs, and policy docs.
- root files: environment/test config and root requirements.
- notebooks: exploratory and historical execution artifacts.

---

## 3) Technology Stack and Dependencies

### Runtime/API stack

- `FastAPI`: API server framework.
- `Pydantic v2` + `pydantic-settings`: typed configuration and validation.
- `Uvicorn`: ASGI runtime.

### Data ingestion and processing stack

- `yfinance`: Yahoo OHLCV market data source.
- `requests`: Binance REST fallback source.
- `feedparser`: RSS/Atom news feed ingestion.
- `nltk` VADER: lexicon sentiment scoring.
- `pandas`, `numpy`: transformation and features.
- `python-dateutil`: flexible timestamp parsing.
- `pyarrow` (optional): parquet output path.

### Analytics/ML packages (root-level scope)

- `scikit-learn`, `statsmodels`, `xgboost`, `lightgbm`.
- `matplotlib`, `seaborn`, `plotly`.
- `openpyxl`.

### Test and tooling

- `pytest`, `pytest-cov`, `pytest-anyio`.
- `httpx`/`fastapi.testclient` via test dependencies.

---

## 4) API System Deep Analysis (`data_api`)

### Validated scraping flow (code-true)

- Market data path: `MarketCollector.fetch()` takes a symbol list, interval, and lookback window.
- Source strategy: Yahoo first (`yfinance`), then Binance REST klines fallback for `-USD` crypto symbols.
- Normalization: both sources are aligned to canonical columns (`timestamp`, `open`, `high`, `low`, `close`, `volume`, `symbol`, `fetched_at_utc`) before downstream use. Yahoo may still include extra columns (for example dividends/splits), but canonical fields are always present.
- News path: `NewsCollector.fetch()` pulls RSS feeds (CoinDesk, CoinTelegraph, Bitcoin Magazine by default), normalizes to six fields (`source`, `title`, `summary`, `link`, `published`, `fetched_at_utc`), drops malformed dates, and sorts newest first.
- Enrichment: `TechnicalIndicatorProcessor` adds RSI/MACD/Bollinger features per symbol. `SentimentProcessor` adds four VADER outputs (`sentiment_neg`, `sentiment_neu`, `sentiment_pos`, `sentiment_compound`).
- Training export: `pipeline._build_training_export()` aggregates sentiment daily and left-joins it to market rows on `day`, producing one row per symbol per candle with both market and sentiment features.
- Output naming: final export is saved as `training_export_*.csv` by `FileStore.save(...)`.
- Scaling data volume: extend symbols via `Settings` (`crypto_symbols`, `stock_symbols`, `macro_symbols`) or environment variables, and add/customize RSS feed URLs via `NewsCollector.fetch(feeds=...)`.

Default runtime note:

- `Settings` defaults are currently `interval=1d` and `lookback_days=365`.
- `MarketCollector.fetch()` method defaults (`1h`, `30`) apply only when called directly without pipeline settings.

### 4.1 Application composition

Main entrypoint: `data_api/app.py`.

Key architecture decisions:

- Dependency provider factory is cached and injectable.
- Endpoints pull dependencies through FastAPI `Depends`, enabling clean test overrides.
- Request validation is explicit for symbols, lookback, and interval.

Primary endpoint contracts:

- `GET /health`: service liveness and minimal metadata.
- `GET /collect/market`: market-only pull for one symbol.
- `GET /collect/news`: news pull and sentiment scoring.
- `GET /collect/full`: full market + news + indicator pipeline.
- `GET /datasets/latest`: discover latest output artifacts.

### 4.2 Configuration model

`data_api/config/settings.py` uses typed settings for:

- data directories,
- feed URLs,
- file format defaults,
- runtime options.

This centralization avoids magic constants and allows environment overrides.

### 4.3 Collector internals

Market collector: `data_api/collectors/market_collector.py`.

- Primary source: Yahoo (`yfinance`).
- Fallback source: Binance REST when Yahoo path fails or returns unusable data.
- Recent hardening: specific handling around request errors and JSON decode paths; logging added for fallback observability.

News collector: `data_api/collectors/news_collector.py`.

- Pulls configured feeds.
- Normalizes item fields.
- Produces deterministic tabular payload for downstream sentiment stage.

### 4.4 Processor internals

Sentiment processor: `data_api/processors/sentiment.py`.

- Uses VADER polarity scoring.
- Converts feed text to sentiment metrics.
- Handles empty/edge inputs safely.

Technical indicators: `data_api/processors/technical_indicators.py`.

- RSI (rolling gain/loss normalization).
- MACD (EMA short-long spread and signal line).
- Bollinger Bands (rolling mean plus/minus standard deviation bands).

### 4.5 Storage internals

`data_api/storage/file_store.py`:

- Persists datasets with unique naming to avoid accidental overwrite.
- Supports parquet where available.
- Falls back to CSV on explicit known exceptions.
- Includes latest-file lookup for API retrieval.

Reliability note:

- Broad `except Exception` has been removed from critical fallback path in favor of explicit exception classes.

### 4.6 Jobs and pipeline

Pipeline: `data_api/jobs/pipeline.py`.

- Orchestrates collectors and processors into full outputs.

Operational scripts:

- `data_api/jobs/run_once.py`: one-shot execution helper.
- `data_api/jobs/run_production.py`: notebook-free production entrypoint.
- `data_api/jobs/prepare_kaggle_dataset.py`: dataset packaging/export path.

Production posture:

- Notebook execution is separated from production path per policy.

---

## 5) Canonical Control-Plane Analysis (`src/canonical`)

The `canonical` package models reliability and governance behaviors beyond the API service itself.

### `reliability.py`

- Retry policy primitives.
- Circuit-breaker style protections.
- Useful for isolating unstable dependencies.

### `supervisor.py`

- Escalation and supervisory decision hooks.
- Defines intervention patterns for repeated failures.

### `orchestrator.py`

- Step-wise orchestration with idempotency awareness.
- Control flow for multi-stage execution.

### `meta_controller.py`

- Higher-level policy and adaptation logic.
- Acts as strategy/governance layer over low-level controls.

### `model_registry.py`

- SQLite-backed model metadata and lifecycle tracking.
- Public docstrings were standardized for maintainability.

### `healing_ledger.py`

- SQLite-backed remediation/history ledger.
- Supports traceability for automated healing actions.

### `realtime_extractor.py`

- Real-time extraction scaffolding aligned with control-plane model.

---

## 6) Algorithms and Data Logic

### Market ingestion algorithm

1. Validate symbol/interval/lookback.
2. Query Yahoo source.
3. If source unavailable/invalid, query Binance fallback.
4. Normalize fields and timestamps.
5. Persist to configured store.

### News sentiment algorithm

1. Pull all configured RSS feeds.
2. Normalize article fields.
3. Build text payloads per item.
4. Apply VADER scoring (`neg`, `neu`, `pos`, `compound`).
5. Persist enriched dataset.

### Technical feature algorithm

1. Compute rolling/EMA components from OHLCV.
2. Derive RSI, MACD, MACD signal, Bollinger upper/lower.
3. Align with timestamps and handle NaN warmup windows.
4. Persist feature-augmented market table.

---

## 7) Full File Inventory (All 54 Files)

### Root

- `.gitignore`: ignores env/data/cache artifacts.
- `requirements.txt`: broad data science and modeling dependency set.
- `pytest.ini`: pytest configuration.
- `IMPLEMENTATION_WORKLOG.md`: root-level implementation notes.
- `AutoData_Analyst_v1_aymen.ipynb`: main exploratory notebook.
- `AutoData_Analyst_v1_aymen.backup_before_polish.ipynb`: historical backup notebook.

### `data_api/`

- `data_api/__init__.py`: package marker.
- `data_api/README.md`: service usage and setup notes.
- `data_api/requirements.txt`: API runtime-focused dependencies.
- `data_api/app.py`: FastAPI app, endpoints, validation, DI wiring.
- `data_api/exceptions.py`: custom exception hierarchy.

### `data_api/config/`

- `data_api/config/__init__.py`: package marker.
- `data_api/config/settings.py`: typed settings and defaults.

### `data_api/collectors/`

- `data_api/collectors/__init__.py`: package marker.
- `data_api/collectors/market_collector.py`: Yahoo primary + Binance fallback market fetch.
- `data_api/collectors/news_collector.py`: RSS ingestion and normalization.

### `data_api/processors/`

- `data_api/processors/__init__.py`: package marker.
- `data_api/processors/sentiment.py`: VADER sentiment features.
- `data_api/processors/technical_indicators.py`: RSI/MACD/Bollinger computations.

### `data_api/storage/`

- `data_api/storage/__init__.py`: package marker.
- `data_api/storage/file_store.py`: filesystem persistence, format fallback, latest lookup.

### `data_api/jobs/`

- `data_api/jobs/__init__.py`: package marker.
- `data_api/jobs/pipeline.py`: full ingestion/processing orchestration.
- `data_api/jobs/run_once.py`: one-time run helper.
- `data_api/jobs/run_production.py`: production-safe non-notebook entrypoint.
- `data_api/jobs/prepare_kaggle_dataset.py`: Kaggle export preparation.

### `src/`

- `src/__init__.py`: package marker.

### `src/canonical/`

- `src/canonical/__init__.py`: canonical exports.
- `src/canonical/reliability.py`: retries/circuit breaker behavior.
- `src/canonical/supervisor.py`: escalation/supervision logic.
- `src/canonical/orchestrator.py`: step orchestrator/idempotency hooks.
- `src/canonical/meta_controller.py`: policy/meta-control logic.
- `src/canonical/model_registry.py`: SQLite model registry.
- `src/canonical/healing_ledger.py`: SQLite healing ledger.
- `src/canonical/realtime_extractor.py`: real-time extraction scaffolding.

### `tests/`

- `tests/__init__.py`: package marker.
- `tests/conftest.py`: fixtures and shared test wiring.
- `tests/test_app.py`: endpoint-level tests with dependency overrides.
- `tests/test_collectors.py`: collector behavior and fallback tests.
- `tests/test_processors.py`: sentiment/indicator processing tests.
- `tests/test_storage.py`: persistence and latest-file tests.
- `tests/test_exceptions.py`: custom exception contracts.
- `tests/test_run_production.py`: production entrypoint behavior.

### `documentation/`

- `documentation/SYSTEM_DOCUMENTATION.md`: broad system docs.
- `documentation/SYSTEM_ARCHITECTURE_VISUAL.md`: architecture visuals.
- `documentation/SYSTEM_PERFORMANCE_DEEP_ANALYSIS.md`: performance-focused analysis.
- `documentation/CODE_ANALYSIS_REPORT.md`: codebase analysis report.
- `documentation/CODE_GUIDE.md`: implementation and behavior guide.
- `documentation/NOTEBOOK_PRODUCTION_POLICY.md`: notebook vs production boundary policy.
- `documentation/IMPLEMENTATION_WORKLOG.md`: documentation-level change log.
- `documentation/VOLT_CONTROL_PLANE_BACKLOG.md`: control-plane backlog.
- `documentation/VOLT_CONTROL_PLANE_IMPLEMENTATION_BLUEPRINT.md`: control-plane implementation plan.
- `documentation/the start of the volt.md`: earlier volt documentation snapshot.
- `documentation/the volt 0.2.md`: earlier volt documentation revision.
- `documentation/the volt 3.md`: this document.

---

## 8) Testing and Quality Diagnostics

### Test status (latest validated cycle)

- Prior validated run: `89 passed, 1 warning`.

### Coverage shape

- API behavior: covered.
- Collector logic and fallback: covered.
- Processor outputs and error handling: covered.
- Storage behavior and format fallback: covered.
- Production entrypoint invocation: covered.

### Diagnostic scan findings

- Python module diagnostics are clean in scanned project files.
- Notebook diagnostics are very noisy due to many inline shell installs (`!pip install`) and optional imports absent from current environment.

Notebook lint recommendation:

- Replace `!pip install` with `%pip install` in notebook cells where interactive install is still needed.

---

## 9) API Local Setup and Runbook

### Environment bootstrap (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r data_api/requirements.txt
```

### Start API

```powershell
uvicorn data_api.app:app --reload
```

### Smoke checks

```powershell
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/collect/market?symbol=BTC-USD&lookback=90d&interval=1d"
curl "http://127.0.0.1:8000/collect/news?symbol=BTC"
curl "http://127.0.0.1:8000/collect/full?symbol=BTC-USD"
curl http://127.0.0.1:8000/datasets/latest
```

### Run tests

```powershell
pytest -q
```

### Production-safe batch run (no notebook)

```powershell
python -m data_api.jobs.run_production
```

---

## 10) Risks, Gaps, and Priority Recommendations

### Current risks

- Notebook sprawl: very large notebooks with persistent outputs/errors can obscure maintainability and inflate review/scan cost.
- Environment drift: notebook-only imports may not match API runtime environment.
- External dependency variability: Yahoo/Binance/feed endpoints can fail or change behavior.

### Recommended next priorities

1. Keep notebook-to-production boundary strict (already documented, continue enforcement).
2. Add contract snapshots for key API response schemas in tests.
3. Add periodic health telemetry around fallback frequency (Yahoo -> Binance).
4. Add explicit integration tests for feed parsing edge cases.
5. Optionally isolate notebook dependencies into a separate `requirements-notebooks.txt`.

---

## 11) Final Assessment

The repository is now in a substantially stronger engineering posture than its initial state:

- API internals are testable and dependency-injectable.
- Data collection pipeline is resilient via fallback and explicit error handling.
- Canonical reliability/control-plane modules are present and documented.
- Production execution can run without notebooks.

The main remaining cleanup burden is notebook hygiene, not core service correctness.

---

## 12) Hybrid Collection Expansion (Uniform Interface)

Your hybrid architecture principle is now captured as an explicit project artifact:

- `documentation/HYBRID_COLLECTOR_ROADMAP.md`

What was codified:

- Every collector should emit a pandas DataFrame with minimum shared columns:
	- `timestamp`
	- `source`
	- `fetched_at_utc`
- Build order:
	1. BrowserCollector (Playwright, TradingView + Investing.com first)
	2. RedditCollector (PRAW) + MacroCollector (FRED)
	3. DesktopCollector (PyAutoGUI + mss)
- Vision extraction layered on top of desktop capture for layout-robust JSON extraction.

Implementation helper added:

- `data_api/collectors/collector_contract.py`
	- `REQUIRED_COLLECTOR_COLUMNS`
	- `ensure_collector_contract(...)`
	- `has_required_columns(...)`

This keeps future collector integration pipeline-safe while allowing different acquisition methods under the same downstream interface.

## 3.3) Notebook Vision vs Production Reality (Gap Analysis, 2026-03-28)

This section records the direct gap analysis between the system vision and what is currently implemented in production code versus notebook prototypes.

### Executive verdict

- The vision is strong and already partially prototyped in the notebook.
- The largest gap is production extraction and integration, not idea absence.
- Many advanced components (real-time orchestration, blockchain brain, quantum-labeled logic) exist in notebook form but are not fully production-wired in `data_api` and `src/canonical` runtime paths.

### Gap table

| Component | Vision | Reality (Code-true) | Gap |
|---|---|---|---|
| Real-time data stream | Live streaming | Notebook has stream prototype; production API is mainly batch collection with stream config helper | BIG GAP |
| Pipeline (clean/process) | Real-time | Batch pipeline works and is stable | Minor |
| Feature store | Versioned feature store | No dedicated online/offline feature store; features computed from files and saved as exports | MAJOR GAP |
| Meta-orchestrator | Quantum logic orchestration | Canonical orchestrator + meta-controller exist, mostly deterministic/rule-based | Partial |
| 3 Brains | Sentiment + Predictive + Blockchain | Sentiment and predictive are present; blockchain brain exists in notebook prototype but not production-integrated | Partial |
| Quantum logic | Flexible adaptive quantum layer | "Quantum" classes exist in notebook, but production path remains classical feature/model flow | MAJOR GAP |
| Rough market adaptation | Strong adaptive behavior | Basic self-healing and escalation are implemented | Partial |
| Execution | Trade execution | No broker/order execution pipeline in production; only execution-cost modeling | MAJOR GAP |

### Evidence from notebook and production code

- Notebook real-time prototypes:
  - `AutoData_Analyst_v1_aymen.ipynb:4679` (`class RealTimeDataExtractor`)
  - `AutoData_Analyst_v1_aymen.ipynb:4885` (`start_real_time_stream(...)`)
  - `AutoData_Analyst_v1_aymen.ipynb:5323` and `AutoData_Analyst_v1_aymen.ipynb:5427` (second real-time implementation)

- Notebook blockchain and multi-brain prototypes:
  - `AutoData_Analyst_v1_aymen.ipynb:65793` (`class AutonomousBlockchainBrain`)
  - `AutoData_Analyst_v1_aymen.ipynb:66051` (`class QuantumSystemWithBlockchain`)
  - `AutoData_Analyst_v1_aymen.ipynb:16788` (trade execution report generation)

- Notebook quantum-labeled prototypes:
  - `AutoData_Analyst_v1_aymen.ipynb:12513` (`class QuantumFeatureEngine`)
  - `AutoData_Analyst_v1_aymen.ipynb:12625` (`class QuantumMLEnsemble`)

- Production runtime behavior:
  - Batch pipeline is primary: `data_api/jobs/pipeline.py`
  - Stream endpoint returns configuration for external clients, not full internal streaming ingestion loop:
    - `data_api/app.py:476`
    - `data_api/collectors/finance_query_stream.py:23`
  - Meta-controller is implemented with threshold/anomaly detection plus healing ledger:
    - `src/canonical/meta_controller.py`
    - `src/canonical/supervisor.py`
  - Execution model exists as slippage/cost prediction, not broker trade execution:
    - `src/canonical/predictive_models.py:311`

### Practical interpretation

- What you have now:
  - Strong batch data and modeling backbone suitable for reliable data operations.
  - Advanced strategic logic in notebook prototypes.

- What is still missing for full vision realization:
  - Production-grade real-time stream processing loop.
  - Dedicated feature store (offline + online, versioned).
  - Production integration of blockchain brain and quantum layer.
  - Broker/order execution engine with risk controls and audit trail.

### Recommended migration priority (short)

1. Extract notebook real-time extractor into `data_api/jobs` or service worker and add monitored daemon scheduling.
2. Add feature store contract (`feature_definitions`, offline parquet/duckdb, online cache) with versioning.
3. Promote blockchain brain to production module and wire into pipeline signal fusion.
4. Add execution gateway abstraction (`paper` then broker adapter), with pre-trade risk checks and post-trade logging.
5. Add CI checks validating parity between notebook prototype outputs and production modules.

## 3.4) Deep System State Reference

A full deep snapshot report was created for this date at:
- `documentation/DEEP_SYSTEM_STATE_2026-03-29.md`

This report consolidates:
- Current architecture state (notebook + production)
- Vision vs reality gap map
- Kaggle dataset inventory snapshot
- Risk register and 3-phase migration plan
- Definition of done for production extraction
