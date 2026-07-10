"""Prometheus /metrics endpoint (active only when prometheus_client is installed)."""
import pytest

pytest.importorskip("prometheus_client")

from fastapi.testclient import TestClient

from api.rest.app import app


def test_metrics_endpoint_exposes_prometheus_format():
    with TestClient(app) as client:
        client.get("/health")  # generate at least one sample
        resp = client.get("/metrics")

    assert resp.status_code == 200
    body = resp.text
    assert "volt_http_requests_total" in body
    assert "volt_build_info" in body


def test_metrics_records_request_labels():
    with TestClient(app) as client:
        client.get("/health")
        body = client.get("/metrics").text

    assert 'path="/health"' in body
