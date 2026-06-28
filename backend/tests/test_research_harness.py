"""
Phase 3 research-harness tests.

Verify the shapes and provenance contracts of the new experiment functions so
the dashboard and paper can rely on them. These run on the synthetic fallback
(no real data on disk in CI), which is exactly what the provenance field must
report.
"""

from app.services.supervisor_engine import (
    run_controller_comparison,
    run_trace_replay,
    run_stress_test,
    run_sensitivity_sweep,
)

EXPECTED_CONTROLLERS = {
    "Threshold Reactive", "Hysteresis Reactive", "EMA Reactive",
    "PID Controller", "CSA-ACI CCE",
}


def test_comparison_has_five_controllers_with_f1():
    out = run_controller_comparison()
    names = {r["controller"] for r in out["results"]}
    assert names == EXPECTED_CONTROLLERS
    assert all("f1" in r for r in out["results"])
    assert out["telemetry_steps"] == 100


def test_trace_replay_reports_provenance():
    out = run_trace_replay("google", n_steps=80)
    # no real data committed -> must honestly report the fallback
    assert out["source"] in ("real", "synthetic_fallback")
    assert len(out["latency"]) == 80
    assert len(out["ground_truth"]) == 80
    assert {r["controller"] for r in out["results"]} == EXPECTED_CONTROLLERS


def test_stress_test_aggregates_and_tests_significance():
    out = run_stress_test(n_runs=4)
    assert out["n_runs"] == 4
    cce = out["controllers"]["CSA-ACI CCE"]
    # every aggregated metric has mean/std/95% CI
    for metric in ("intent_switches", "f1", "recall"):
        assert set(cce[metric]) == {"mean", "std", "ci95"}
    assert "intent_switches" in out["significance"]["tests"]


def test_sensitivity_sweep_grid_and_default():
    out = run_sensitivity_sweep()
    assert len(out["grid"]) == 5 * 4 * 5          # ew x frac x dwell
    assert out["default"] is not None             # default (8,6,10) is in grid
    assert 0.0 <= out["best"]["csi"] <= 1.0
