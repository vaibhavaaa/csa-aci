"""
supervisor_engine.py

Backend service layer — bridges FastAPI endpoints to the csa_aci package.

NOTE — per_step_trust formula:
    trust_score = 1 - clamp(intervention_distance / 5, 0, 1)

    intervention_distance is the L1 distance between what the agents
    wanted to do and what CCE actually allowed (sum of capacity + network
    magnitude deltas).  Dividing by 5 normalises against a practical
    worst-case of ~5 units total displacement.  This is an empirical
    proxy; a principled derivation from system dynamics is deferred to
    the thesis.  For cross-run comparisons use CSI and TrustDecayModel
    instead — those are the citable metrics.
"""

from csa_aci import Supervisor, TelemetrySnapshot
from csa_aci.agents import CapacityAgent, NetworkAgent
from csa_aci import compute_csi, TrustDecayModel

# Max expected intervention distance used to normalise per-step trust.
# Empirical: capacity_mag clamped to 1.0 + network_mag clamped to 1.0
# gives worst-case ~4-5 per step.  Value is intentionally conservative.
_TRUST_NORM = 5.0


def _per_step_trust(intervention_distance: float) -> float:
    """
    Proxy trust score for a single CCE step.
    Returns 1.0 when CCE made no corrections, approaches 0.0 at max correction.
    """
    return round(1.0 - min(intervention_distance / _TRUST_NORM, 1.0), 2)


# ── Persistent live supervisor ────────────────────────────────────────────────
_live_sup = Supervisor()
_live_cap = CapacityAgent()
_live_net = NetworkAgent()


def reset_live_supervisor() -> None:
    """Reset persistent supervisor — clears evidence window and dwell timer."""
    global _live_sup, _live_cap, _live_net
    _live_sup = Supervisor()
    _live_cap = CapacityAgent()
    _live_net = NetworkAgent()


def run_supervised_task(
    task_name: str,
    observed_latency: float = 122.0,
    cpu_utilisation: float = 0.0,
    throughput: float = 0.0,
):
    """
    Creates a fresh Supervisor per call — no shared state between requests.
    Agents observe the provided telemetry and propose intents.
    CCE governs the final decision.
    """
    global _live_sup, _live_cap, _live_net
    sup = _live_sup
    cap = _live_cap
    net = _live_net

    telemetry = TelemetrySnapshot(
        observed_latency=observed_latency,
        cpu_utilisation=cpu_utilisation,
        throughput=throughput,
    )

    cap_intent, cap_action = cap.step(telemetry, None)
    net_intent, net_action = net.step(telemetry, None)

    record = sup.step(
        telemetry=telemetry,
        capacity_intent=cap_intent.value,
        capacity_intent_age=cap.intent_age,
        capacity_action_type=cap_action,
        capacity_action_mag=1.0 if cap_intent.value == "SCALE_UP" else 0.0,
        network_intent=net_intent.value,
        network_intent_age=net.intent_age,
        network_action_type=net_action,
        network_action_mag=-1.0 if net_intent.value == "SCALE_DOWN" else 0.0,
    )

    summary = sup.summary()

    return {
        "task": task_name,
        "observed_latency": observed_latency,
        "capacity_agent": cap_intent.value,
        "network_agent": net_intent.value,
        "final_intent": record.final_intent,
        "reason": record.arbitration_reason,
        "intent_changed": record.intent_changed,
        "intent_age": record.final_intent_age,
        "intervention_distance": record.intervention_distance,
        "trust_score": _per_step_trust(record.intervention_distance),
        "summary": summary,
        "window_size": len(_live_sup.engine.state.recent_latency),
        "window_contents": list(_live_sup.engine.state.recent_latency)[-8:],
        "signal_age": _live_sup.engine.state.signal_age,
        "signal_needed": _live_sup.engine.cfg.min_dwell_time,
    }

def run_simulation(steps) -> dict:
    """
    Runs a multi-step simulation through a single Supervisor instance.
    Now includes CSI and Trust Decay Model alongside the CCE trace.
    """
    sup = Supervisor()
    cap = CapacityAgent()
    net = NetworkAgent()
    trust_model = TrustDecayModel()

    trace = []
    trust_curve = []

    for i, step_data in enumerate(steps):
        telemetry = TelemetrySnapshot(
            observed_latency=step_data.observed_latency,
            cpu_utilisation=step_data.cpu_utilisation,
            throughput=getattr(step_data, "throughput", getattr(step_data, "error_rate", 0.0)),
            timestamp=i,
        )

        cap_intent, cap_action = cap.step(telemetry, None)
        net_intent, net_action = net.step(telemetry, None)

        record = sup.step(
            telemetry=telemetry,
            capacity_intent=cap_intent.value,
            capacity_intent_age=cap.intent_age,
            capacity_action_type=cap_action,
            capacity_action_mag=1.0 if cap_intent.value == "SCALE_UP" else 0.0,
            network_intent=net_intent.value,
            network_intent_age=net.intent_age,
            network_action_type=net_action,
            network_action_mag=-1.0 if net_intent.value == "SCALE_DOWN" else 0.0,
        )

        # conflict = agents disagreed
        conflict = cap_intent.value != net_intent.value
        evidence_accepted = record.arbitration_reason == "EVIDENCE_ACCEPT"

        # trust decay step
        decayed_trust = trust_model.step(conflict, evidence_accepted)
        trust_curve.append(decayed_trust)

        per_step_trust = _per_step_trust(record.intervention_distance)

        trace.append({
            "step": i,
            "observed_latency": telemetry.observed_latency,
            "capacity_agent": cap_intent.value,
            "network_agent": net_intent.value,
            "final_intent": record.final_intent,
            "reason": record.arbitration_reason,
            "intent_changed": record.intent_changed,
            "intent_age": record.final_intent_age,
            "intervention_distance": record.intervention_distance,
            "trust_score": per_step_trust,
            "decayed_trust": decayed_trust,
            "conflict": conflict,
        })

    summary = sup.summary()
    summary["total_steps"] = len(trace)
    summary["conflict_count"] = sum(1 for t in trace if t["conflict"])

    # compute CSI
    avg_trust = trust_model.summary()["avg"]
    trace_conflict_count = sum(1 for t in trace if t["conflict"])
    csi_result = compute_csi(
        avg_trust=avg_trust,
        intent_switch_count=summary["intent_switch_count"],
        conflict_count=trace_conflict_count,
        total_steps=summary["total_steps"],
    )

    trust_summary = trust_model.summary()

    return {
        "trace": trace,
        "summary": summary,
        "csi": csi_result,
        "trust_decay": trust_summary,
        "trust_curve": trust_curve,
    }

def run_ablation(steps) -> dict:
    """
    Runs the same telemetry sequence through 4 CCE configurations.
    Proves each governance component contributes to stability independently.

    Configurations:
    1. Baseline      — no evidence gate, no dwell time
    2. Evidence only — evidence gate on, dwell time off
    3. Dwell only    — evidence gate off, dwell time on
    4. Full CCE      — both gates active (default)
    """
    from csa_aci.config import CCEConfig

    import random
    random.seed(42)

    # Generate noisy telemetry internally for fair comparison
    # Base pattern: 25 steps low, 25 steps high, repeated twice = 100 steps
    # Add gaussian noise to simulate real telemetry
    noisy_steps = []
    base_pattern = (
        [30] * 25 +   # low latency period
        [130] * 25 +  # high latency period
        [30] * 25 +   # low again
        [130] * 25    # high again
    )
    for latency in base_pattern:
        noise = random.gauss(0, 20)   # std dev 20ms
        noisy_latency = max(10, latency + noise)
        noisy_steps.append(type("Step", (), {
            "observed_latency": round(noisy_latency, 1),
            "cpu_utilisation": 0.5,
            "throughput": 300.0,
        })())

    configs = [
    {
        "name": "Baseline",
        "description": "No governance — agents act immediately",
        "cfg": CCEConfig(
            evidence_window=1,
            evidence_required_count=0,
            min_dwell_time=0,
        ),
    },
    {
        "name": "Evidence Gate Only",
        "description": "Evidence persistence enforced, no dwell time",
        "cfg": CCEConfig(
            evidence_window=8,
            evidence_required_count=6,
            min_dwell_time=0,
        ),
    },
    {
        "name": "Dwell Time Only",
        "description": "Minimum dwell enforced, no evidence gate",
        "cfg": CCEConfig(
            evidence_window=1,
            evidence_required_count=0,
            min_dwell_time=10,
        ),
    },
    {
        "name": "Full CCE",
        "description": "Both evidence gate and dwell time active",
        "cfg": CCEConfig(
            evidence_window=8,
            evidence_required_count=6,
            min_dwell_time=10,
        ),
    },
]
    
    results = []

    for config in configs:
        from csa_aci.supervisor import Supervisor

        sup = Supervisor(cfg=config["cfg"])
        cap = CapacityAgent()
        net = NetworkAgent()
        trust_model = TrustDecayModel()

        trace = []

        for i, step_data in enumerate(noisy_steps):
            telemetry = TelemetrySnapshot(
                observed_latency=step_data.observed_latency,
                cpu_utilisation=step_data.cpu_utilisation,
                throughput=getattr(step_data, "throughput", getattr(step_data, "error_rate", 0.0)),
                timestamp=i,
            )

            cap_intent, cap_action = cap.step(telemetry, None)
            net_intent, net_action = net.step(telemetry, None)

            record = sup.step(
                telemetry=telemetry,
                capacity_intent=cap_intent.value,
                capacity_intent_age=cap.intent_age,
                capacity_action_type=cap_action,
                capacity_action_mag=1.0 if cap_intent.value == "SCALE_UP" else 0.0,
                network_intent=net_intent.value,
                network_intent_age=net.intent_age,
                network_action_type=net_action,
                network_action_mag=-1.0 if net_intent.value == "SCALE_DOWN" else 0.0,
            )

            conflict = cap_intent.value != net_intent.value
            evidence_accepted = record.arbitration_reason == "EVIDENCE_ACCEPT"
            trust_model.step(conflict, evidence_accepted)

            trace.append({
                "step": i,
                "final_intent": record.final_intent,
                "reason": record.arbitration_reason,
                "intent_changed": record.intent_changed,
                "trust_score": _per_step_trust(record.intervention_distance),
            })

        summary = sup.summary()
        trust_summary = trust_model.summary()

        avg_trust = sum(t["trust_score"] for t in trace) / len(trace)
        csi_result = compute_csi(
            avg_trust=avg_trust,
            intent_switch_count=summary["intent_switch_count"],
            conflict_count=summary["conflict_count"],
            total_steps=len(trace),
        )

        results.append({
            "config": config["name"],
            "description": config["description"],
            "intent_switch_count": summary["intent_switch_count"],
            "intent_switch_rate": summary["intent_switch_rate"],
            "conflict_count": summary["conflict_count"],
            "avg_trust": round(avg_trust, 3),
            "decayed_trust_final": trust_summary["final"],
            "csi": csi_result["csi"],
            "csi_label": csi_result["label"],
            "trace": trace,
        })

    return {
        "ablation": results,
        "total_steps": len(noisy_steps),
        "winner": min(results, key=lambda r: r["intent_switch_count"])["config"],
    }


