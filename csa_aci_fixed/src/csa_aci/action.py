"""
action.py

Represents a concrete action recommended by an agent.

FIX: original Action dataclass had no connection to the action_type
strings actually produced by CapacityAgent / NetworkAgent
("CAPACITY_SCALE", "NETWORK_THROTTLE", "NO_OP").  The known action
type constants are now defined here, and a factory helper is provided.
"""

from dataclasses import dataclass

# -----------------------------------------------------------------
# Known action-type string constants
# Keep these in sync with what agents emit.
# -----------------------------------------------------------------
ACTION_CAPACITY_SCALE = "CAPACITY_SCALE"
ACTION_NETWORK_THROTTLE = "NETWORK_THROTTLE"
ACTION_NO_OP = "NO_OP"


@dataclass
class Action:
    source: str       # agent name, e.g. "capacity" or "network"
    action_type: str  # one of the ACTION_* constants above
    magnitude: float  # signed magnitude; 0.0 for NO_OP
    target: str       # resource label, e.g. "gpu_cluster_0"

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def no_op(cls, source: str, target: str = "default") -> "Action":
        return cls(source=source, action_type=ACTION_NO_OP,
                   magnitude=0.0, target=target)

    @classmethod
    def capacity_scale(cls, source: str, magnitude: float,
                       target: str = "default") -> "Action":
        return cls(source=source, action_type=ACTION_CAPACITY_SCALE,
                   magnitude=magnitude, target=target)

    @classmethod
    def network_throttle(cls, source: str, magnitude: float,
                         target: str = "default") -> "Action":
        return cls(source=source, action_type=ACTION_NETWORK_THROTTLE,
                   magnitude=magnitude, target=target)
