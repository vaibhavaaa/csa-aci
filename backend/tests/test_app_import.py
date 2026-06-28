"""
Smoke test: the FastAPI app imports cleanly with the full router chain.

Catches import-time regressions (bad imports, missing modules, the deleted
orphan stubs) without needing a live database or Redis.
"""


def test_app_imports_and_has_routes():
    from app.main import app

    assert app.title == "Cognitive Agent Platform"

    # Assert against the OpenAPI schema rather than walking `app.routes`:
    # it's the stable public contract for which paths the app serves. Newer
    # FastAPI nests included routers in an internal wrapper object instead of
    # flattening their routes into `app.routes`, so walking routes directly is
    # version-fragile; the OpenAPI `paths` map is not.
    paths = set(app.openapi()["paths"].keys())
    # core experiment endpoints must be wired
    assert "/tasks/run" in paths
    assert "/tasks/compare" in paths
    assert "/tasks/metrics" in paths
    # Phase 3 research endpoints
    assert "/tasks/stress-test" in paths
    assert "/tasks/sensitivity" in paths
    assert "/tasks/trace-replay" in paths
    assert "/tasks/datasets" in paths
    assert "/tasks/history/export" in paths