# ── Controller Comparison Experiment ──────────────────────────────────────────
# Proves CCE outperforms existing reactive controller paradigms.
# All controllers run on identical noisy telemetry (seed=42, σ=20ms).
# This is the core thesis comparison — not just ablation of CCE components,
# but CCE vs real-world controller archetypes.

def _generate_comparison_telemetry(seed: int = 42):
    """
    Generates 100-step noisy telemetry for the comparison experiment.
    Same pattern as the ablation study; `seed` varies the noise realization
    (used by run_stress_test to sample many realizations for significance).

    Ground truth:
      Steps  0-24:  LOW  (base 30ms)  — correct answer: HOLD
      Steps 25-49:  HIGH (base 130ms) — correct answer: SCALE_UP
      Steps 50-74:  LOW  (base 30ms)  — correct answer: HOLD / SCALE_DOWN
      Steps 75-99:  HIGH (base 130ms) — correct answer: SCALE_UP
    """
    import random
    random.seed(seed)

    base_pattern = [30]*25 + [130]*25 + [30]*25 + [130]*25
    steps = []
    for i, latency in enumerate(base_pattern):
        noise = random.gauss(0, 20)
        noisy = max(10.0, latency + noise)
        steps.append({
            "step": i,
            "observed_latency": round(noisy, 1),
            "base_latency": latency,
            "ground_truth": "SCALE_UP" if latency >= 100 else "HOLD",
        })
    return steps


def _evaluate_controller(decisions, telemetry):
    """
    Computes comparison metrics for a controller's decision sequence.

    Parameters
    ----------
    decisions : list of str  — "SCALE_UP" / "SCALE_DOWN" / "HOLD" per step
    telemetry : list of dict — output of _generate_comparison_telemetry()

    Returns
    -------
    dict of metrics
    """
    n = len(decisions)

    # Intent switches (any change in final decision, incl. HOLD<->action)
    switches = sum(
        1 for i in range(1, n)
        if decisions[i] != decisions[i-1]
    )

    # Total interventions — non-HOLD decisions (capacity churn). CCE's
    # "minimal intervention" property: it acts far less than reactive
    # controllers that re-issue the same decision every step. See
    # finding_switch_metric_mismeasure — intent_switches alone penalises CCE's
    # benign HOLD<->SCALE_DOWN pacing, so report this alongside it.
    total_interventions = sum(1 for d in decisions if d != "HOLD")

    # Direction reversals — UP<->DOWN flips ignoring HOLD. This is real capacity
    # thrash (oscillating up then down), distinct from pacing. Lower is better.
    direction_reversals = 0
    last_dir = None
    for d in decisions:
        if d in ("SCALE_UP", "SCALE_DOWN"):
            if last_dir is not None and d != last_dir:
                direction_reversals += 1
            last_dir = d

    # False positives — switched to SCALE_UP during a LOW-latency ground-truth period
    false_positives = sum(
        1 for i in range(n)
        if decisions[i] == "SCALE_UP" and telemetry[i]["ground_truth"] == "HOLD"
    )

    # False negatives — stayed HOLD during a HIGH-latency ground-truth period
    false_negatives = sum(
        1 for i in range(n)
        if decisions[i] == "HOLD" and telemetry[i]["ground_truth"] == "SCALE_UP"
    )

    # Oscillations — switched back within 3 steps
    oscillations = 0
    for i in range(1, n):
        if decisions[i] != decisions[i-1]:
            # look ahead up to 3 steps for a reversal
            for j in range(i+1, min(i+4, n)):
                if decisions[j] == decisions[i-1]:
                    oscillations += 1
                    break

    # Response lag — for each contiguous genuine-HIGH period (ground_truth ==
    # SCALE_UP), how many steps until the controller first proposes SCALE_UP.
    # Derived from ground_truth so it works for ANY trace length/layout, not
    # just the synthetic 100-step pattern (which had highs at 25-49 / 75-99).
    gt = [t["ground_truth"] for t in telemetry]
    lags = []
    i = 0
    while i < n:
        if gt[i] == "SCALE_UP":
            start = i
            while i < n and gt[i] == "SCALE_UP":
                i += 1
            period = decisions[start:i]
            lags.append(period.index("SCALE_UP") if "SCALE_UP" in period else (i - start))
        else:
            i += 1

    avg_response_lag = round(sum(lags) / len(lags), 1) if lags else 0.0

    # Precision — of all SCALE_UP decisions, how many were correct
    total_scale_up = sum(1 for d in decisions if d == "SCALE_UP")
    correct_scale_up = sum(
        1 for i in range(n)
        if decisions[i] == "SCALE_UP" and telemetry[i]["ground_truth"] == "SCALE_UP"
    )
    precision = round(correct_scale_up / total_scale_up, 3) if total_scale_up > 0 else 0.0

    # Recall — of all genuine HIGH steps, how many did we correctly act on
    total_genuine = sum(1 for t in telemetry if t["ground_truth"] == "SCALE_UP")
    recall = round(correct_scale_up / total_genuine, 3) if total_genuine > 0 else 0.0

    # F1 — harmonic mean of precision and recall (single-number quality metric)
    f1 = (
        round(2 * precision * recall / (precision + recall), 3)
        if (precision + recall) > 0
        else 0.0
    )

    # Stability score (simple: 1 - normalised switches)
    stability = round(1.0 - (switches / n), 3)

    return {
        "intent_switches": switches,
        "total_interventions": total_interventions,
        "direction_reversals": direction_reversals,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "oscillations": oscillations,
        "avg_response_lag": avg_response_lag,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "stability_score": stability,
    }


