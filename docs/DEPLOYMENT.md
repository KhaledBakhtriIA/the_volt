# Deployment & Operations Runbook

How the Volt System is built, shipped, observed, and operated in production.

## 1. Topology

| Service | Image | Port | Purpose |
|---|---|---|---|
| `volt-data-api` | built from [`infrastructure/docker/Dockerfile`](../infrastructure/docker/Dockerfile) | 8000 | FastAPI gateway (`/health`, `/metrics`, collectors, paper broker) |
| `redpanda` | `redpandadata/redpanda` | 9092 | Kafka-compatible tick stream |
| `redis` | `redis:7.2-alpine` | 6379 | Real-time feature cache |
| `prometheus` | `prom/prometheus` | 9090 | Metrics scrape + alert rules |
| `grafana` | `grafana/grafana` | 3000 | Dashboards (auto-provisioned) |

```bash
cp .env.example .env       # fill credentials; set GRAFANA_ADMIN_PASSWORD
docker compose up --build -d
docker compose ps
```

- API: http://localhost:8000/health · http://localhost:8000/metrics
- Prometheus: http://localhost:9090 (alerts under Status → Rules)
- Grafana: http://localhost:3000 (admin / `$GRAFANA_ADMIN_PASSWORD`) — the
  **Volt System — API Overview** dashboard is provisioned automatically.

## 2. CI/CD

**CI** ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) runs on every push/PR to `main`:
1. `ruff check .` — lint gate (config in `pyproject.toml`)
2. `pytest tests` — full suite (unit + integration + agent) with coverage summary
3. `npm run build` — frontend build
4. Docker image build (no push) — validates the Dockerfile

**CD** ([`.github/workflows/cd.yml`](../.github/workflows/cd.yml)) runs on push to `main` and on `v*` tags:
- Builds the API image and pushes to **GHCR** as
  `ghcr.io/<owner>/<repo>:latest`, `:sha-<commit>`, and `:<semver>` for tags.

Release flow:

```bash
git tag v0.2.0 && git push origin v0.2.0     # -> ghcr.io/...:0.2.0
docker pull ghcr.io/khaledbakhtriia/the_volt:0.2.0
```

Rollback = redeploy the previous immutable `sha-*` tag.

## 3. Observability

- The API exposes Prometheus metrics at `/metrics`
  ([`api/rest/metrics.py`](../api/rest/metrics.py)): request counts by
  method/route/status, latency histograms, and build info. Instrumentation is a
  no-op if `prometheus_client` is absent, so local test runs are unaffected.
- Prometheus scrapes every 15s; alert rules live in
  [`infrastructure/monitoring/prometheus/alerts.yml`](../infrastructure/monitoring/prometheus/alerts.yml):
  `VoltApiDown` (critical), `VoltHighErrorRate` >5% 5xx, `VoltHighLatency` p95 >1s.
- Grafana datasource + dashboard are file-provisioned from
  [`infrastructure/monitoring/grafana/`](../infrastructure/monitoring/grafana/) — no manual setup.

## 4. MLOps lifecycle

1. **Drift detection** — `models/evaluation/drift_detector.py` runs KS + PSI
   checks against live features.
2. **Retraining** — drift beyond thresholds triggers the
   `NeuroplasticityLoop` (`models/training/learning_loop.py`), which invokes the
   Optuna-tuned XGBoost pipeline.
3. **Approval gate** — candidate models are registered `PENDING` in the
   `ModelRegistry` (`models/registry/model_registry.py`). With
   `REQUIRE_HUMAN_APPROVAL` enabled, nothing serves traffic until a human
   promotes it.
4. **Serving** — promoted models are scored by `models/inference/` through the
   real-time runtime; the `PredictionErrorMonitor` feeds errors back to step 1.

Model artifacts and the registry DB are runtime state — they are **not**
committed; persist them via the compose volumes.

## 5. Ops quick reference

```bash
make up / make down          # start / stop the stack
make logs                    # tail API logs
make test                    # 190+ tests
make lint                    # ruff gate (same as CI)
docker compose restart volt-data-api
```

**Data & state to back up:** `data_api/data/` (parquet feature store),
Grafana + Prometheus volumes, and the model registry / paper-ledger SQLite files.
