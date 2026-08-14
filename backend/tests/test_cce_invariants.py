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


def _step_cpu(sup, latency, cpu, cap_intent, net_intent, step=0):
    """Like _step but with an explicit CPU reading (for CPU-emergency cases)."""
    tel = TelemetrySnapshot(
        observed_latency=latency,
        cpu_utilisation=cpu,
        throughput=300.0,
        timestamp=step,
    )
    return sup.step(
        telemetry=tel,
        capacity_intent=cap_intent,
        capacity_intent_age=0,
        capacity_action_type="CAPACITY_SCALE" if cap_intent == "SCALE_UP" else "NO_OP",
        capacity_action_mag=1.0 if cap_intent == "SCALE_UP" else 0.0,
        network_intent=net_intent,
        network_intent_age=0,
        network_action_type="NETWORK_THROTTLE" if net_intent == "SCALE_DOWN" else "NO_OP",
        network_action_mag=-1.0 if net_intent == "SCALE_DOWN" else 0.0,
    )


# ── Invariant 3b: the emergency guarantee must NOT depend on agent behaviour.
#    Per csa_aci_package.md: "Emergency override (>=300ms) must bypass BOTH the
#    evidence gate and dwell time" and force SCALE_UP. If both agents (wrongly)
#    propose SCALE_DOWN during a latency crisis, the governor must still act.
#    Exercises the guard at cce.py:250.
def test_emergency_latency_overrides_even_when_agents_say_scale_down():
    sup = Supervisor()
    rec = _step(sup, latency=350, cap_intent="SCALE_DOWN", net_intent="SCALE_DOWN")
    assert rec.final_intent == "SCALE_UP"
    assert rec.arbitration_reason == "EMERGENCY_OVERRIDE"


# ── Invariant 3c: same guarantee for the CPU emergency trigger (>=0.95).
#    A critical CPU reading must force SCALE_UP regardless of arbitrated
#    direction. Exercises the CPU branch at cce.py:244-250.
def test_emergency_cpu_overrides_even_when_agents_say_scale_down():
    sup = Supervisor()
    rec = _step_cpu(sup, latency=40, cpu=0.97, cap_intent="SCALE_DOWN", net_intent="SCALE_DOWN")
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


# ── Invariant 6: the Step-1 conflict-arbitration outcome is preserved in
#    conflict_reason even when the evidence gate overwrites arbitration_reason.
#    Without this, multi-signal conflict resolution is invisible in telemetry.
def test_conflict_reason_preserved_through_gate():
    # capacity HOLD, network SCALE_DOWN, calm latency → resolved by deferring
    # the capacity agent; the gate then rejects (window not full this step).
    sup = Supervisor()
    rec = _step(sup, latency=50, cap_intent="HOLD", net_intent="SCALE_DOWN")
    assert rec.conflict_reason == "CAPACITY_DEFERRED"    # arbitration outcome kept
    assert rec.arbitration_reason == "EVIDENCE_REJECT"   # gate outcome is final

    # other direction: network HOLD, capacity SCALE_UP, latency below the 100ms
    # safety-override threshold → resolved by deferring the network agent.
    sup2 = Supervisor()
    rec2 = _step(sup2, latency=50, cap_intent="SCALE_UP", net_intent="HOLD")
    assert rec2.conflict_reason == "NETWORK_DEFERRED"


# ── Invariant 6b: the multi-signal safety override is recorded as a distinct
#    conflict_reason (not mislabeled, not lost behind the gate outcome).
def test_safety_override_recorded_as_conflict_reason():
    sup = Supervisor()
    rec = _step(sup, latency=150, cap_intent="SCALE_UP", net_intent="HOLD")
    assert rec.conflict_reason == "SAFETY_OVERRIDE"


# ── Invariant 6c: Lemma 1b — emergency dwell credit is DIRECTION-SCOPED.
#    The emergency branch sets pending_direction=SCALE_UP and signal_age=D. That
#    credit must attach to SCALE_UP only: a later SCALE_DOWN has to earn its own
#    D steps, while a sustained SCALE_UP may resume sooner (evidence-gated). An
#    emergency may accelerate action toward capacity, never away from it.
def _drive(sup, seq):
    """Feed [(latency, cpu, intent)] and return the records."""
    out = []
    for i, (lat, cpu, intent) in enumerate(seq):
        out.append(_step_raw(sup, latency=lat, cpu=cpu, cap_intent=intent,
                             net_intent=intent,
                             cap_mag=-1.0 if intent == "SCALE_DOWN" else 1.0,
                             net_mag=-1.0 if intent == "SCALE_DOWN" else 1.0,
                             step=i))
    return out