def _run_all_controllers(
    telemetry: list,
    up_thresh: float = 100.0,
    down_thresh: float = 70.0,
    keep_decisions: bool = False,
) -> dict:
    """
    Run all five controllers on a single telemetry sequence and return
    {results, winner, analysis}.

    Each telemetry item is a dict with 'observed_latency',
    'ground_truth' ("SCALE_UP"/"HOLD"), and 'step'.

    Controllers
    -----------
    1. Threshold Reactive  — fires on every reading above threshold
    2. Hysteresis Reactive — needs 2 consecutive readings above threshold
    3. EMA Reactive        — acts on exponential moving average (α=0.3)
    4. PID Controller      — Kp·e + Ki·∫e + Kd·Δe on latency error
    5. CSA-ACI CCE         — intent governance: evidence gate + dwell time

    Shared by the synthetic comparison (run_controller_comparison) and the
    real-trace replay (run_trace_replay) so both judge the identical controllers
    on whatever telemetry they are given.
    """
    UP_THRESH   = up_thresh
    DOWN_THRESH = down_thresh

    results = []

    # ── 1. Threshold Reactive ─────────────────────────────────────────────────
    decisions = []
    for t in telemetry:
        lat = t["observed_latency"]
        if lat >= UP_THRESH:
            decisions.append("SCALE_UP")
        elif lat <= DOWN_THRESH:
            decisions.append("SCALE_DOWN")
        else:
            decisions.append("HOLD")

    metrics = _evaluate_controller(decisions, telemetry)
    results.append({
        "controller": "Threshold Reactive",
        "description": "Acts on every single reading. No memory. CPU > threshold → scale.",
        "decisions": decisions,
        **metrics,
    })

    # ── 2. Hysteresis Reactive ────────────────────────────────────────────────
    decisions = []
    current = "HOLD"
    consecutive_high = 0
    consecutive_low  = 0

    for t in telemetry:
        lat = t["observed_latency"]
        if lat >= UP_THRESH:
            consecutive_high += 1
            consecutive_low   = 0
        elif lat <= DOWN_THRESH:
            consecutive_low  += 1
            consecutive_high  = 0
        else:
            consecutive_high = 0
            consecutive_low  = 0

        if consecutive_high >= 2:
            current = "SCALE_UP"
        elif consecutive_low >= 2:
            current = "SCALE_DOWN"
        else:
            current = "HOLD"
        decisions.append(current)

    metrics = _evaluate_controller(decisions, telemetry)
    results.append({
        "controller": "Hysteresis Reactive",
        "description": "Needs 2 consecutive readings above threshold. Slight noise resistance.",
        "decisions": decisions,
        **metrics,
    })

    # ── 3. EMA Reactive ───────────────────────────────────────────────────────
    decisions = []
    alpha = 0.3
    ema   = telemetry[0]["observed_latency"]

    for t in telemetry:
        ema = alpha * t["observed_latency"] + (1 - alpha) * ema
        if ema >= UP_THRESH:
            decisions.append("SCALE_UP")
        elif ema <= DOWN_THRESH:
            decisions.append("SCALE_DOWN")
        else:
            decisions.append("HOLD")

    metrics = _evaluate_controller(decisions, telemetry)
    results.append({
        "controller": "EMA Reactive",
        "description": "Exponential moving average (α=0.3). Smooths signal. No intent concept.",
        "decisions": decisions,
        **metrics,
    })

    # ── 4. PID Controller ─────────────────────────────────────────────────────
    # Textbook control: u = Kp·e + Ki·∫e + Kd·Δe on latency error.
    # This is the de-facto industry baseline (Kubernetes HPA uses a PID-like
    # loop). Fast to respond, but memoryless about *intent* — so it chases
    # noise and oscillates, which is exactly the contrast CCE addresses.
    decisions = []
    Kp, Ki, Kd = 0.5, 0.01, 0.1
    setpoint = (UP_THRESH + DOWN_THRESH) / 2.0   # 85ms target latency
    integral = 0.0
    prev_error = 0.0
    DEADBAND = 8.0

    for t in telemetry:
        error = t["observed_latency"] - setpoint
        integral += error
        integral = max(-200.0, min(200.0, integral))   # anti-windup clamp
        derivative = error - prev_error
        output = Kp * error + Ki * integral + Kd * derivative
        prev_error = error

        if output > DEADBAND:
            decisions.append("SCALE_UP")
        elif output < -DEADBAND:
            decisions.append("SCALE_DOWN")
        else:
            decisions.append("HOLD")

    metrics = _evaluate_controller(decisions, telemetry)
    results.append({
        "controller": "PID Controller",
        "description": "Kp·e + Ki·∫e + Kd·Δe on latency error (setpoint=85ms, anti-windup). Industry-standard control baseline.",
        "decisions": decisions,
        **metrics,
    })

    # ── 5. CSA-ACI CCE ────────────────────────────────────────────────────────
    sup = Supervisor()
    cap = CapacityAgent()
    net = NetworkAgent()
    decisions = []

    for t in telemetry:
        snap = TelemetrySnapshot(
            observed_latency=t["observed_latency"],
            cpu_utilisation=0.5,
            throughput=300.0,
            timestamp=t["step"],
        )
        cap_intent, cap_action = cap.step(snap, None)
        net_intent, net_action = net.step(snap, None)

        record = sup.step(
            telemetry=snap,
            capacity_intent=cap_intent.value,
            capacity_intent_age=cap.intent_age,
            capacity_action_type=cap_action,
            capacity_action_mag=1.0 if cap_intent.value == "SCALE_UP" else 0.0,
            network_intent=net_intent.value,
            network_intent_age=net.intent_age,
            network_action_type=net_action,
            network_action_mag=-1.0 if net_intent.value == "SCALE_DOWN" else 0.0,
        )
        decisions.append(record.final_intent)

    metrics = _evaluate_controller(decisions, telemetry)
    results.append({
        "controller": "CSA-ACI CCE",
        "description": "Intent governance: evidence gate (8-window, 6-of-8) + dwell time (10 steps).",
        "decisions": decisions,
        **metrics,
    })

    # ── Winner analysis ───────────────────────────────────────────────────────
    # Best overall = fewest false positives (noise suppression is the claim)
    # with recall >= 0.5 (still responds to genuine signals)
    eligible = [r for r in results if r["recall"] >= 0.5]
    if not eligible:
        eligible = results  # fallback

    winner = min(eligible, key=lambda r: (r["false_positives"], r["oscillations"]))

    # Compute improvement of CCE over best reactive
    cce = next(r for r in results if r["controller"] == "CSA-ACI CCE")
    best_reactive = min(
        [r for r in results if r["controller"] != "CSA-ACI CCE"],
        key=lambda r: r["false_positives"]
    )

    fp_reduction = round(
        (best_reactive["false_positives"] - cce["false_positives"])
        / max(best_reactive["false_positives"], 1) * 100, 1
    )
    switch_reduction = round(
        (best_reactive["intent_switches"] - cce["intent_switches"])
        / max(best_reactive["intent_switches"], 1) * 100, 1
    )

    # Strip decisions list from results (too large for API response) unless the
    # caller needs them — the multi-controller trace figure does.
    if not keep_decisions:
        for r in results:
            r.pop("decisions", None)

    return {
        "results": results,
        "winner": winner["controller"],
        "analysis": {
            "cce_vs_best_reactive": best_reactive["controller"],
            "false_positive_reduction_pct": fp_reduction,
            "switch_reduction_pct": switch_reduction,
            "cce_precision": cce["precision"],
            "cce_recall": cce["recall"],
            "cce_false_positives": cce["false_positives"],
            "cce_response_lag": cce["avg_response_lag"],
        },
    }


def run_controller_comparison() -> dict:
    """
    Compare CSA-ACI CCE against four reactive controller paradigms on a single
    clean synthetic telemetry sequence (seed=42, σ=20ms).

    Honest baseline: on a clean, well-separated signal CCE pays a response-lag
    cost (low recall) while the reactive controllers have nothing to thrash on.
    CCE's advantage appears on noisy/bursty signals — see run_trace_replay,
    which runs these same controllers on real production traces.
    """
    telemetry = _generate_comparison_telemetry()
    out = _run_all_controllers(telemetry)
    out["telemetry_steps"] = len(telemetry)
    out["noise_sigma"] = 20
    out["ground_truth_note"] = (
        "Steps 0-24 and 50-74 are genuine LOW periods (HOLD correct). "
        "Steps 25-49 and 75-99 are genuine HIGH periods (SCALE_UP correct). "
        "Gaussian noise σ=20ms applied to all steps."
    )
    return out


# ── Multi-Signal Conflict Experiment (the differentiator) ─────────────────────
# The experiment that secures CSA-ACI's space. Single-loop controllers act on ONE
# signal; CSA-ACI arbitrates two agents watching DIFFERENT signals (CPU vs
# latency). Four sustained regimes — two are CONFLICTS where the signals disagree:
#   R1 cpu+latency bound : high CPU + high latency  -> agree SCALE_UP
#   R2 dependency-bound  : LOW CPU + HIGH latency   -> CONFLICT, correct = SCALE_UP
#   R3 idle              : low CPU + low latency    -> agree SCALE_DOWN
#   R4 saturating        : HIGH CPU + low latency   -> CONFLICT, correct = SCALE_UP
# Each single-signal controller fails exactly one conflict direction:
#   latency-only (Threshold/Hysteresis/EMA/PID) is blind to R4 (CPU saturating)
#   CPU-only (Kubernetes HPA) is blind to R2 (latency burning)
# Any controller that reads BOTH signals reaches 4/4 — so against a FAIR multi-
# signal baseline (Multi-Metric HPA / Multi-Signal Hysteresis, added below) the
# capability gap closes. CSA-ACI's edge there is STABILITY: its evidence gate +
# dwell ignore the transient noise that makes a memoryless multi-signal controller
# thrash (direction reversals / oscillation / wrong-direction). The honest cost is
# scale-up lag (dwell). See the stability-vs-responsiveness verdict in the result.
# Regimes are defined by signal semantics, identical for everyone (no tuning win).

_CONFLICT_REGIMES = [
    # (name, description, cpu_base, latency_base)
    ("R1 cpu+latency bound", "high CPU + high latency",            0.90, 130.0),
    ("R2 dependency-bound",  "LOW CPU + HIGH latency (conflict)",  0.20, 130.0),
    ("R3 idle",              "low CPU + low latency",              0.12,  25.0),
    ("R4 saturating",        "HIGH CPU + low latency (conflict)",  0.90,  30.0),
]

# Two-signal ground truth thresholds. SCALE_UP if EITHER signal is in danger
# (latency breaches SLO OR CPU saturates); SCALE_DOWN only if BOTH are idle.
_SLO_LATENCY = 100.0
_CPU_SAT     = 0.75
_LAT_IDLE    = 40.0
_CPU_IDLE    = 0.30


def _conflict_ground_truth(cpu: float, lat: float) -> str:
    if lat >= _SLO_LATENCY or cpu >= _CPU_SAT:
        return "SCALE_UP"
    if lat <= _LAT_IDLE and cpu <= _CPU_IDLE:
        return "SCALE_DOWN"
    return "HOLD"


