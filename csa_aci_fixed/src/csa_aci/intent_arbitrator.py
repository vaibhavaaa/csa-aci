"""
intent_arbitrator.py

Lightweight single-agent intent arbitrator.

FIX: ``from intent import Intent`` → ``from .intent import Intent``
The bare module import worked only when the cwd was src/csa_aci (i.e.
when running scripts directly).  It fails as soon as the package is
installed or imported normally.

NOTE: The CCE (cce.py) supersedes this class for multi-agent scenarios.
IntentArbitrator is kept as a useful standalone utility for single-agent
or unit-test contexts where only one agent's view is needed.
"""

from .intent import Intent


class IntentArbitrator:
    """
    Single-agent intent arbitrator with dwell-time enforcement.

    For multi-agent conflict resolution use CognitiveConstraintEngine.
    """

    def __init__(self, min_dwell_time: int = 50) -> None:
        self.min_dwell_time = min_dwell_time

    def decide(
        self,
        current_intent: Intent,
        intent_age: int,
        latency: float,
        latency_trend: float,
    ) -> tuple[Intent, bool]:
        """
        Decide whether intent should change.

        Returns
        -------
        (new_intent, intent_changed)
        """

        # Rule 1: Enforce minimum dwell time
        if intent_age < self.min_dwell_time:
            return current_intent, False

        # Rule 2: Strong evidence for scale up
        if latency > 100 and latency_trend > 0:
            if current_intent != Intent.SCALE_UP:
                return Intent.SCALE_UP, True

        # Rule 3: Strong evidence for scale down
        if latency < 40 and latency_trend < 0:
            if current_intent != Intent.SCALE_DOWN:
                return Intent.SCALE_DOWN, True

        # Rule 4: Default to HOLD
        if current_intent != Intent.HOLD:
            return Intent.HOLD, True

        return current_intent, False
