"""
state.py

Runtime system state — the live picture of the controlled environment
at a single timestep.

FIX: this file was completely empty (0 bytes) in the original package.
It is referenced by the project plan as the shared runtime snapshot.

SystemState captures what the CCE and supervisor need beyond raw
telemetry: current confirmed intent, trust score, active conflicts, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from .intent import Intent


@dataclass
class SystemState:
    """
    A snapshot of the governance layer's runtime state at one timestep.

    Passed from the orchestrator into supervisors / dashboards so they
    can log and visualise what the CCE decided without reaching into
    internal CCE state directly.
    """

    # Current authoritative intent
    current_intent: Intent = Intent.HOLD

    # How many consecutive timesteps this intent has been held
    intent_age: int = 0

    # Was the intent different from the previous timestep?
    intent_changed: bool = False

    # The reason string returned by the last CCE arbitration step
    last_arbitration_reason: str = ""

    # How far the CCE had to clamp agent magnitudes (stability signal)
    last_intervention_distance: float = 0.0

    # Simulation step counter
    timestep: int = 0

    # Most recent latency observed (mirrors telemetry for quick access)
    observed_latency: float = 0.0

    # Running count of intent switches (for stability metrics)
    total_intent_switches: int = 0

    # Reasons that caused the last N decisions (short audit trail)
    recent_reasons: List[str] = field(default_factory=list)

    def record_step(
        self,
        new_intent: Intent,
        intent_changed: bool,
        arbitration_reason: str,
        intervention_distance: float,
        observed_latency: float,
    ) -> None:
        """Update state in-place after a CCE step."""
        if intent_changed:
            self.total_intent_switches += 1
        self.current_intent = new_intent
        self.intent_changed = intent_changed
        self.intent_age = 0 if intent_changed else self.intent_age + 1
        self.last_arbitration_reason = arbitration_reason
        self.last_intervention_distance = intervention_distance
        self.observed_latency = observed_latency
        self.timestep += 1

        # keep a short audit trail (last 20 reasons)
        self.recent_reasons.append(arbitration_reason)
        if len(self.recent_reasons) > 20:
            self.recent_reasons.pop(0)