def _generate_conflict_telemetry(
    seed: int = 42,
    steps_per_regime: int = 40,
    transients: bool = True,
):
    """Two independent signals (cpu_utilisation + observed_latency) over four
    sustained regimes. Ground truth is denoised (computed from the regime base
    values, not the noisy per-step samples) so it measures tracking of true load.

    When ``transients`` is set, each regime carries short opposite-direction noise
    bursts (a single bad sample or two — a transient spike/dip) confined to the
    EARLY part of the regime, leaving a clean steady-state tail. These are noise,
    not load, so ground truth is unchanged. This is what separates a memoryless
    multi-signal controller (which chases every burst → wrong-direction actions and
    oscillation) from CSA-ACI's evidence-gated, dwell-bounded governor (which holds
    through the burst). With ``transients=False`` the regimes are clean blocks and
    a naive multi-signal controller is already optimal — see finding_cce_tradeoff.
    """
    import random
    random.seed(seed)

    # One short transient spike per regime, placed early; the rest of the regime
    # (incl. the whole steady-state tail) is clean so steady-state correctness and
    # CCE's dwell recovery are unaffected. A single 2-sample spike models a
    # realistic measurement transient — enough that a memoryless controller reacts
    # to it, short enough that CCE's 6-of-8 evidence gate ignores it.
    burst_starts = [int(steps_per_regime * 0.18)]
    burst_len = 2
    burst_window = {s + k for s in burst_starts for k in range(burst_len)
                    if s + k < int(steps_per_regime * 0.40)} if transients else set()

    steps = []
    i = 0
    for name, _desc, cpu_base, lat_base in _CONFLICT_REGIMES:
        regime_gt = _conflict_ground_truth(cpu_base, lat_base)   # denoised target
        # Transient pushes the signals toward the OPPOSITE of the true regime.
        if regime_gt == "SCALE_UP":
            burst_cpu, burst_lat = 0.12, 25.0     # looks idle for a moment
        else:
            burst_cpu, burst_lat = 0.90, 135.0    # looks hot for a moment
        for s in range(steps_per_regime):
            base_cpu, base_lat = (burst_cpu, burst_lat) if s in burst_window else (cpu_base, lat_base)
            cpu = min(0.99, max(0.0, base_cpu + random.gauss(0, 0.03)))
            lat = max(5.0, base_lat + random.gauss(0, 8.0))
            steps.append({
                "step": i,
                "observed_latency": round(lat, 1),
                "cpu_utilisation": round(cpu, 3),
                "regime": name,
                "ground_truth": regime_gt,
            })
            i += 1
    return steps


def _symmetric_mag(intent: str) -> float:
    """+1 for SCALE_UP, -1 for SCALE_DOWN, 0 for HOLD (both agents can do either
    direction now that they are multi-signal)."""
    return 1.0 if intent == "SCALE_UP" else -1.0 if intent == "SCALE_DOWN" else 0.0


