"""
agents/network_agent.py

Network / SLO agent — monitors USER-FACING latency and recommends scaling to
protect the latency SLO.

This is the second of the two agents the CCE arbitrates. It watches observed
latency (what users actually feel); the CapacityAgent watches CPU. Latency can be
high while CPU is low (a downstream dependency or network is the bottleneck), in
which case this agent calls for SCALE_UP even though a CPU-only autoscaler would
do nothing. Conversely, latency can still look fine while CPU saturates, where
this agent is content to HOLD and the CapacityAgent drives the action. The two
independent viewpoints are what let the CCE resolve conflicts a single-signal
controller cannot.
"""

from __future__ import annotations

from ..intent import Intent
from ..telemetry import is_finite_value


class NetworkAgent:
    """
    Recommends SCALE_UP when latency breaches the SLO, SCALE_DOWN when latency is
    comfortably low (capacity reclaimable), HOLD in between (hysteresis band on
    latency).

    Parameters
    ----------
    up_latency:
        Latency (ms) at/above which the SLO is considered breached.
    down_latency:
        Latency (ms) at/below which load is low enough to reclaim capacity.
    force_conflict:
        Legacy flag retained for back-compat. Raises ``down_latency`` so the
        agent reclaims more eagerly. Real conflict now arises STRUCTURALLY from
        CPU-vs-latency divergence, so this flag is no longer needed.
    """

    def __init__(
        self,
        up_latency: float = 100.0,
        down_latency: float = 40.0,
        force_conflict: bool = False,
    ) -> None:
        self.current_intent = Intent.HOLD
        self.intent_age     = 0
        self.up_latency     = up_latency
        self.down_latency   = 80.0 if force_conflict else down_latency
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
        latency = (
            telemetry["observed_latency"]
            if isinstance(telemetry, dict)
            else telemetry.observed_latency
        )

        # An agent that cannot read its signal has no opinion: abstain to HOLD
        # rather than raise. See CapacityAgent.step for the reasoning — a failed
        # scrape yields None, and comparing it raises inside the agent before
        # the CCE can name the problem.
        if not is_finite_value(latency):
            if self.current_intent != Intent.HOLD:
                self.current_intent = Intent.HOLD
                self.intent_age     = 0
            else:
                self.intent_age += 1
            return self.current_intent, "NO_OP"

        if latency >= self.up_latency:
            new_intent = Intent.SCALE_UP
            action     = "NETWORK_SCALE_UP"
        elif latency <= self.down_latency:
            new_intent = Intent.SCALE_DOWN
            action     = "NETWORK_THROTTLE"
        else:
            new_intent = Intent.HOLD
            action     = "NO_OP"

        if new_intent != self.current_intent:
            self.current_intent = new_intent
            self.intent_age     = 0
        else:
            self.intent_age += 1

        return self.current_intent, action
