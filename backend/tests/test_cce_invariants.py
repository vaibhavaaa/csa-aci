"""
CCE invariant tests.

These lock down the core governance behaviours documented in
.claude/rules/csa_aci_package.md. If any of these break, the paper's
central claims are invalidated — so they must always pass.
"""

import pytest

from csa_aci import Supervisor, TelemetrySnapshot, compute_csi, TrustDecayModel


def _telemetry(latency: float, step: int = 0) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        observed_latency=latency,
        cpu_utilisation=0.5,
        throughput=300.0,
        timestamp=step,
    )


def _step(sup, latency, cap_intent, net_intent, step=0):
    """Drive one supervisor step with the given agent proposals."""
    return sup.step(
        telemetry=_telemetry(latency, step),
        capacity_intent=cap_intent,
        capacity_intent_age=0,
        capacity_action_type="CAPACITY_SCALE" if cap_intent == "SCALE_UP" else "NO_OP",
        capacity_action_mag=1.0 if cap_intent == "SCALE_UP" else 0.0,
        network_intent=net_intent,
        network_intent_age=0,
        network_action_type="NETWORK_THROTTLE" if net_intent == "SCALE_DOWN" else "NO_OP",
        network_action_mag=-1.0 if net_intent == "SCALE_DOWN" else 0.0,
    )


# ── Invariant 1: HOLD agreement bypasses the evidence gate ──────────────────
def test_hold_agreement_passes_immediately():
    sup = Supervisor()
    rec = _step(sup, latency=75, cap_intent="HOLD", net_intent="HOLD")
    assert rec.final_intent == "HOLD"
    assert rec.arbitration_reason == "AGREEMENT"


# ── Invariant 2: a single high spike is suppressed by the evidence gate ─────
def test_single_spike_is_rejected():
    sup = Supervisor()
    rec = _step(sup, latency=150, cap_intent="SCALE_UP", net_intent="HOLD")
    # window has only 1 reading (< evidence_window=8) → must NOT switch
    assert rec.final_intent == "HOLD"
    assert rec.arbitration_reason == "EVIDENCE_REJECT"


# ── Invariant 3: emergency override bypasses BOTH gates at >= 300ms ─────────
def test_emergency_override_acts_in_one_step():
    sup = Supervisor()
    rec = _step(sup, latency=350, cap_intent="SCALE_UP", net_intent="HOLD")
    assert rec.final_intent == "SCALE_UP"
    assert rec.arbitration_reason == "EMERGENCY_OVERRIDE"


# ── Invariant 4: sustained high load eventually switches to SCALE_UP ────────
def test_sustained_high_load_switches_up():
    sup = Supervisor()
    last = None
    for i in range(15):
        last = _step(sup, latency=130, cap_intent="SCALE_UP", net_intent="HOLD", step=i)
    # after dwell (10) + full evidence window (8 of which >=100), gate opens
    assert last.final_intent == "SCALE_UP"
    assert last.arbitration_reason == "EVIDENCE_ACCEPT"


# ── Invariant 5: intervention_distance is bounded (trust-score premise) ─────
def test_intervention_distance_non_negative_and_bounded():
    sup = Supervisor()
    for i in range(20):
        lat = 130 if i % 2 == 0 else 40
        rec = _step(sup, latency=lat,
                    cap_intent="SCALE_UP" if lat > 100 else "HOLD",
                    net_intent="SCALE_DOWN" if lat < 70 else "HOLD",
                    step=i)
        assert rec.intervention_distance >= 0.0
        # trust-score normalisation assumes worst case ~5.0
        assert rec.intervention_distance <= 5.0


# ── CSI metric: label thresholds ────────────────────────────────────────────
def test_csi_labels():
    perfect = compute_csi(avg_trust=1.0, intent_switch_count=0, conflict_count=0, total_steps=100)
    assert perfect["csi"] == pytest.approx(1.0)
    assert perfect["label"] == "STABLE"

    bad = compute_csi(avg_trust=0.5, intent_switch_count=50, conflict_count=50, total_steps=100)
    assert bad["label"] == "DEGRADED"

    empty = compute_csi(avg_trust=0.0, intent_switch_count=0, conflict_count=0, total_steps=0)
    assert empty["label"] == "NO DATA"


# ── Trust Decay Model: decay, recovery, and floor ──────────────────────────
def test_trust_decays_then_recovers():
    m = TrustDecayModel()
    decayed = m.step(conflict=True, evidence_accepted=False)
    assert decayed < 1.0
    recovered = m.step(conflict=False, evidence_accepted=True)
    assert recovered > decayed


def test_trust_never_below_floor():
    m = TrustDecayModel()
    for _ in range(200):
        m.step(conflict=True, evidence_accepted=False)
    assert m.current() >= 0.1