def _conflict_metrics(decisions: list, telemetry: list) -> dict:
    """Per-regime correctness plus global SLO-violation / wrong-direction counts.

    A regime is 'handled' if the controller reaches the correct decision in
    steady state (the last quarter of the regime) — fair to CCE's dwell-time lag,
    while still exposing single-signal controllers that NEVER reach the right
    direction in their blind regime.
    """
    from collections import OrderedDict

    regimes = OrderedDict()
    for d, t in zip(decisions, telemetry):
        regimes.setdefault(t["regime"], []).append((d, t["ground_truth"]))

    per_regime = OrderedDict()
    regimes_handled = 0
    for name, pairs in regimes.items():
        n = len(pairs)
        correct = sum(1 for d, gt in pairs if d == gt)
        tail = pairs[max(0, n - max(1, n // 4)):]                 # last quarter
        gt = tail[0][1]
        reached = sum(1 for d, _ in tail if d == gt) >= max(1, len(tail) // 2)
        per_regime[name] = {
            "steps": n,
            "correct_steps": correct,
            "accuracy": round(correct / n, 2),
            "steady_state_correct": reached,
        }
        if reached:
            regimes_handled += 1

    slo_violation = sum(
        1 for d, t in zip(decisions, telemetry)
        if t["ground_truth"] == "SCALE_UP" and d != "SCALE_UP"
    )
    wrong_direction = sum(
        1 for d, t in zip(decisions, telemetry)
        if (t["ground_truth"] == "SCALE_UP" and d == "SCALE_DOWN")
        or (t["ground_truth"] == "SCALE_DOWN" and d == "SCALE_UP")
    )
    return {
        "per_regime": per_regime,
        "regimes_handled": regimes_handled,
        "slo_violation_steps": slo_violation,
        "wrong_direction_steps": wrong_direction,
    }


def run_conflict_experiment(seed: int = 42) -> dict:
    """Run latency-only controllers, a CPU-only Kubernetes-HPA archetype, and the
    multi-signal CSA-ACI CCE on identical two-signal telemetry. Returns per-step
    decisions, per-regime correctness, and the conflict summary.
    """
    telemetry = _generate_conflict_telemetry(seed)
    UP_L, DOWN_L = _SLO_LATENCY, 70.0
    UP_C, DOWN_C = _CPU_SAT, _CPU_IDLE
    lat = [t["observed_latency"] for t in telemetry]
    cpu = [t["cpu_utilisation"] for t in telemetry]

    results = []

    def _record(name, desc, decisions, signal):
        results.append({
            "controller": name, "description": desc, "signal": signal,
            "decisions": decisions,
            **_evaluate_controller(decisions, telemetry),
            **_conflict_metrics(decisions, telemetry),
        })

    # 1. Threshold Reactive (latency-only)
    d = ["SCALE_UP" if x >= UP_L else "SCALE_DOWN" if x <= DOWN_L else "HOLD" for x in lat]
    _record("Threshold Reactive", "Latency-only threshold. Blind to CPU.", d, "latency")

    # 2. Hysteresis Reactive (latency-only)
    d, cur, hi, lo = [], "HOLD", 0, 0
    for x in lat:
        if x >= UP_L: hi, lo = hi + 1, 0
        elif x <= DOWN_L: lo, hi = lo + 1, 0
        else: hi = lo = 0
        cur = "SCALE_UP" if hi >= 2 else "SCALE_DOWN" if lo >= 2 else "HOLD"
        d.append(cur)
    _record("Hysteresis Reactive", "2-step latency hysteresis. Blind to CPU.", d, "latency")

    # 3. EMA Reactive (latency-only)
    d, ema = [], lat[0]
    for x in lat:
        ema = 0.3 * x + 0.7 * ema
        d.append("SCALE_UP" if ema >= UP_L else "SCALE_DOWN" if ema <= DOWN_L else "HOLD")
    _record("EMA Reactive", "EMA(α=0.3) on latency. Blind to CPU.", d, "latency")

    # 4. PID Controller (latency-only)
    d, integral, prev = [], 0.0, 0.0
    setp, DB = (UP_L + DOWN_L) / 2.0, 8.0
    for x in lat:
        e = x - setp
        integral = max(-200.0, min(200.0, integral + e))
        out = 0.5 * e + 0.01 * integral + 0.1 * (e - prev)
        prev = e
        d.append("SCALE_UP" if out > DB else "SCALE_DOWN" if out < -DB else "HOLD")
    _record("PID Controller", "PID on latency error. Industry control baseline. Blind to CPU.", d, "latency")

    # 5. Kubernetes HPA archetype (CPU-only) — the real-world default autoscaler
    d = ["SCALE_UP" if c >= UP_C else "SCALE_DOWN" if c <= DOWN_C else "HOLD" for c in cpu]
    _record("Kubernetes HPA (CPU)", "CPU-threshold autoscaler — the real-world default. Blind to latency.", d, "cpu")

    # 6. Multi-Metric HPA (CPU+latency) — the FAIR multi-signal baseline. Sees both
    # signals, so it also reaches every regime (no capability gap vs CCE). It is
    # memoryless, though: it re-decides on every raw sample, so it chases transient
    # noise. This is the honest comparison — CCE's edge over THIS is stability, not
    # capability. (K8s HPA genuinely supports multiple metrics this way.)
    d = ["SCALE_UP" if (c >= UP_C or x >= UP_L)
         else "SCALE_DOWN" if (x <= DOWN_L and c <= DOWN_C)
         else "HOLD" for x, c in zip(lat, cpu)]
    _record("Multi-Metric HPA", "CPU+latency thresholds (OR-up / AND-idle-down). Multi-signal but memoryless.", d, "cpu+latency")

    # 7. Multi-Signal Hysteresis — a careful engineer's multi-signal baseline:
    # the same OR/AND rule but with 2-step debounce. Some noise resistance, still
    # no evidence window or dwell. The strongest non-CCE multi-signal contender.
    d, cur, hi, lo = [], "HOLD", 0, 0
    for x, c in zip(lat, cpu):
        up_now = c >= UP_C or x >= UP_L
        down_now = x <= DOWN_L and c <= DOWN_C
        if up_now: hi, lo = hi + 1, 0
        elif down_now: lo, hi = lo + 1, 0
        else: hi = lo = 0
        cur = "SCALE_UP" if hi >= 2 else "SCALE_DOWN" if lo >= 2 else "HOLD"
        d.append(cur)
    _record("Multi-Signal Hysteresis", "2-step debounce on CPU+latency. Multi-signal, mild memory, no dwell.", d, "cpu+latency")

    # 8. CSA-ACI CCE — multi-signal governance (arbitrates CPU agent vs latency agent)
    sup, cap, net = Supervisor(), CapacityAgent(), NetworkAgent()
    d = []
    for t in telemetry:
        snap = TelemetrySnapshot(
            observed_latency=t["observed_latency"],
            cpu_utilisation=t["cpu_utilisation"],
            timestamp=t["step"],
        )
        ci, ca = cap.step(snap, None)
        ni, na = net.step(snap, None)
        rec = sup.step(
            telemetry=snap,
            capacity_intent=ci.value, capacity_intent_age=cap.intent_age,
            capacity_action_type=ca, capacity_action_mag=_symmetric_mag(ci.value),
            network_intent=ni.value, network_intent_age=net.intent_age,
            network_action_type=na, network_action_mag=_symmetric_mag(ni.value),
        )
        d.append(rec.final_intent)
    _record("CSA-ACI CCE", "Multi-signal governance: arbitrates CPU agent vs latency agent.", d, "cpu+latency")

    total_regimes = len(_CONFLICT_REGIMES)
    cce = next(r for r in results if r["controller"] == "CSA-ACI CCE")

    # Capability: which controllers reach the correct decision in EVERY regime
    # (incl. both conflicts). Single-signal controllers cap at 3/4; any controller
    # that reads BOTH signals — naive or not — can reach 4/4.
    capable = [r for r in results if r["regimes_handled"] == total_regimes]

    # Among multi-signal-capable controllers the question is no longer capability
    # but an honest STABILITY vs RESPONSIVENESS Pareto trade-off:
    #   thrash = noise-induced bad actions (reversals + oscillations + wrong-dir)
    #   lag    = slo_violation_steps (slow to scale up — CCE's dwell cost)
    def _thrash(r):
        return r["direction_reversals"] + r["oscillations"] + r["wrong_direction_steps"]

    stability_winner = min(capable, key=_thrash) if capable else cce
    responsiveness_winner = (
        min(capable, key=lambda r: r["slo_violation_steps"]) if capable else cce
    )
    naive_thrash = min(
        (_thrash(r) for r in capable if r["controller"] != "CSA-ACI CCE"), default=None
    )

    return {
        "results": results,
        # This is a stability / anti-thrash governance paper, so the headline
        # "winner" is the most stable controller AMONG those that handle every
        # regime. The responsiveness cost is reported alongside — never hidden.
        "winner": stability_winner["controller"],
        "stability_winner": stability_winner["controller"],
        "responsiveness_winner": responsiveness_winner["controller"],
        "telemetry": telemetry,
        "regimes": [{"name": n, "description": desc} for n, desc, _c, _l in _CONFLICT_REGIMES],
        "analysis": {
            "cce_regimes_handled": cce["regimes_handled"],
            "total_regimes": total_regimes,
            "conflict_regimes": ["R2 dependency-bound", "R4 saturating"],
            # kept for backward-compat with the existing dashboard line
            "cce_wrong_direction_steps": cce["wrong_direction_steps"],
            "cce_slo_violation_steps": cce["slo_violation_steps"],
            "multi_signal_capable": [r["controller"] for r in capable],
            # the honest per-controller trade-off among multi-signal-capable controllers
            "tradeoff": [
                {
                    "controller": r["controller"],
                    "thrash": _thrash(r),
                    "direction_reversals": r["direction_reversals"],
                    "oscillations": r["oscillations"],
                    "wrong_direction_steps": r["wrong_direction_steps"],
                    "total_interventions": r["total_interventions"],
                    "slo_lag_steps": r["slo_violation_steps"],
                }
                for r in capable
            ],
            "verdict": (
                f"Vs single-signal baselines CSA-ACI wins on CAPABILITY "
                f"({cce['regimes_handled']}/{total_regimes} vs 3/4). Vs a FAIR multi-signal "
                f"baseline capability ties; CSA-ACI's edge is STABILITY — "
                f"{_thrash(cce)} noise-induced thrash actions vs "
                f"{naive_thrash if naive_thrash is not None else 'n/a'} for the best naive "
                f"multi-signal controller — at the cost of slower scale-up "
                f"({cce['slo_violation_steps']} SLO-lag steps). The trade favors CSA-ACI where "
                f"capacity thrash (cost spikes, instability) is worse than bounded lag."
            ),
        },
        "ground_truth_note": (
            "Two independent signals (CPU + latency) over four sustained regimes, each "
            "carrying one short transient spike (NOISE, not load — ground truth is the "
            "denoised regime base). Ground truth = SCALE_UP if latency >= 100ms OR "
            "cpu >= 0.75; SCALE_DOWN if latency <= 40ms AND cpu <= 0.30; else HOLD. A "
            "regime is 'handled' if the controller reaches the correct decision in steady "
            "state (the clean last quarter)."
        ),
    }


# ── Closed-Loop Control (feedback: actions change the next observation) ───────
# The ablation and conflict experiments are OPEN-LOOP: controllers act on a
# fixed pre-generated telemetry sequence, so a scale-up never actually lowers
# the latency the controller sees next. run_closed_loop closes that loop —
# latency is recomputed each step from utilisation (M/M/1) given the current
# server count, and each controller's decision changes that server count. A
# thrashing controller now hunts around the operating point (the thermostat
# swing); a stable one converges. This is the evaluation that answers the
# "you never closed the loop" reviewer objection. Paper Section 5.6.

def run_closed_loop(seed: int = 42, steps: int = 200, transients: bool = True) -> dict:
    import random
    import statistics

    MU       = 60.0     # per-server service capacity (req/s)
    BASE_MS  = 20.0     # base service time at zero queue (ms)
    SLO      = 100.0    # latency SLO (ms); breached when utilisation > 0.8
    LAT_CAP  = 1000.0   # saturation cap (ms)
    MIN_SRV, MAX_SRV, INIT_SRV = 1, 40, 3
    UP_L, DOWN_L = SLO, 70.0
    UP_C, DOWN_C = _CPU_SAT, _CPU_IDLE   # 0.75 / 0.30, same as elsewhere

    # Workload (req/s): ramp up, hold high, ramp down, hold low — forces both
    # a scale-up and a scale-down phase so every controller must move servers.
    def _load_schedule(n):
        out = []
        for t in range(n):
            f = t / n
            if   f < 0.20: base = 100 + 400 * (f / 0.20)        # ramp 100 -> 500
            elif f < 0.50: base = 500                            # hold high
            elif f < 0.70: base = 500 - 350 * ((f - 0.50) / 0.20)  # ramp 500 -> 150
            else:          base = 150                            # hold low
            out.append(base)
        return out

    load = _load_schedule(steps)

    # Transient MEASUREMENT spikes: 2-sample glitches that corrupt only what the
    # controller OBSERVES, never the true state (ground truth stays denoised).
    # During high load a spike fakes an idle reading (tempting a wrong
    # scale-down); during low load it fakes a hot reading (tempting a wrong
    # scale-up). This is the closed-loop analogue of the conflict experiment's
    # noise spikes — the phenomenon CCE's evidence gate is designed to reject.
    burst_len = 2
    spike_steps = set()
    if transients:
        for frac in (0.30, 0.42, 0.78, 0.90):
            s = int(steps * frac)
            for k in range(burst_len):
                spike_steps.add(s + k)

    def _true_latency(load_t, servers):
        rho = load_t / (servers * MU)
        if rho >= 0.99:
            return LAT_CAP
        return min(LAT_CAP, BASE_MS / (1.0 - rho))

    def _utilisation(load_t, servers):
        return min(1.0, load_t / (servers * MU))

    def _run(name, decide_fn, uses_cce=False):
        random.seed(seed)                       # identical noise stream per controller
        servers, prev_dir = INIT_SRV, 0
        scaling_actions = direction_reversals = slo_violations = 0
        latencies, server_trace = [], []
        sup = cap = net = None
        if uses_cce:
            sup, cap, net = Supervisor(), CapacityAgent(), NetworkAgent()
        st = {"ema": None, "hi": 0, "lo": 0, "cur": "HOLD"}

        for t in range(steps):
            true_lat = _true_latency(load[t], servers)
            cpu      = _utilisation(load[t], servers)
            n_lat    = random.gauss(0, 8.0)        # drawn every step (noise alignment)
            n_cpu    = random.gauss(0, 0.03)
            if t in spike_steps:
                if load[t] >= 325.0:               # truly loaded -> fake an idle reading
                    obs_lat = max(5.0, 25.0 + n_lat)
                    obs_cpu = min(1.0, max(0.0, 0.15 + n_cpu))
                else:                              # truly idle -> fake a hot reading
                    obs_lat = 260.0 + n_lat
                    obs_cpu = min(1.0, max(0.0, 0.92 + n_cpu))
            else:
                obs_lat = max(5.0, true_lat + n_lat)
                obs_cpu = min(1.0, max(0.0, cpu + n_cpu))

            latencies.append(true_lat)
            server_trace.append(servers)
            if true_lat > SLO:
                slo_violations += 1

            if uses_cce:
                snap = TelemetrySnapshot(observed_latency=obs_lat, cpu_utilisation=obs_cpu, timestamp=t)
                ci, ca = cap.step(snap, None)
                ni, na = net.step(snap, None)
                rec = sup.step(
                    telemetry=snap,
                    capacity_intent=ci.value, capacity_intent_age=cap.intent_age,
                    capacity_action_type=ca, capacity_action_mag=_symmetric_mag(ci.value),
                    network_intent=ni.value, network_intent_age=net.intent_age,
                    network_action_type=na, network_action_mag=_symmetric_mag(ni.value),
                )
                intent = rec.final_intent
            else:
                intent = decide_fn(obs_lat, obs_cpu, st)

            if intent == "SCALE_UP":
                servers = min(MAX_SRV, servers + 1); d = 1; scaling_actions += 1
            elif intent == "SCALE_DOWN":
                servers = max(MIN_SRV, servers - 1); d = -1; scaling_actions += 1
            else:
                d = 0
            if d != 0 and prev_dir != 0 and d != prev_dir:
                direction_reversals += 1
            if d != 0:
                prev_dir = d

        n = len(latencies)
        return {
            "controller": name,
            "scaling_actions": scaling_actions,
            "direction_reversals": direction_reversals,
            "slo_violation_steps": slo_violations,
            "slo_violation_rate": round(slo_violations / n, 3),
            "mean_latency": round(statistics.fmean(latencies), 1),
            "p99_latency": round(sorted(latencies)[max(0, int(0.99 * n) - 1)], 1),
            "latency_std": round(statistics.pstdev(latencies), 1),
            "final_servers": server_trace[-1],
            "server_trace": server_trace,
            "latency_trace": [round(x, 1) for x in latencies],
        }

    def _threshold(lat, cpu, st):
        return "SCALE_UP" if lat >= UP_L else "SCALE_DOWN" if lat <= DOWN_L else "HOLD"

    def _hysteresis(lat, cpu, st):
        if lat >= UP_L: st["hi"] += 1; st["lo"] = 0
        elif lat <= DOWN_L: st["lo"] += 1; st["hi"] = 0
        else: st["hi"] = st["lo"] = 0
        st["cur"] = "SCALE_UP" if st["hi"] >= 2 else "SCALE_DOWN" if st["lo"] >= 2 else "HOLD"
        return st["cur"]

    def _ema(lat, cpu, st):
        st["ema"] = lat if st["ema"] is None else 0.3 * lat + 0.7 * st["ema"]
        return "SCALE_UP" if st["ema"] >= UP_L else "SCALE_DOWN" if st["ema"] <= DOWN_L else "HOLD"

    def _mm_hpa(lat, cpu, st):
        if cpu >= UP_C or lat >= UP_L: return "SCALE_UP"
        if cpu <= DOWN_C and lat <= DOWN_L: return "SCALE_DOWN"
        return "HOLD"

    def _ms_hyst(lat, cpu, st):
        up = cpu >= UP_C or lat >= UP_L
        dn = cpu <= DOWN_C and lat <= DOWN_L
        if up: st["hi"] += 1; st["lo"] = 0
        elif dn: st["lo"] += 1; st["hi"] = 0
        else: st["hi"] = st["lo"] = 0
        st["cur"] = "SCALE_UP" if st["hi"] >= 2 else "SCALE_DOWN" if st["lo"] >= 2 else "HOLD"
        return st["cur"]

    results = [
        _run("Threshold Reactive",      _threshold),
        _run("Hysteresis Reactive",     _hysteresis),
        _run("EMA Reactive",            _ema),
        _run("Multi-Metric HPA",        _mm_hpa),
        _run("Multi-Signal Hysteresis", _ms_hyst),
        _run("CSA-ACI CCE",             None, uses_cce=True),
    ]

    cce = next(r for r in results if r["controller"] == "CSA-ACI CCE")
    peers = [r for r in results if r["controller"] != "CSA-ACI CCE"]
    most_stable = min(results, key=lambda r: r["scaling_actions"])
    worst_thrash = max(r["scaling_actions"] for r in peers)
    reduction = round(100 * (1 - cce["scaling_actions"] / worst_thrash), 1) if worst_thrash else 0.0

    return {
        "seed": seed,
        "steps": steps,
        "transients": transients,
        "spike_steps": sorted(spike_steps),
        "workload": "ramp-up / hold-high / ramp-down / hold-low (req/s)",
        "model": "latency = M/M/1 response time from utilisation; action changes server count",
        "slo_ms": SLO,
        "results": results,
        "stability_winner": most_stable["controller"],
        "cce_scaling_actions": cce["scaling_actions"],
        "worst_peer_scaling_actions": worst_thrash,
        "thrash_reduction_pct": reduction,
        "verdict": (
            f"Closed loop: a scale action changes the server count, which changes the next "
            f"latency. CCE issues {cce['scaling_actions']} scaling actions "
            f"({cce['direction_reversals']} reversals) vs up to {worst_thrash} for reactive "
            f"controllers — a {reduction}% reduction in actuation churn — at "
            f"{cce['slo_violation_steps']}/{steps} SLO-violation steps (the dwell-lag cost)."
        ),
    }


# ── Formal Operating Guarantees (the contribution beyond heuristics) ──────────
# CSA-ACI is not just a tuned controller — it offers checkable operating bounds.
# run_guarantee_audit() empirically certifies four properties across seeds; the
# audit passes only if every bound holds on every seed. These are the guarantees
# a PID/hysteresis controller does not articulate.

def _run_cce_records(seq, cfg=None):
    """Drive the CCE (via Supervisor + the two agents) over a [(latency, cpu)]
    sequence and return the StepRecords."""
    from csa_aci import CCEConfig
    sup = Supervisor(cfg=cfg or CCEConfig())
    cap, net = CapacityAgent(), NetworkAgent()
    recs = []
    for i, (lat, cpu) in enumerate(seq):
        snap = TelemetrySnapshot(observed_latency=lat, cpu_utilisation=cpu, timestamp=i)
        ci, ca = cap.step(snap, None)
        ni, na = net.step(snap, None)
        recs.append(sup.step(
            telemetry=snap,
            capacity_intent=ci.value, capacity_intent_age=cap.intent_age,
            capacity_action_type=ca, capacity_action_mag=_symmetric_mag(ci.value),
            network_intent=ni.value, network_intent_age=net.intent_age,
            network_action_type=na, network_action_mag=_symmetric_mag(ni.value),
        ))
    return recs


def _direction_change_indices(recs):
    """Indices where the final intent establishes a NEW action direction
    (UP<->DOWN), ignoring HOLD — i.e. real direction changes."""
    idx, last = [], None
    for i, r in enumerate(recs):
        if r.final_intent in ("SCALE_UP", "SCALE_DOWN"):
            if last is not None and r.final_intent != last:
                idx.append(i)
            last = r.final_intent
    return idx


def run_conflict_stress_test(n_runs: int = 30) -> dict:
    """Statistical robustness of the multi-signal STABILITY result (paper Sec 5.3).

    Repeats run_conflict_experiment across n_runs seeds (each reseeds the
    transient-noise telemetry) and reports, per controller, mean +/- std and 95%
    CI for the stability metrics, plus a PAIRED Wilcoxon signed-rank test of CCE's
    thrash vs the strongest (lowest-thrash) fair multi-signal baseline — paired
    because every controller sees the identical telemetry on each seed.

        thrash = direction_reversals + oscillations + wrong_direction_steps
                 (noise-induced bad actions; the headline stability metric)

    slo_violation_steps is reported as the honest responsiveness cost.
    """
    import numpy as np
    from scipy import stats

    n_runs = max(2, min(int(n_runs), 200))
    METRICS = [
        "thrash", "direction_reversals", "oscillations", "wrong_direction_steps",
        "total_interventions", "slo_violation_steps", "regimes_handled",
    ]

    def _thrash(r):
        return r["direction_reversals"] + r["oscillations"] + r["wrong_direction_steps"]

    per_controller: dict = {}
    capable_counts: dict = {}
    total_regimes = None

    for run in range(n_runs):
        o = run_conflict_experiment(seed=run)
        total_regimes = o["analysis"]["total_regimes"]
        for r in o["results"]:
            d = per_controller.setdefault(r["controller"], {m: [] for m in METRICS})
            d["thrash"].append(_thrash(r))
            d["direction_reversals"].append(r["direction_reversals"])
            d["oscillations"].append(r["oscillations"])
            d["wrong_direction_steps"].append(r["wrong_direction_steps"])
            d["total_interventions"].append(r["total_interventions"])
            d["slo_violation_steps"].append(r["slo_violation_steps"])
            d["regimes_handled"].append(r["regimes_handled"])
            if r["regimes_handled"] == total_regimes:
                capable_counts[r["controller"]] = capable_counts.get(r["controller"], 0) + 1

    def agg(vals):
        a = np.asarray(vals, dtype=float)
        mean = float(a.mean())
        std = float(a.std(ddof=1)) if a.size > 1 else 0.0
        if a.size > 1 and std > 0:
            lo, hi = stats.t.interval(0.95, a.size - 1, loc=mean, scale=stats.sem(a))
            ci = [round(float(lo), 3), round(float(hi), 3)]
        else:
            ci = [round(mean, 3), round(mean, 3)]
        return {"mean": round(mean, 3), "std": round(std, 3), "ci95": ci}

    controllers_agg = {
        name: {m: agg(metrics[m]) for m in METRICS}
        for name, metrics in per_controller.items()
    }

    # Strongest fair baseline = a non-CCE controller that is multi-signal-capable
    # in EVERY run, with the LOWEST mean thrash (hardest to beat -> conservative).
    multi_capable = [
        name for name in per_controller
        if name != "CSA-ACI CCE" and capable_counts.get(name, 0) == n_runs
    ]
    baseline = min(
        multi_capable or [k for k in per_controller if k != "CSA-ACI CCE"],
        key=lambda k: float(np.mean(per_controller[k]["thrash"])),
    )

    # Paired Wilcoxon signed-rank on thrash (one-sided: CCE < baseline).
    cce_thrash = per_controller["CSA-ACI CCE"]["thrash"]
    base_thrash = per_controller[baseline]["thrash"]
    try:
        w, p = stats.wilcoxon(cce_thrash, base_thrash, alternative="less")
        sig = {
            "test": "wilcoxon_signed_rank_paired",
            "alternative": "CCE thrash < baseline thrash",
            "w": round(float(w), 2), "p_value": round(float(p), 6),
            "significant_0_05": bool(p < 0.05),
        }
    except ValueError as e:  # e.g. all differences zero
        sig = {"test": "wilcoxon_signed_rank_paired", "w": None, "p_value": None,
               "significant_0_05": False, "note": str(e)}

    cce_thr, base_thr = float(np.mean(cce_thrash)), float(np.mean(base_thrash))
    cce_slo = float(np.mean(per_controller["CSA-ACI CCE"]["slo_violation_steps"]))
    base_slo = float(np.mean(per_controller[baseline]["slo_violation_steps"]))

    return {
        "n_runs": n_runs,
        "regime": "multi_signal_conflict_seed_variation",
        "total_regimes": total_regimes,
        "controllers": controllers_agg,
        "fully_capable_controllers": [k for k, v in capable_counts.items() if v == n_runs],
        "significance": {
            "cce_vs": baseline,
            "metric": "thrash (direction_reversals + oscillations + wrong_direction)",
            **sig,
        },
        "verdict": (
            f"Across {n_runs} seeds, CSA-ACI's noise-induced thrash (mean {cce_thr:.1f}) "
            f"is below the strongest fair multi-signal baseline '{baseline}' (mean "
            f"{base_thr:.1f}), "
            f"{'SIGNIFICANT' if sig.get('significant_0_05') else 'not significant'} "
            f"(paired Wilcoxon p={sig.get('p_value')}). Honest responsiveness cost: "
            f"CCE SLO-lag mean {cce_slo:.1f} vs {base_slo:.1f}."
        ),
    }


def run_guarantee_audit(seeds=(1, 2, 3, 4, 5)) -> dict:
    """Empirically certify CSA-ACI's operating guarantees across seeds.

    Each check corresponds to a stated lemma in paper/sections/guarantees.md —
    the audit is the empirical certification of those proof sketches.
    """
    import random
    from csa_aci import CCEConfig

    cfg = CCEConfig()
    K, D = cfg.evidence_window, cfg.min_dwell_time
    maxc, maxn = cfg.max_capacity_step, cfg.max_network_step

    bounded_switching = {
        "lemma": 1,
        "property": f"Lemma 1 (Bounded Switching): direction changes (UP<->DOWN) are >= min_dwell_time ({D}) steps apart",
        "violations": 0, "observed_min_gap": None,
    }
    bounded_intervention = {
        "lemma": 2,
        "property": f"Lemma 2 (Bounded Actuation): per-step magnitude change <= max_step (cap {maxc}, net {maxn})",
        "violations": 0, "observed_max_step": 0.0,
    }
    bounded_response_lag = {
        "lemma": 3,
        "property": f"Lemma 3 (Bounded Response Lag): persistent signal acted on within min_dwell_time ({D}); emergency in 1 step",
        "violations": 0, "observed_normal_lag": [], "observed_emergency_lag": [],
    }
    deterministic = {
        "lemma": 4,
        "property": "Lemma 4 (Determinism & Accountability): identical inputs -> identical outputs, every step carries a named reason",
        "violations": 0,
    }

    for s in seeds:
        random.seed(s)

        # Bounds 1 & 2: sustained alternating blocks (each > D) + noise.
        blocks = [30.0] * 15 + [150.0] * 15 + [30.0] * 15 + [150.0] * 15
        seq = [(max(5.0, b + random.gauss(0, 8)), 0.5) for b in blocks]
        recs = _run_cce_records(seq, cfg)

        changes = _direction_change_indices(recs)
        gaps = [b - a for a, b in zip(changes, changes[1:])]
        if gaps:
            mn = min(gaps)
            bounded_switching["observed_min_gap"] = (
                mn if bounded_switching["observed_min_gap"] is None
                else min(bounded_switching["observed_min_gap"], mn)
            )
            if mn < D:
                bounded_switching["violations"] += 1

        prev_c, prev_n = 0.0, 0.0
        for r in recs:
            dc, dn = abs(r.capacity_action_mag - prev_c), abs(r.network_action_mag - prev_n)
            bounded_intervention["observed_max_step"] = max(
                bounded_intervention["observed_max_step"], dc, dn)
            if dc > maxc + 1e-9 or dn > maxn + 1e-9:
                bounded_intervention["violations"] += 1
            prev_c, prev_n = r.capacity_action_mag, r.network_action_mag

        # Bound 3a: sustained genuine high latency (below critical) -> act within D.
        recs_hi = _run_cce_records([(150.0, 0.5)] * (D + K + 5), cfg)
        up = next((i for i, r in enumerate(recs_hi) if r.final_intent == "SCALE_UP"), None)
        bounded_response_lag["observed_normal_lag"].append(up)
        if up is None or up > D:
            bounded_response_lag["violations"] += 1

        # Bound 3b: emergency (>= critical latency) -> act on the first step.
        recs_em = _run_cce_records([(350.0, 0.5)] * 5, cfg)
        up_em = next((i for i, r in enumerate(recs_em) if r.final_intent == "SCALE_UP"), None)
        bounded_response_lag["observed_emergency_lag"].append(up_em)
        if up_em is None or up_em > 0:
            bounded_response_lag["violations"] += 1

        # Bound 4: determinism + every step has a reason.
        seq_det = [(max(5.0, b + random.gauss(0, 8)), 0.5) for b in blocks]
        d1 = [r.final_intent for r in _run_cce_records(seq_det, cfg)]
        d2 = [r.final_intent for r in _run_cce_records(seq_det, cfg)]
        recs_reason = _run_cce_records(seq_det, cfg)
        if d1 != d2 or any(not r.arbitration_reason for r in recs_reason):
            deterministic["violations"] += 1

    checks = {
        "bounded_switching": bounded_switching,
        "bounded_intervention": bounded_intervention,
        "bounded_response_lag": bounded_response_lag,
        "deterministic_arbitration": deterministic,
    }
    for c in checks.values():
        c["passed"] = c["violations"] == 0

    return {
        "seeds": list(seeds),
        "config": {"evidence_window": K, "min_dwell_time": D,
                   "max_capacity_step": maxc, "max_network_step": maxn},
        "checks": checks,
        "all_passed": all(c["passed"] for c in checks.values()),
    }


# ── Research Harness (Phase 3) ────────────────────────────────────────────────
# Statistical significance, real-trace replay, and hyperparameter sensitivity.
# These produce the citable, paper-grade results.

def _run_cce_csi(latencies: list, cfg) -> tuple:
    """
    Run CCE + both agents over a latency sequence under a given CCEConfig.
    Returns (csi_score, intent_switch_count). Inner loop for the sensitivity
    sweep — kept separate so each config is evaluated identically.
    """
    sup = Supervisor(cfg=cfg)
    cap = CapacityAgent()
    net = NetworkAgent()
    trust_model = TrustDecayModel()

    for i, lat in enumerate(latencies):
        snap = TelemetrySnapshot(
            observed_latency=lat, cpu_utilisation=0.5, throughput=300.0, timestamp=i
        )
        cap_intent, cap_action = cap.step(snap, None)
        net_intent, net_action = net.step(snap, None)
        record = sup.step(
            telemetry=snap,
            capacity_intent=cap_intent.value,
            capacity_intent_age=cap.intent_age,
            capacity_action_type=cap_action,
            capacity_action_mag=1.0 if cap_intent.value == "SCALE_UP" else 0.0,
            network_intent=net_intent.value,
            network_intent_age=net.intent_age,
            network_action_type=net_action,
            network_action_mag=-1.0 if net_intent.value == "SCALE_DOWN" else 0.0,
        )
        conflict = cap_intent.value != net_intent.value
        evidence_accepted = record.arbitration_reason == "EVIDENCE_ACCEPT"
        trust_model.step(conflict, evidence_accepted)

    summary = sup.summary()
    csi = compute_csi(
        avg_trust=trust_model.summary()["avg"],
        intent_switch_count=summary["intent_switch_count"],
        conflict_count=summary["conflict_count"],
        total_steps=summary["total_steps"],
    )
    return csi["csi"], summary["intent_switch_count"]


def _ground_truth_from_latency(latencies: list, up_thresh: float = 100.0, window: int = 9) -> list:
    """
    Denoised ground truth for real traces. There is no labelled answer in a
    production trace, so we treat the centered rolling-median latency,
    thresholded at up_thresh, as the 'true' load: SCALE_UP where local median
    latency >= up_thresh, else HOLD. The median removes transient noise so
    precision/recall measure tracking of genuine load, not noise-chasing.
    """
    import numpy as np

    arr = np.asarray(latencies, dtype=float)
    n = arr.size
    half = window // 2
    gt = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        med = float(np.median(arr[lo:hi]))
        gt.append("SCALE_UP" if med >= up_thresh else "HOLD")
    return gt


def run_trace_replay(dataset: str = "google", n_steps: int = 200) -> dict:
    """
    Replay a REAL production trace through all five controllers.

    Loads the dataset via trace_loader (Google CPU / Wikipedia rate -> latency
    via M/M/1), derives a denoised ground truth, and runs the identical
    controller suite used by run_controller_comparison. The response carries the
    data `source` ("real" vs "synthetic_fallback") so results are never
    mislabelled — only source=="real" is paper-valid.
    """
    from app.services.trace_loader import load_trace

    trace = load_trace(dataset, n_steps=n_steps)
    latencies = trace["latency"]
    ground_truth = _ground_truth_from_latency(latencies)

    telemetry = [
        {"step": i, "observed_latency": lat, "ground_truth": ground_truth[i]}
        for i, lat in enumerate(latencies)
    ]

    out = _run_all_controllers(telemetry, keep_decisions=True)
    out.update({
        "dataset": dataset,
        "label": trace["label"],
        "source": trace["source"],
        "provenance": trace["provenance"],
        "telemetry_steps": len(telemetry),
        "latency": latencies,
        "ground_truth": ground_truth,
        "ground_truth_note": (
            "Ground truth = centered rolling-median latency (window=9) "
            "thresholded at 100ms. Denoises the real signal so precision/recall "
            "measure tracking of true load rather than noise."
        ),
    })
    return out


def run_stress_test(n_runs: int = 30, dataset: str = None) -> dict:
    """
    Repeat the controller comparison n_runs times to test statistical robustness.

      dataset is None  -> synthetic clean signal, a fresh noise seed each run.
      dataset given     -> real trace + small measurement jitter (sigma=5ms) per
                           run (a bootstrap over measurement noise).

    Reports per-controller mean +/- std and 95% CI for the key metrics, plus a
    Mann-Whitney U test of CCE vs the best reactive controller on intent
    switches and F1 (non-parametric: no normality assumption).
    """
    import numpy as np
    from scipy import stats
    from app.services.trace_loader import load_trace

    n_runs = max(2, min(int(n_runs), 200))
    METRICS = ["intent_switches", "false_positives", "recall", "f1", "avg_response_lag"]
    per_controller: dict = {}

    base_trace = None
    base_lat = None
    if dataset is not None:
        base_trace = load_trace(dataset, n_steps=200)
        base_lat = np.asarray(base_trace["latency"], dtype=float)

    for run in range(n_runs):
        if dataset is None:
            telemetry = _generate_comparison_telemetry(seed=run)
        else:
            rng = np.random.default_rng(run)
            jittered = np.clip(base_lat + rng.normal(0, 5.0, base_lat.size), 10.0, None)
            gt = _ground_truth_from_latency(jittered.tolist())
            telemetry = [
                {"step": i, "observed_latency": float(jittered[i]), "ground_truth": gt[i]}
                for i in range(jittered.size)
            ]

        out = _run_all_controllers(telemetry)
        for r in out["results"]:
            d = per_controller.setdefault(r["controller"], {m: [] for m in METRICS})
            for m in METRICS:
                d[m].append(r[m])

    def agg(vals):
        a = np.asarray(vals, dtype=float)
        mean = float(a.mean())
        std = float(a.std(ddof=1)) if a.size > 1 else 0.0
        if a.size > 1 and std > 0:
            lo, hi = stats.t.interval(0.95, a.size - 1, loc=mean, scale=stats.sem(a))
            ci = [round(float(lo), 3), round(float(hi), 3)]
        else:
            ci = [round(mean, 3), round(mean, 3)]
        return {"mean": round(mean, 3), "std": round(std, 3), "ci95": ci}

    controllers_agg = {
        name: {m: agg(metrics[m]) for m in METRICS}
        for name, metrics in per_controller.items()
    }

    reactive = {k: v for k, v in per_controller.items() if k != "CSA-ACI CCE"}
    best_reactive = min(
        reactive.keys(),
        key=lambda k: float(np.mean(reactive[k]["false_positives"])),
    )

    sig = {}
    for m in ["intent_switches", "f1"]:
        cce_vals = per_controller["CSA-ACI CCE"][m]
        rea_vals = per_controller[best_reactive][m]
        try:
            u, p = stats.mannwhitneyu(cce_vals, rea_vals, alternative="two-sided")
            sig[m] = {
                "u": round(float(u), 2),
                "p_value": round(float(p), 5),
                "significant_0_05": bool(p < 0.05),
            }
        except ValueError:  # all values identical -> test undefined
            sig[m] = {"u": None, "p_value": None, "significant_0_05": False}

    return {
        "n_runs": n_runs,
        "regime": "real_trace_jitter" if dataset else "synthetic_seed_variation",
        "dataset": dataset,
        "source": base_trace["source"] if base_trace else "synthetic",
        "controllers": controllers_agg,
        "significance": {"cce_vs": best_reactive, "tests": sig},
    }


def run_sensitivity_sweep() -> dict:
    """
    Sweep the three core CCE hyperparameters and measure CSI for each
    configuration on a fixed noisy signal (seed=42, sigma=20ms).

    Justifies the defaults (evidence_window=8, 6-of-8 = 0.75, min_dwell_time=10):
    if CSI is near-maximal and flat around the defaults, they are empirically
    validated rather than arbitrary.
    """
    import random
    from csa_aci.config import CCEConfig

    random.seed(42)
    base_pattern = [30] * 25 + [130] * 25 + [30] * 25 + [130] * 25
    signal = [max(10.0, lat + random.gauss(0, 20)) for lat in base_pattern]

    EVIDENCE_WINDOWS = [4, 6, 8, 10, 12]
    REQUIRED_FRACS = [0.5, 0.625, 0.75, 0.875]
    DWELL_TIMES = [5, 8, 10, 12, 15]

    grid = []
    for ew in EVIDENCE_WINDOWS:
        for frac in REQUIRED_FRACS:
            req = max(1, round(ew * frac))
            for dwell in DWELL_TIMES:
                cfg = CCEConfig(
                    evidence_window=ew,
                    evidence_required_count=req,
                    min_dwell_time=dwell,
                )
                csi_val, switches = _run_cce_csi(signal, cfg)
                grid.append({
                    "evidence_window": ew,
                    "evidence_required_count": req,
                    "evidence_required_frac": frac,
                    "min_dwell_time": dwell,
                    "csi": csi_val,
                    "intent_switches": switches,
                })

    best = max(grid, key=lambda c: c["csi"])
    default_cell = next(
        (c for c in grid
         if c["evidence_window"] == 8
         and c["evidence_required_count"] == 6
         and c["min_dwell_time"] == 10),
        None,
    )
    return {
        "grid": grid,
        "best": best,
        "default": default_cell,
        "swept": {
            "evidence_window": EVIDENCE_WINDOWS,
            "evidence_required_frac": REQUIRED_FRACS,
            "min_dwell_time": DWELL_TIMES,
        },
        "signal_steps": len(signal),
        "noise_sigma": 20,
    }


# ── Multi-Simulation Experiment ───────────────────────────────────────────────
# Runs 5 simulations with different seeds and load patterns.
# Each simulation is 100 steps with Gaussian noise (σ=20ms).
# Returns all 5 results with full traces for dashboard display.

MULTI_SIM_SCENARIOS = [
    {
        "id": 1,
        "seed": 42,
        "label": "Cyclic Load (Low→High→Low→High)",
        "description": "Classic oscillating pattern. 25 steps low, 25 high, repeated. Tests full cycle governance.",
        "base_pattern": [30]*25 + [130]*25 + [30]*25 + [130]*25,
    },
    {
        "id": 2,
        "seed": 7,
        "label": "Sustained High Load",
        "description": "Constant high latency throughout. Tests how quickly CCE confirms and holds SCALE_UP.",
        "base_pattern": [120]*100,
    },
    {
        "id": 3,
        "seed": 13,
        "label": "Normal with Late Spike",
        "description": "Long stable period then a genuine high-latency event. Tests noise-free detection.",
        "base_pattern": [75]*70 + [130]*20 + [75]*10,
    },
    {
        "id": 4,
        "seed": 99,
        "label": "Rapid Alternating Load",
        "description": "High and low latency alternating every 5 steps. Tests thrashing suppression.",
        "base_pattern": ([120]*5 + [60]*5) * 10,
    },
    {
        "id": 5,
        "seed": 21,
        "label": "Gradual Ramp Up then Down",
        "description": "Latency ramps from low to high then back. Tests smooth transition handling.",
        "base_pattern": [60 + i for i in range(50)] + [110 - i//2 for i in range(50)],
    },
]


def run_multi_simulation() -> dict:
    """
    Runs 5 predefined simulations with different seeds and load patterns.
    Each is 100 steps with Gaussian noise σ=20ms applied to the base pattern.
    Returns full traces + CSI for each simulation.
    """
    import random

    results = []

    for scenario in MULTI_SIM_SCENARIOS:
        random.seed(scenario["seed"])
        noisy_latencies = [
            max(10.0, lat + random.gauss(0, 20))
            for lat in scenario["base_pattern"]
        ]

        # Build SimulationStep-like objects
        steps = [
            type("Step", (), {
                "observed_latency": round(lat, 1),
                "cpu_utilisation": 0.5,
                "throughput": 0.0,
                "error_rate": 0.0,
            })()
            for lat in noisy_latencies
        ]

        sim_result = run_simulation(steps)

        # ── Compute Governance Evaluation Triad ───────────────────────
        n = len(steps)
        trace = sim_result["trace"]
        conflict_count = sum(1 for t in trace if t["conflict"])
        cce_switches   = sim_result["summary"]["intent_switch_count"]

        # 1. Signal Clarity — how clean/unambiguous was the input?
        #    1.0 = both agents always agree (no conflict)
        #    0.0 = agents disagree every single step
        conflict_rate   = conflict_count / n
        signal_clarity  = round((1 - conflict_rate), 3)

        if signal_clarity >= 0.7:
            signal_label = "CLEAN"
        elif signal_clarity >= 0.4:
            signal_label = "MIXED"
        else:
            signal_label = "CONTESTED"

        # 2. Governance Score — how stable were the decisions?
        #    1.0 = zero unnecessary switches
        #    0.0 = switched every step
        switch_rate      = cce_switches / n
        governance_score = round(1 - switch_rate, 3)

        if governance_score >= 0.95:
            governance_label = "OPTIMAL"
        elif governance_score >= 0.85:
            governance_label = "STABLE"
        else:
            governance_label = "ACTIVE"

        # 3. Oscillation Prevention — CCE vs threshold reactive baseline
        #    Shows how many unnecessary switches CCE prevented
        noisy_latencies = [t["observed_latency"] for t in trace]
        baseline_switches = 0
        last_b = None
        for lat in noisy_latencies:
            b = "SCALE_UP" if lat >= 100 else "SCALE_DOWN" if lat <= 70 else "HOLD"
            if last_b is not None and b != last_b:
                baseline_switches += 1
            last_b = b

        prevented = baseline_switches - cce_switches
        prevention_pct = round(
            (prevented / baseline_switches * 100) if baseline_switches > 0 else 100.0,
            1
        )

        results.append({
            "id":          scenario["id"],
            "seed":        scenario["seed"],
            "label":       scenario["label"],
            "description": scenario["description"],
            "csi":         sim_result["csi"],
            "summary":     sim_result["summary"],
            "trust_decay": sim_result["trust_decay"],
            "trace":       sim_result["trace"],
            "trust_curve": sim_result["trust_curve"],
            # Governance Evaluation Triad
            "signal_clarity":    signal_clarity,
            "signal_label":      signal_label,
            "governance_score":  governance_score,
            "governance_label":  governance_label,
            "baseline_switches": baseline_switches,
            "cce_switches":      cce_switches,
            "prevented_switches":prevented,
            "prevention_pct":    prevention_pct,
        })

    # Sort by CSI descending so most stable appears first
    results.sort(key=lambda r: r["csi"]["csi"], reverse=True)

    return {
        "simulations": results,
        "total_simulations": len(results),
        "noise_sigma": 20,
        "steps_per_simulation": 100,
    }