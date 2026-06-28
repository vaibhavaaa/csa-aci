"""
history.py

Rolling window of recent telemetry snapshots used by agents to
compute trends before forming an intent.

FIX:
- trend() had no KeyError guard; would raise on missing keys.
- record() accepted raw dicts with no type information.
- Added typed overloads so both TelemetrySnapshot objects AND legacy
  plain dicts are accepted (backward compatibility).
- Added average() helper needed by future supervisor metrics.
"""

from __future__ import annotations

from collections import deque
from typing import Union, List

from .telemetry import TelemetrySnapshot


class StateHistory:
    """
    Rolling window of telemetry for short-term trend analysis.

    Agents call ``record(snapshot)`` each step, then call
    ``trend("observed_latency")`` to get Δ over the window.
    """

    def __init__(self, window: int = 20) -> None:
        self.window = window
        self.states: deque[Union[TelemetrySnapshot, dict]] = deque(maxlen=window)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def record(self, telemetry: Union[TelemetrySnapshot, dict]) -> None:
        self.states.append(telemetry)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def trend(self, key: str) -> float:
        """
        Return the difference between the newest and oldest recorded
        value for *key*.  Returns 0.0 when fewer than 2 samples exist
        or the key is absent (no crash).
        """
        if len(self.states) < 2:
            return 0.0
        try:
            newest = self._get(self.states[-1], key)
            oldest = self._get(self.states[0], key)
            if newest is None or oldest is None:
                return 0.0
            return float(newest) - float(oldest)
        except (TypeError, ValueError):
            return 0.0

    def average(self, key: str) -> float:
        """Mean of *key* across the current window. Returns 0.0 if empty."""
        if not self.states:
            return 0.0
        values = [
            v for v in (self._get(s, key) for s in self.states)
            if v is not None
        ]
        return sum(values) / len(values) if values else 0.0

    def last_n(self, n: int) -> List[Union[TelemetrySnapshot, dict]]:
        return list(self.states)[-n:]

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.states)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get(snapshot: Union[TelemetrySnapshot, dict], key: str):
        if isinstance(snapshot, dict):
            return snapshot.get(key)
        # TelemetrySnapshot supports [] access
        try:
            return snapshot[key]
        except (AttributeError, KeyError):
            return None
