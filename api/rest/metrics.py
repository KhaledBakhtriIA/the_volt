"""Prometheus instrumentation for the REST gateway.

Guarded by design: if `prometheus_client` is not installed (e.g. in a minimal
local venv), `setup_metrics` is a no-op and the app runs unchanged. The
production image installs the dependency, so `/metrics` is exposed there for
Prometheus to scrape.
"""
from __future__ import annotations

import time

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response


def setup_metrics(app: FastAPI, service: str = "volt-data-api", version: str = "0.1.0") -> bool:
    """Attach request metrics + a /metrics endpoint. Returns True if enabled."""
    try:  # optional dependency — present in the prod image
        from prometheus_client import (
            CONTENT_TYPE_LATEST,
            Counter,
            Gauge,
            Histogram,
            generate_latest,
        )
    except Exception:  # pragma: no cover - exercised only when the dep is missing
        return False

    try:
        requests_total = Counter(
            "volt_http_requests_total", "HTTP requests", ["method", "path", "status"],
        )
        request_latency = Histogram(
            "volt_http_request_duration_seconds", "Request latency (s)", ["method", "path"],
        )
        build_info = Gauge("volt_build_info", "Build info", ["service", "version"])
    except ValueError:  # already registered (module re-imported, e.g. under test reloads)
        return False
    build_info.labels(service=service, version=version).set(1)

    @app.middleware("http")
    async def _record(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        # Use the route template (not the raw path) to keep label cardinality low.
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        elapsed = time.perf_counter() - start
        request_latency.labels(request.method, path).observe(elapsed)
        requests_total.labels(request.method, path, response.status_code).inc()
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return True
