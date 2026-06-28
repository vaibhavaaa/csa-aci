"""
agents/base.py

Abstract base class for CSA-ACI agents.

FIX: ``from intent import Intent`` → ``from ..intent import Intent``
The bare module import worked only when the script was run with
src/csa_aci as cwd.  It fails on normal package installation.

NOTE: CapacityAgent and NetworkAgent in this codebase do NOT currently
inherit from BaseAgent — they were written independently during the
research phase.  BaseAgent is kept as the canonical contract and
CapacityAgent / NetworkAgent will be migrated to inherit from it in
a future refactor.  The assess_intent / step interface documented here
is intentionally compatible with what those agents already implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..intent import Intent
from ..telemetry import TelemetrySnapshot
from ..history import StateHistory


class BaseAgent(ABC):
    """
    Abstract base for all CSA-ACI agents.

    Subclasses must implement ``assess_intent``.
    The ``step`` method handles intent-age tracking automatically.
    """

    def __init__(self, name: str) -> None:
        self.name           = name
        self.current_intent = Intent.HOLD
        self.intent_age     = 0

    @abstractmethod
    def assess_intent(
        self,
        telemetry: TelemetrySnapshot,
        history: StateHistory,
    ) -> Intent:
        """Return the agent's recommended intent for this timestep."""

    def step(
        self,
        telemetry: TelemetrySnapshot,
        history: StateHistory,
    ) -> tuple[Intent, Intent]:
        """
        Phase-1 unified interface.

        Returns
        -------
        (intent, action_placeholder)
        In Phase-1 the action IS the intent (intent-as-action).
        """
        intent = self.assess_intent(telemetry, history)

        if intent != self.current_intent:
            self.current_intent = intent
            self.intent_age     = 0
        else:
            self.intent_age += 1

        return intent, intent
