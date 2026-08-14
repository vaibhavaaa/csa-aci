"""
telemetry.py

Telemetry snapshot passed to agents at each timestep.

FIX: this file was referenced in docs and the project vision but
was completely missing from the package.  Agents received raw dicts
instead (e.g. telemetry["observed_latency"]), which is fragile and
un-typed.

TelemetrySnapshot is a typed dataclass that agents should accept.
A dict-compatibility helper (from_dict) is provided for backward
compatibility with existing simulation code.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Any


def is_finite_value(value) -> bool:
    """True only for values that are real, numeric and finite.

    Deliberately broad: NaN, ±inf, None and non-numeric types all return False.
    Lives here because both layers need it and telemetry.py is a leaf module:
    the CCE uses it to decide whether it can govern a reading at all, and the
    agents use it to decide whether they can form an opinion about one.

    None matters as much as NaN in practice — a metrics scrape that fails
    returns no value, not a NaN, and an unguarded comparison against None
    raises TypeError rather than quietly evaluating False.
    """
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


@dataclass
class TelemetrySnapshot:
    observed_latency: float        # ms
    cpu_utilisation: float = 0.0   # 0.0–1.0
    throughput: float = 0.0        # requests/s
    queue_depth: int = 0           # pending request backlog
    timestamp: int = 0             # simulation step / wall-clock epoch

    # Catch-all for extra fields from experiment harnesses.
    extras: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Dict interop (agents currently use telemetry["observed_latency"])
    # ------------------------------------------------------------------

    def __getitem__(self, key: str) -> Any:
        """Allow agents to use telemetry[key] without code changes."""
        if hasattr(self, key):
            return getattr(self, key)
        return self.extras[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except (AttributeError, KeyError):
            return default

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TelemetrySnapshot":
        known = {
            "observed_latency", "cpu_utilisation",
            "throughput", "queue_depth", "timestamp",
        }
        kwargs = {k: v for k, v in d.items() if k in known}
        extras = {k: v for k, v in d.items() if k not in known}
        return cls(**kwargs, extras=extras)