def test_emergency_credit_does_not_transfer_to_scale_down():
    sup = Supervisor()
    D = sup.cfg.min_dwell_time
    recs = _drive(sup,
                  [(30.0, 0.10, "SCALE_DOWN")] * 14
                  + [(350.0, 0.10, "SCALE_UP")]
                  + [(30.0, 0.10, "SCALE_DOWN")] * (D + 10))

    em = next(i for i, r in enumerate(recs)
              if r.arbitration_reason == "EMERGENCY_OVERRIDE")
    down = next(i for i, r in enumerate(recs)
                if i > em and r.final_intent == "SCALE_DOWN")
    assert down - em >= D, "SCALE_DOWN inherited the emergency's dwell credit"


def test_emergency_credit_is_kept_by_sustained_scale_up():
    sup = Supervisor()
    D = sup.cfg.min_dwell_time
    recs = _drive(sup,
                  [(30.0, 0.10, "SCALE_DOWN")] * 14
                  + [(350.0, 0.10, "SCALE_UP")]
                  + [(150.0, 0.80, "SCALE_UP")] * (D + 10))

    em = next(i for i, r in enumerate(recs)
              if r.arbitration_reason == "EMERGENCY_OVERRIDE")
    up = next(i for i, r in enumerate(recs)
              if i > em and r.final_intent == "SCALE_UP")
    # Strictly sooner than D: UP keeps its credit and waits on evidence only.
    assert up - em < D
    assert recs[up].arbitration_reason == "EVIDENCE_ACCEPT"


def test_intent_changed_is_not_the_reversal_predicate():
    """Guards the trap documented in backend/probe_l1.py. `intent_changed` is
    also true on HOLD<->direction transitions, so using it as a stability
    metric reports reversals that did not happen. The committed-direction
    predicate (HOLD-filtered) is the correct one."""
    sup = Supervisor()
    recs = _drive(sup,
                  [(30.0, 0.10, "SCALE_DOWN")] * 12
                  + [(350.0, 0.10, "SCALE_UP")]
                  + [(150.0, 0.80, "SCALE_UP")] * 15)

    naive = [i for i, r in enumerate(recs) if r.intent_changed and r.final_intent != "HOLD"]

    reversals, committed = [], None
    for i, r in enumerate(recs):
        if r.final_intent != "HOLD":
            if committed is not None and r.final_intent != committed:
                reversals.append(i)
            committed = r.final_intent

    # The naive predicate strictly over-reports; every true reversal is in it.
    assert set(reversals) < set(naive)
    # ...and every extra it reports is a departure from HOLD that reverses
    # nothing: the preceding step was HOLD, and the direction is either the
    # first ever committed or a resumption of the one already committed.
    extras = set(naive) - set(reversals)
    committed = None
    for i, r in enumerate(recs):
        if i in extras:
            assert i > 0 and recs[i - 1].final_intent == "HOLD"
            assert committed is None or r.final_intent == committed
        if r.final_intent != "HOLD":
            committed = r.final_intent


# ── Invariant 7: non-finite input is HELD and NAMED, never acted on ─────────
#    CSA-ACI is published as a drop-in module taking caller-supplied telemetry
#    and magnitudes. An adopting system deriving a magnitude from a ratio
#    (utilisation, queue depth) can produce NaN on an empty observation window.
#    Policy: unclear input -> HOLD, name the reason, count it. Never raise —
#    a governor that crashes the system it governs has failed at its job.

def _step_raw(sup, latency, cpu=0.5, cap_mag=0.0, net_mag=0.0,
              cap_intent="HOLD", net_intent="HOLD", step=0):
    """Drive one step with fully explicit telemetry and magnitudes."""
    return sup.step(
        telemetry=TelemetrySnapshot(observed_latency=latency, cpu_utilisation=cpu,
                                    throughput=300.0, timestamp=step),
        capacity_intent=cap_intent, capacity_intent_age=0,
        capacity_action_type="NO_OP", capacity_action_mag=cap_mag,
        network_intent=net_intent, network_intent_age=0,
        network_action_type="NO_OP", network_action_mag=net_mag,
    )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), None])
def test_non_finite_magnitude_holds_and_is_named(bad):
    sup = Supervisor()
    rec = _step_raw(sup, latency=150, cap_mag=bad, cap_intent="SCALE_UP")
    assert rec.final_intent == "HOLD"
    assert rec.arbitration_reason == "INVALID_INPUT"
    assert "capacity_action_mag" in rec.invalid_fields
    assert sup.invalid_input_count == 1


@pytest.mark.parametrize("field,kwargs", [
    ("observed_latency", {"latency": float("nan")}),
    ("cpu_utilisation",  {"latency": 150, "cpu": float("nan")}),
])
def test_non_finite_telemetry_is_named_not_silent(field, kwargs):
    """The quiet failure: NaN telemetry makes every threshold test False, so
    both agents fall through to HOLD and the system looks calm. It must be
    reported as INVALID_INPUT, not as an ordinary HOLD."""
    sup = Supervisor()
    rec = _step_raw(sup, **kwargs)
    assert rec.final_intent == "HOLD"
    assert rec.arbitration_reason == "INVALID_INPUT"
    assert field in rec.invalid_fields


