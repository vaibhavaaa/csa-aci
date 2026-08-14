"""
api.py

Public façade for CSA-ACI.

``CSAACI`` is the recommended drop-in governance module for callers
that don't want to manage the CCE, Supervisor, or telemetry types
directly.  Zero file I/O.  Pure in-memory decision step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .cce import CognitiveConstraintEngine, CCEConfig, CCEOutput


@dataclass
class AgentIO:
    intent:      str
    intent_age:  int
    action_type: str
    action_mag:  float


@dataclass
class GovernanceDecision:
    final_intent:          str
    arbitration_reason:    str
    conflict_reason:       str

    capacity_action_type:  str
    capacity_action_mag:   float
    network_action_type:   str
    network_action_mag:    float

    intent_changed:        bool
    final_intent_age:      int
    intervention_distance: float

    # Non-empty when an input failed the finiteness check: the step was held at
    # HOLD and `arbitration_reason` is INVALID_INPUT. Adopting systems that
    # derive magnitudes from a ratio (utilisation, queue depth) should alert on
    # this — it means CSA-ACI declined to govern rather than guessed.
    invalid_fields:        tuple = ()


class CSAACI:
    """
    CSA-ACI as a drop-in governance module.
    Zero file I/O.  Pure in-memory decision step.
    """

    def __init__(self, cfg: Optional[CCEConfig] = None) -> None:
        self.cfg    = cfg or CCEConfig()
        self.engine = CognitiveConstraintEngine(self.cfg)

    def step(
        self,
        *,
        observed_latency: float,
        capacity: AgentIO,
        network:  AgentIO,
    ) -> GovernanceDecision:
        out: CCEOutput = self.engine.step(
            observed_latency     = observed_latency,
            capacity_intent      = capacity.intent,
            capacity_intent_age  = capacity.intent_age,
            capacity_action_type = capacity.action_type,
            capacity_action_mag  = capacity.action_mag,
            network_intent       = network.intent,
            network_intent_age   = network.intent_age,
            network_action_type  = network.action_type,
            network_action_mag   = network.action_mag,
        )

        return GovernanceDecision(
            final_intent          = out.final_intent,
            arbitration_reason    = out.arbitration_reason,
            conflict_reason       = out.conflict_reason,
            capacity_action_type  = out.capacity_action_type,
            capacity_action_mag   = out.capacity_action_mag,
            network_action_type   = out.network_action_type,
            network_action_mag    = out.network_action_mag,
            intent_changed        = out.intent_changed,
            final_intent_age      = out.final_intent_age,
            intervention_distance = out.intervention_distance,
            invalid_fields        = out.invalid_fields,
        )
