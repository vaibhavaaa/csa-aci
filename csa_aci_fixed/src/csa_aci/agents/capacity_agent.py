"""
agents/capacity_agent.py

Capacity agent — monitors COMPUTE saturation (CPU utilisation) and recommends
scaling of compute capacity.

This is one of the two agents whose DISAGREEMENT the CCE arbitrates. The
CapacityAgent watches CPU; the NetworkAgent watches user-facing latency. Because
they read DIFFERENT signals they can genuinely conflict — e.g. low CPU but high
latency in a dependency/network-bound workload, or high CPU but still-low latency
just before saturation. Resolving that conflict is the capability a single-metric
autoscaler (Kubernetes HPA, which sees only CPU) cannot provide. With a single
signal the whole system would reduce to hysteresis; the second, independent agent
is what makes CSA-ACI a multi-signal governance layer rather than a smoother.
"""

from __future__ import annotations

from ..intent import Intent


class CapacityAgent:
    """
    Recommends SCALE_UP when CPU is saturating, SCALE_DOWN when CPU is idle,
    HOLD in between (a hysteresis band on CPU).

    Parameters
    ----------
    up_cpu:
        Utilisation (0–1) at/above which compute is considered saturating.
    down_cpu:
        Utilisation at/below which compute is considered idle (reclaimable).
    force_conflict:
        Legacy flag retained for back-compat. Lowers ``up_cpu`` so the agent
        trips earlier. Real conflict now arises STRUCTURALLY from CPU-vs-latency
        divergence, so this flag is no longer needed to induce disagreement.
    """

    def __init__(
        self,
        up_cpu: float = 0.75,
        down_cpu: float = 0.30,
        force_conflict: bool = False,
    ) -> None:
        self.current_intent = Intent.HOLD
        self.intent_age     = 0
        self.up_cpu         = 0.60 if force_conflict else up_cpu
        self.down_cpu       = down_cpu
        self.force_conflict = force_conflict

    def step(self, telemetry, history) -> tuple[Intent, str]:
        """
        Parameters
        ----------
        telemetry : TelemetrySnapshot or dict
        history   : StateHistory (unused by this agent currently)

        Returns
        -------
        (intent, action_type_string)
        """
        cpu = (
            telemetry["cpu_utilisation"]
            if isinstance(telemetry, dict)
            else telemetry.cpu_utilisation
        )

        if cpu >= self.up_cpu:
            new_intent = Intent.SCALE_UP
            action     = "CAPACITY_SCALE_UP"
        elif cpu <= self.down_cpu:
            new_intent = Intent.SCALE_DOWN
            action     = "CAPACITY_SCALE_DOWN"
        else:
            new_intent = Intent.HOLD
            action     = "NO_OP"

        if new_intent != self.current_intent:
            self.current_intent = new_intent
            self.intent_age     = 0
        else:
            self.intent_age += 1

        return self.current_intent, action
