"""
Observability endpoints: the liveness probe and the Prometheus /metrics scrape
target. These back the k8s probes and the in-cluster Prometheus/Grafana stack
(see infra/deployment/monitoring/).

TestClient is used WITHOUT the `with` context manager on purpose: that avoids
running the app lifespan (which opens a real Redis connection). These routes
need neither a DB nor Redis.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_ok():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_metrics_exposes_prometheus_format():
    # Make a request first so at least one HTTP metric series exists.
    client.get("/healthz")

    r = client.get("/metrics")
    assert r.status_code == 200

    body = r.text
    # Prometheus text exposition format + the instrumentator's default HTTP
    # request metrics must be present.
    assert "# HELP" in body
    assert "http_request" in body
