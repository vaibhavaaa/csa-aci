"""
Cognitive Stability Index (CSI)

A single number from 0.0 to 1.0 that summarises how stable
the governed system has been over a simulation run.

Formula:
    CSI = (avg_trust × 0.4)
        + ((1 - switch_rate) × 0.4)
        + ((1 - conflict_rate) × 0.2)

Above 0.8  → STABLE
0.6 – 0.8  → MODERATE
Below 0.6  → DEGRADED
"""


def compute_csi(
    avg_trust: float,
    intent_switch_count: int,
    conflict_count: int,
    total_steps: int,
) -> dict:
    """
    Compute the Cognitive Stability Index from simulation metrics.

    Returns CSI score, label, and component breakdown.
    """
    if total_steps == 0:
        return {
            "csi": 0.0,
            "label": "NO DATA",
            "components": {},
        }

    switch_rate = intent_switch_count / total_steps
    conflict_rate = conflict_count / total_steps

    # clamp all inputs to [0, 1]
    avg_trust = max(0.0, min(1.0, avg_trust))
    switch_rate = max(0.0, min(1.0, switch_rate))
    conflict_rate = max(0.0, min(1.0, conflict_rate))

    csi = (
        (avg_trust * 0.4)
        + ((1.0 - switch_rate) * 0.4)
        + ((1.0 - conflict_rate) * 0.2)
    )
    csi = round(csi, 4)

    if csi >= 0.8:
        label = "STABLE"
    elif csi >= 0.6:
        label = "MODERATE"
    else:
        label = "DEGRADED"

    return {
        "csi": csi,
        "label": label,
        "components": {
            "avg_trust_contribution": round(avg_trust * 0.4, 4),
            "switch_stability_contribution": round((1.0 - switch_rate) * 0.4, 4),
            "conflict_stability_contribution": round((1.0 - conflict_rate) * 0.2, 4),
            "switch_rate": round(switch_rate, 4),
            "conflict_rate": round(conflict_rate, 4),
        },
    }


def csi_label(score: float) -> str:
    if score >= 0.8:
        return "STABLE"
    elif score >= 0.6:
        return "MODERATE"
    return "DEGRADED"