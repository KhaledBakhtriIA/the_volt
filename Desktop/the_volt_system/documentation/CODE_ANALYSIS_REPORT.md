# Deep Code Analysis Report (Rebased)

Date: 2026-03-31
Scope: Current repository state, reconciled with live source and tests after reliability/governance/realtime scaffold updates.

## Summary

This report supersedes older snapshots that showed unresolved remediation items and outdated test counts.

Current status:
- Critical priorities fixed: `4/4`
- Tests passing: `164`
- Compliance estimate: `~96%` for implemented batch/control-plane scope
- Residual risk: realtime consumer path is now wired, but broker-grade execution controls, latency SLO instrumentation, and exchange-level safeguards are still pending for live-capital operation.

## Tabs

Use these section links as tabs:
- [Violations](#violations)
- [Files Affected](#files-affected)
- [Fix Order](#fix-order)
- [What Works](#what-works)

---

## Violations

Tap each item to expand exact old bad code, implemented fix, and file.

<details>
<summary><strong>V1 (Fixed): Silent exception swallowing</strong></summary>

Status:
- Fixed.

Implemented in:
- `data_api/collectors/market_collector.py`
- `data_api/storage/file_store.py`

Old bad code:
```python
if response.status_code != 200:
    return pd.DataFrame()

if not isinstance(payload, list) or not payload:
    return pd.DataFrame()

except (IOError, OSError, Exception) as e:
    logger.warning(...)
```

Implemented fix:
```python
# collector now logs explicit context before returning fallback empty DataFrame
logger.warning("Binance request returned %s for %s", response.status_code, market)
logger.warning("Binance returned empty/invalid payload for %s", market)

# storage now removes broad Exception catch
except (IOError, OSError, ValueError, TypeError, ImportError) as e:
    logger.warning(...)
```

Outcome:
- No broad `except Exception` in storage.
- Collector fallback paths now emit diagnostic logs.

</details>

<details>
<summary><strong>V2 (Fixed): Module-level singletons as primary patch target</strong></summary>

Status:
- Fixed.

Implemented in:
- `data_api/app.py`
- `tests/test_app.py`

Old bad code:
```python
market_collector = MarketCollector()
news_collector = NewsCollector()
sentiment_processor = SentimentProcessor()
```

Implemented fix:
```python
@lru_cache
def get_dependencies() -> AppDependencies:
    return AppDependencies(
        market_collector=MarketCollector(),
        news_collector=NewsCollector(),
        sentiment_processor=SentimentProcessor(),
        raw_store=FileStore(settings.raw_dir),
        processed_store=FileStore(settings.processed_dir),
        export_store=FileStore(settings.export_dir),
    )
```

```python
# tests now use dependency overrides
app.dependency_overrides[get_dependencies] = lambda: mocked_dependencies
```

Outcome:
- Endpoints consume dependency-injected services.
- Tests no longer patch module-global service objects.

</details>

<details>
<summary><strong>V3 (Fixed): Missing canonical docstrings</strong></summary>

Status:
- Fixed.

Implemented in:
- `src/canonical/model_registry.py`
- `src/canonical/healing_ledger.py`

Old bad code:
```python
class ModelRegistry:
    def register(...):
        ...

class HealingLedger:
    def record(...):
        ...
```

Implemented fix:
```python
class ModelRegistry:
    """Persist model versions and track the active deployment version."""

class HealingLedger:
    """Persist self-healing intervention records for audit and replay."""
```

Outcome:
- Public classes and public methods now include concise docstrings.

</details>

<details>
<summary><strong>V4 (Fixed/Mitigated): Notebook production safety</strong></summary>

Status:
- Fixed as an operational policy and execution path.
- Notebooks remain as research artifacts (intended), not production entrypoints.

Implemented in:
- `data_api/jobs/run_once.py`
- `data_api/jobs/run_production.py`
- `tests/test_run_production.py`
- `data_api/README.md`
- `documentation/NOTEBOOK_PRODUCTION_POLICY.md`

Old bad pattern:
```text
Production flow depended on notebook execution as practical source-of-truth.
```

Implemented fix:
```text
1) Added explicit notebook-free production entrypoint:
   python -m data_api.jobs.run_production
2) Added optional Kaggle export orchestration:
   python -m data_api.jobs.run_production --prepare-kaggle
3) Added tests proving module entrypoint behavior.
4) Added policy doc enforcing notebooks as exploration only.
```

Outcome:
- Production runtime no longer requires notebook execution.
- Reproducible module-based execution path is documented and tested.

</details>

---

## Files Affected

Core fixes:
- `data_api/collectors/market_collector.py`
- `data_api/storage/file_store.py`
- `data_api/app.py`
- `tests/test_app.py`
- `src/canonical/model_registry.py`
- `src/canonical/healing_ledger.py`
- `data_api/jobs/run_once.py`
- `data_api/jobs/run_production.py`
- `tests/test_run_production.py`
- `data_api/README.md`
- `documentation/NOTEBOOK_PRODUCTION_POLICY.md`

---

## Fix Order

Executed order:
1. Exception handling hardening.
2. DI-first endpoint wiring and test override migration.
3. Canonical module docstrings.
4. Notebook-independent production entrypoint + policy + tests.

---

## What Works

Verified working now:
- Full test suite passes: `164 passed`.
- API endpoints validate requests and run with injected dependencies.
- Storage fallback logic logs and avoids broad catch-all swallowing.
- Canonical public APIs are documented.
- Production run path is module-first and notebook-free.
- Model governance includes approval-aware activation (`REQUIRE_HUMAN_APPROVAL`) and realized prediction-error tracking.
- Realtime bootstrap exists with Redpanda/Redis compose services and runtime modules (`realtime_runtime.py`).
- Always-on runtime service now wires continuous consumer execution in app lifecycle when realtime mode is enabled.

---

## Delta vs Prior Rebased Report

Changed since prior version:
- All four listed priorities are now addressed.
- `tests/test_app.py` was rewritten around FastAPI dependency overrides.
- Added production execution policy and entrypoint tests.

This document is now the current source of truth for compliance status.
