"""
csa_aci — Cognitive Stability-Aware Autonomous Cloud Infrastructure

Public API
----------
from csa_aci import CSAACI, CCEConfig, AgentIO, GovernanceDecision
from csa_aci import Supervisor, TelemetrySnapshot, SystemState
from csa_aci import Intent, StateHistory
"""

from .api import CSAACI, AgentIO, GovernanceDecision
from .cce import CCEConfig, CCEOutput, ArbitrationReason
from .config import DEFAULT_CCE_CONFIG, MAX_TIMESTEPS, RANDOM_SEED
from .history import StateHistory
from .intent import Intent, IntentState
from .state import SystemState
from .supervisor import Supervisor, StepRecord
from .telemetry import TelemetrySnapshot
from .action import Action, ACTION_CAPACITY_SCALE, ACTION_NETWORK_THROTTLE, ACTION_NO_OP
from .csi import compute_csi
from .trust import TrustDecayModel

__all__ = [
    # Primary entry-point
    "CSAACI",
    "AgentIO",
    "GovernanceDecision",
    # Engine internals (for advanced use)
    "CCEConfig",
    "CCEOutput",
    "ArbitrationReason",
    # Config
    "DEFAULT_CCE_CONFIG",
    "MAX_TIMESTEPS",
    "RANDOM_SEED",
    # Domain types
    "Intent",
    "IntentState",
    "SystemState",
    "TelemetrySnapshot",
    "StateHistory",
    "Action",
    "ACTION_CAPACITY_SCALE",
    "ACTION_NETWORK_THROTTLE",
    "ACTION_NO_OP",
    # Supervisor / audit
    "Supervisor",
    "StepRecord",
]

__version__ = "0.1.0"
