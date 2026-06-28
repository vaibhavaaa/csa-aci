from enum import Enum
from dataclasses import dataclass


class Intent(Enum):
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    HOLD = "HOLD"


@dataclass
class IntentState:
    current_intent: Intent = Intent.HOLD
    intent_age: int = 0  # timesteps since last intent change
