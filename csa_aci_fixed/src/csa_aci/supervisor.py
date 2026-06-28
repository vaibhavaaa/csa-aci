"""
supervisor.py

Governance supervisor — wraps the CCE engine and tracks higher-level
stability metrics over time.

FIX: this file was listed in the project plan and referenced by the
project vision but was completely absent from the package.

The Supervisor is the recommended entry-point for experiment loops.
It holds one CCE instance, advances it step by step, and records an
audit log that the backend / dashboard can query.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .cce import CognitiveConstraintEngine, CCEConfig, CCEOutput
from .state import SystemState
from .intent import Intent
from .telemetry import TelemetrySnapshot
from .history import StateHistory


@dataclass
class StepRecord:
    """One row in the supervisor audit log."""
    timestep:             int
    observed_latency:     float
    capacity_intent:      str
    network_intent:       str
    final_intent:         str
    arbitration_reason:   str
    intent_changed:       bool
    final_intent_age:     int
    intervention_distance: float
    capacity_action_mag:  float
    network_action_mag:   float


class Supervisor:
    """
    Wraps CognitiveConstraintEngine and tracks governance metrics.

    Usage
    -----
    >>> sup = Supervisor()
    >>> record = sup.step(telemetry, cap_intent, cap_age, cap_type, cap_mag,
    ...                   net_intent, net_age, net_type, net_mag)
    >>> print(sup.system_state.total_intent_switches)
    """

    def __init__(self, cfg: Optional[CCEConfig] = None) -> None:
        self.cfg    = cfg or CCEConfig()
        self.engine = CognitiveConstraintEngine(self.cfg)
        self.system_state = SystemState()
        self.history      = StateHistory(window=200)
        self.log: List[StepRecord] = []

    # ------------------------------------------------------------------
    # Main step
    # ------------------------------------------------------------------

    def step(
        self,
        telemetry: TelemetrySnapshot,
        capacity_intent:      str,
        capacity_intent_age:  int,
        capacity_action_type: str,
        capacity_action_mag:  float,
        network_intent:       str,
        network_intent_age:   int,
        network_action_type:  str,
        network_action_mag:   float,
    ) -> StepRecord:
        """Advance the governance engine by one timestep."""

        out: CCEOutput = self.engine.step(
            observed_latency     = telemetry.observed_latency,
            cpu_utilisation      = telemetry.cpu_utilisation,
            capacity_intent      = capacity_intent,
            capacity_intent_age  = capacity_intent_age,
            capacity_action_type = capacity_action_type,
            capacity_action_mag  = capacity_action_mag,
            network_intent       = network_intent,
            network_intent_age   = network_intent_age,
            network_action_type  = network_action_type,
            network_action_mag   = network_action_mag,
        )

        # Update shared system state
        self.system_state.record_step(
            new_intent            = Intent[out.final_intent],
            intent_changed        = out.intent_changed,
            arbitration_reason    = out.arbitration_reason,
            intervention_distance = out.intervention_distance,
            observed_latency      = telemetry.observed_latency,
        )

        # Record telemetry for trend analysis
        self.history.record(telemetry)

        # Append to audit log
        record = StepRecord(
            timestep              = self.system_state.timestep,
            observed_latency      = telemetry.observed_latency,
            capacity_intent       = capacity_intent,
            network_intent        = network_intent,
            final_intent          = out.final_intent,
            arbitration_reason    = out.arbitration_reason,
            intent_changed        = out.intent_changed,
            final_intent_age      = out.final_intent_age,
            intervention_distance = out.intervention_distance,
            capacity_action_mag   = out.capacity_action_mag,
            network_action_mag    = out.network_action_mag,
        )
        self.log.append(record)
        return record

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @property
    def intent_switch_count(self) -> int:
        return self.system_state.total_intent_switches

    @property
    def intent_switch_rate(self) -> float:
        if not self.log:
            return 0.0
        return self.intent_switch_count / len(self.log)

    @property
    def conflict_count(self) -> int:
        """Number of steps where capacity and network disagreed."""
        return sum(
            1 for r in self.log
            if r.capacity_intent != r.network_intent
        )

    def summary(self) -> dict:
        return {
            "total_steps":         len(self.log),
            "intent_switch_count": self.intent_switch_count,
            "intent_switch_rate":  round(self.intent_switch_rate, 4),
            "conflict_count":      self.conflict_count,
            "last_intent":         self.system_state.current_intent.value,
            "last_reason":         self.system_state.last_arbitration_reason,
        }