"""
config.py

Single source of truth for all CSA-ACI configuration.

FIX: original file contained only two orphaned simulation constants
(MAX_TIMESTEPS, RANDOM_SEED) with no relation to the CCEConfig used
by the engine.  All settings now live here.
"""

from .cce import CCEConfig

# -----------------------------------------------------------------
# Simulation / experiment constants
# -----------------------------------------------------------------
MAX_TIMESTEPS: int = 1000
RANDOM_SEED: int = 42

# -----------------------------------------------------------------
# Default CCE configuration (used when callers don't pass their own)
# -----------------------------------------------------------------
DEFAULT_CCE_CONFIG = CCEConfig(
    min_dwell_time=10,
    max_capacity_step=1.0,
    max_network_step=1.0,
    up_latency_threshold=100.0,
    down_latency_threshold=70.0,
    evidence_window=8,
    evidence_required_count=6,
    max_latency_buffer=50,
)