def test_emergency_path_survives_a_telemetry_glitch():
    """Regression: the emergency branch must not be disabled by a bad reading.
    A NaN must not enter the evidence buffers, and the very next critical
    reading must still fire in one step."""
    sup = Supervisor()
    _step_raw(sup, latency=float("nan"), step=0)
    assert len(sup.engine.state.recent_latency) == 0      # buffer not poisoned

    rec = _step_raw(sup, latency=350, cap_intent="SCALE_UP", step=1)
    assert rec.final_intent == "SCALE_UP"
    assert rec.arbitration_reason == "EMERGENCY_OVERRIDE"


def test_glitch_does_not_erase_accumulated_dwell():
    """A single bad reading must not cost the system signal age it legitimately
    earned — the same treatment EVIDENCE_REJECT gives (which also leaves
    signal_age standing). Nine good steps, one glitch, then the tenth good step
    must switch."""
    sup = Supervisor()
    for i in range(9):
        _step_raw(sup, latency=150, cap_intent="SCALE_UP", cap_mag=1.0, step=i)
    assert sup.engine.state.signal_age == 9

    glitch = _step_raw(sup, latency=150, cap_mag=float("nan"),
                       cap_intent="SCALE_UP", step=9)
    assert glitch.arbitration_reason == "INVALID_INPUT"
    assert sup.engine.state.signal_age == 9               # preserved, not reset

    rec = _step_raw(sup, latency=150, cap_intent="SCALE_UP", cap_mag=1.0, step=10)
    assert rec.arbitration_reason == "EVIDENCE_ACCEPT"
    assert rec.final_intent == "SCALE_UP"


def test_invalid_step_keeps_intervention_distance_finite():
    """intervention_distance is the trust-score premise and must stay a
    non-negative real even when the requested magnitude was NaN."""
    sup = Supervisor()
    rec = _step_raw(sup, latency=150, cap_mag=float("nan"), net_mag=float("nan"),
                    cap_intent="SCALE_UP")
    assert rec.intervention_distance == 0.0
    assert rec.intervention_distance >= 0.0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, "oops"])
def test_agents_abstain_instead_of_raising(bad):
    """The agents run BEFORE the CCE in the live path, so validation at the
    engine alone is not enough: a failed metrics scrape yields None, and
    `None >= 0.75` raises TypeError inside the agent. An agent that cannot read
    its signal must abstain to HOLD and let the CCE name the problem."""
    from csa_aci.agents import CapacityAgent, NetworkAgent

    tel = TelemetrySnapshot(observed_latency=bad, cpu_utilisation=bad)
    cap_intent, cap_action = CapacityAgent().step(tel, None)
    net_intent, net_action = NetworkAgent().step(tel, None)

    assert cap_intent.value == "HOLD" and cap_action == "NO_OP"
    assert net_intent.value == "HOLD" and net_action == "NO_OP"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, "oops"])
def test_full_live_path_never_raises_on_bad_telemetry(bad):
    """End-to-end: agents + CCE. A governance layer that crashes the system it
    governs has failed at its job."""
    from csa_aci.agents import CapacityAgent

    sup = Supervisor()
    tel = TelemetrySnapshot(observed_latency=bad, cpu_utilisation=bad)
    cap_intent, _ = CapacityAgent().step(tel, None)
    rec = _step_raw(sup, latency=bad, cpu=bad, cap_intent=cap_intent.value)
    assert rec.final_intent == "HOLD"
    assert rec.arbitration_reason == "INVALID_INPUT"

    # ...and the emergency path is still alive on the very next good reading
    rec2 = _step_raw(sup, latency=350, cap_intent="SCALE_UP", step=1)
    assert rec2.arbitration_reason == "EMERGENCY_OVERRIDE"


def test_clamp_holds_position_on_non_finite_delta():
    """Lemma 2 (Bounded Actuation), default-deny. The clamp previously tested
    only the two out-of-range branches and fell through to `return proposed`;
    a non-finite delta compares False both ways and escaped, then poisoned
    last_*_mag and disabled the bound for the process lifetime."""
    eng = Supervisor().engine
    assert eng._clamp(prev=0.5, proposed=float("nan"), max_step=1.0) == 0.5
    assert eng._clamp(prev=0.5, proposed=float("inf"), max_step=1.0) == 0.5
    # finite behaviour is untouched
    assert eng._clamp(prev=0.0, proposed=999.0, max_step=1.0) == 1.0
    assert eng._clamp(prev=0.0, proposed=-999.0, max_step=1.0) == -1.0
    assert eng._clamp(prev=0.0, proposed=0.25, max_step=1.0) == 0.25


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
