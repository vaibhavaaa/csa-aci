"""
cce.py

Cognitive Constraint Engine (CCE) — the core governance engine of CSA-ACI.

Arbitration design (5 steps):

STEP 1 — Conflict Arbitration
  Two agents propose intents independently. CCE resolves disagreement:
  - Agreement → use that intent directly
  - One HOLD, one non-HOLD → defer to the non-HOLD agent (one sees a signal)
  - Latency >= up_threshold AND SCALE_UP proposed → safety override, SCALE_UP wins
  - Both non-HOLD and conflicting → defer to agent with older (more stable) intent

STEP 2 — Evidence Persistence Gate + Emergency Bypass
  Proposed intent from Step 1 is checked against recent history:
  - HOLD → always passes (no check needed)
  - SCALE_UP → need evidence_required_count of last evidence_window >= up_threshold
  - SCALE_DOWN → need evidence_required_count of last evidence_window <= down_threshold
  - Window not yet full → reject
  - EMERGENCY: if observed_latency >= critical_latency_threshold → bypass gate,
    bypass dwell, force SCALE_UP immediately (system is already failing)

STEP 3 — Signal-Age Dwell (Minimum Dwell Time)
  Tracks how long the PROPOSED DIRECTION has been consistent, not how long
  the final intent has been stable. This is the key design decision:

  The dwell timer counts signal_age — incremented every step the proposed
  direction matches the pending direction. When signal_age >= min_dwell_time,
  the switch is allowed.

  WHY: The old design counted final_intent_age (how long HOLD was the final
  output). This caused additive waiting: 8 steps evidence + 4 steps dwell = 12.
  But the system has already been observing consistent signal for those 8 steps —
  that IS dwell evidence. The correct design is: if you have been seeing consistent
  signal for min_dwell_time steps, switch. Evidence and dwell are unified.

  Result: from clean state, SCALE_DOWN fires at step max(min_dwell_time,
  evidence_window) — step 10 with the defaults (min_dwell_time=10 >=
  evidence_window=8), not 12.
  Steps 1-9: signal_age building, HOLD
  Step 10: signal_age >= 10, evidence window full and passing → SCALE_DOWN

STEP 4 — Minimal Intervention Projection
  Translate intent to action magnitudes:
  - HOLD → zero all magnitudes (no action leaks through)
  - SCALE_UP → positive magnitudes only
  - SCALE_DOWN → negative magnitudes only

STEP 5 — Magnitude Clamping
  Cap per-step change to max_capacity_step and max_network_step.
  Prevents aggressive execution even when a switch is allowed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import deque

from .telemetry import is_finite_value


# -----------------------------------------------------------------
# Arbitration reason vocabulary
# -----------------------------------------------------------------

class ArbitrationReason(str, Enum):
    # ── Conflict-arbitration stage (Step 1) — surfaced via CCEOutput.conflict_reason
    AGREEMENT            = "AGREEMENT"            # both agents proposed the same intent
    CAPACITY_DEFERRED    = "CAPACITY_DEFERRED"    # conflict resolved by deferring the capacity agent
    NETWORK_DEFERRED     = "NETWORK_DEFERRED"     # conflict resolved by deferring the network agent
    SAFETY_OVERRIDE      = "SAFETY_OVERRIDE"      # multi-signal safety override → SCALE_UP wins

    # ── Evidence + dwell gate stage (Step 2) — surfaced via CCEOutput.arbitration_reason
    MIN_DWELL_BLOCK      = "MIN_DWELL_BLOCK"       # evidence ok, signal age not yet met
    EVIDENCE_REJECT      = "EVIDENCE_REJECT"       # window not full or not enough hits
    EVIDENCE_ACCEPT      = "EVIDENCE_ACCEPT"       # evidence ok + dwell met → switching
    EMERGENCY_OVERRIDE   = "EMERGENCY_OVERRIDE"    # latency/CPU >= critical threshold

    # ── Input validation stage (Step 0)
    INVALID_INPUT        = "INVALID_INPUT"         # non-finite input → hold, don't guess


# -----------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------

@dataclass
class CCEConfig:
    # temporal constraint — minimum steps signal must be consistent before switch
    min_dwell_time: int = 10

    # magnitude bounds
    max_capacity_step: float = 1.0
    max_network_step:  float = 1.0

    # evidence persistence gate
    up_latency_threshold:    float = 100.0
    down_latency_threshold:  float = 70.0    # hysteresis gap prevents flip-flopping
    evidence_window:         int   = 8       # K — size of sliding window
    evidence_required_count: int   = 6       # need >= 6 hits out of K

    # multi-signal gate (paper §System Design — Multi-Signal Arbitration).
    # The CapacityAgent watches CPU, the NetworkAgent watches latency. SCALE_UP
    # fires if EITHER signal is in danger; SCALE_DOWN requires latency idle AND
    # CPU not saturating. This is what lifts CSA-ACI above a single-signal
    # hysteresis controller — it resolves conflicts (low CPU + high latency, or
    # high CPU + low latency) that no single-metric autoscaler can.
    up_cpu_threshold:   float = 0.75
    down_cpu_threshold: float = 0.30

    # emergency bypass — skip evidence gate AND dwell entirely
    critical_latency_threshold: float = 300.0
    critical_cpu_threshold:     float = 0.95

    # rolling history size
    max_latency_buffer: int = 50


# -----------------------------------------------------------------
# Internal state
# -----------------------------------------------------------------

@dataclass
class CCEState:
    last_final_intent:    Optional[str] = None
    final_intent_age:     int   = 0
    last_capacity_mag:    float = 0.0
    last_network_mag:     float = 0.0

    # signal-age dwell tracking
    # pending_direction: the direction the system wants to move toward
    # signal_age: how many consecutive steps the signal has been pointing
    #             in that direction (counts up every step, resets on flip)
    pending_direction: Optional[str] = None
    signal_age:        int = 0

    recent_latency: deque = field(default_factory=deque)
    recent_cpu:     deque = field(default_factory=deque)

    # input-validation accounting — a monotonic counter the host process can
    # export as an alertable metric. A governor that stops governing must be
    # visible from outside; see paper §Limitations.
    invalid_input_count: int = 0
    last_invalid_fields: tuple = ()

    def init_buffers(self, cfg: CCEConfig) -> None:
        self.recent_latency = deque(maxlen=cfg.max_latency_buffer)
        self.recent_cpu     = deque(maxlen=cfg.max_latency_buffer)


# -----------------------------------------------------------------
# Output
# -----------------------------------------------------------------

@dataclass
class CCEOutput:
    final_intent:         str
    arbitration_reason:   str       # final/gate reason (evidence, dwell, emergency)
    conflict_reason:      str       # Step-1 conflict-arbitration outcome (never overwritten)
    capacity_action_type: str
    capacity_action_mag:  float
    network_action_type:  str
    network_action_mag:   float
    intent_changed:       bool
    final_intent_age:     int
    signal_age:           int       # exposed so dashboard can show progress
    intervention_distance: float
    # names of the inputs that failed the finiteness check this step; empty on
    # every normal step. Non-empty always accompanies INVALID_INPUT.
    invalid_fields:       tuple = ()


# -----------------------------------------------------------------
# Engine
# -----------------------------------------------------------------

class CognitiveConstraintEngine:
    """
    Cognitive Constraint Engine — governs intent switching above raw agents.

    The two key improvements over a simple reactive controller:
    1. Evidence gate: signal must be persistent across K readings
    2. Signal-age dwell: signal must have been consistent for min_dwell_time steps
       Both are unified — signal_age counts from the first consistent reading, so
       a switch fires at step max(min_dwell_time, evidence_window). With the
       defaults (min_dwell_time=10 >= evidence_window=8) that equals
       min_dwell_time; if a config sets min_dwell_time < evidence_window the gate
       must still wait for the window to fill. Sensitivity sweeps over these
       params should therefore expect max(min_dwell_time, evidence_window).
    """

    def __init__(self, config: CCEConfig) -> None:
        self.cfg   = config
        self.state = CCEState()
        self.state.init_buffers(self.cfg)

    def step(
        self,
        *,
        observed_latency:     float,
        capacity_intent:      str,
        capacity_intent_age:  int,
        capacity_action_type: str,
        capacity_action_mag:  float,
        network_intent:       str,
        network_intent_age:   int,
        network_action_type:  str,
        network_action_mag:   float,
        cpu_utilisation:      float = 0.0,
    ) -> CCEOutput:

        # ----------------------------------------------------------------
        # STEP 0 — Input validation (paper §4 Lemma 2, §Limitations)
        #
        # CSA-ACI is published as a drop-in governance module: magnitudes and
        # telemetry arrive from the caller, and an adopting system computing a
        # magnitude from a utilisation ratio or queue-depth quotient can hand
        # us NaN under ordinary conditions (an empty observation window).
        #
        # Untreated, that is silent: IEEE-754 comparisons against NaN are False
        # in both directions, so every threshold test fails, both agents fall
        # through to HOLD, and — worst of all — the emergency branch never
        # fires. The governor stops governing while reporting normal operation.
        #
        # Policy: unclear input → HOLD, name the reason, count it. We do NOT
        # raise: a governance layer that crashes the system it governs has
        # failed at its job, and a metrics glitch is exactly the moment the
        # governed system most needs to stay up.
        # ----------------------------------------------------------------
        invalid_fields = tuple(
            name for name, value in (
                ("observed_latency",    observed_latency),
                ("cpu_utilisation",     cpu_utilisation),
                ("capacity_action_mag", capacity_action_mag),
                ("network_action_mag",  network_action_mag),
            )
            if not is_finite_value(value)
        )

        if invalid_fields:
            self.state.invalid_input_count += 1
            self.state.last_invalid_fields = invalid_fields

            # The reading is NOT appended to the evidence buffers — a value we
            # cannot interpret must never enter the window it would corrupt.
            #
            # Dwell state is left untouched, exactly as EVIDENCE_REJECT leaves
            # it: a single glitched reading must not erase signal age the
            # system legitimately accumulated over the preceding steps.
            #
            # Magnitudes are forced to 0.0 so intervention_distance stays
            # finite and non-negative; the corrupt request is discarded whole
            # rather than differenced against.
            final_intent, intent_changed = self._resolve_final_intent("HOLD")
            return self._build_output(
                final_intent,
                ArbitrationReason.INVALID_INPUT.value,
                ArbitrationReason.INVALID_INPUT.value,
                intent_changed,
                capacity_action_type, 0.0,
                network_action_type,  0.0,
                invalid_fields=invalid_fields,
            )

        self.state.recent_latency.append(float(observed_latency))
        self.state.recent_cpu.append(float(cpu_utilisation))

        # ----------------------------------------------------------------
        # STEP 1 — Conflict Arbitration
        # ----------------------------------------------------------------
        if capacity_intent == network_intent:
            proposed_intent = capacity_intent
            arb_reason      = ArbitrationReason.AGREEMENT.value
        else:
            # Safety override (paper §System Design — Multi-Signal Arbitration):
            # if EITHER signal is in danger (latency breaching SLO OR CPU
            # saturating) and any agent proposes SCALE_UP, SCALE_UP wins. This is
            # the multi-signal generalisation of the old latency-only override —
            # it lets the CPU agent win the R4 conflict (high CPU, low latency)
            # that a latency-only controller is blind to.
            if (
                (
                    observed_latency >= self.cfg.up_latency_threshold
                    or cpu_utilisation >= self.cfg.up_cpu_threshold
                )
                and "SCALE_UP" in {capacity_intent, network_intent}
            ):
                proposed_intent = "SCALE_UP"
                arb_reason      = ArbitrationReason.SAFETY_OVERRIDE.value
            else:
                # Defer to non-HOLD agent
                if capacity_intent == "HOLD" and network_intent != "HOLD":
                    proposed_intent = network_intent
                    arb_reason      = ArbitrationReason.CAPACITY_DEFERRED.value
                elif network_intent == "HOLD" and capacity_intent != "HOLD":
                    proposed_intent = capacity_intent
                    arb_reason      = ArbitrationReason.NETWORK_DEFERRED.value
                else:
                    # Both non-HOLD and conflicting → defer to older intent
                    if capacity_intent_age >= network_intent_age:
                        proposed_intent = capacity_intent
                        arb_reason      = ArbitrationReason.NETWORK_DEFERRED.value
                    else:
                        proposed_intent = network_intent
                        arb_reason      = ArbitrationReason.CAPACITY_DEFERRED.value

        # Snapshot the Step-1 conflict-arbitration outcome before the evidence
        # gate (below) can overwrite arb_reason. Without this, conflict
        # resolution (deferral / safety override / agreement) is invisible in
        # the output — the gate reason always wins. Surfaced as conflict_reason.
        conflict_reason = arb_reason

        # ----------------------------------------------------------------
        # STEP 2 — Emergency Bypass
        # Fires BEFORE evidence gate. If latency is critical, skip everything.
        # ----------------------------------------------------------------
        emergency = (
            (
                self.cfg.critical_latency_threshold is not None
                and observed_latency >= self.cfg.critical_latency_threshold
            )
            or (
                self.cfg.critical_cpu_threshold is not None
                and cpu_utilisation >= self.cfg.critical_cpu_threshold
            )
        )

        if emergency:
            # System is failing — act immediately, no evidence or dwell needed.
            # The emergency guarantee must hold regardless of the arbitrated
            # direction: a critical latency/CPU reading always forces SCALE_UP,
            # even if both agents propose SCALE_DOWN (defense in depth).
            final_intent   = "SCALE_UP"
            arb_reason     = ArbitrationReason.EMERGENCY_OVERRIDE.value
            intent_changed = final_intent != self.state.last_final_intent
            self.state.last_final_intent = final_intent
            self.state.final_intent_age  = 0
            self.state.pending_direction = "SCALE_UP"
            self.state.signal_age        = self.cfg.min_dwell_time  # mark as satisfied

            return self._build_output(
                final_intent, arb_reason, conflict_reason, intent_changed,
                capacity_action_type, capacity_action_mag,
                network_action_type,  network_action_mag,
            )

        # ----------------------------------------------------------------
        # STEP 2 (continued) — Evidence Persistence Gate + Signal-Age Dwell
        #
        # Design: signal_age counts how many consecutive steps the proposed
        # direction has been consistent. It resets when direction flips.
        # A switch is allowed when BOTH:
        #   (a) evidence window has enough hits (quality check)
        #   (b) signal_age >= min_dwell_time (persistence check)
        #
        # This unifies evidence and dwell into one counter. The system does NOT
        # wait evidence_window steps THEN min_dwell_time more steps; it waits
        # max(min_dwell_time, evidence_window) steps total. With the defaults
        # (10 >= 8) that is min_dwell_time, during which the window also fills.
        # ----------------------------------------------------------------
        if proposed_intent in ("SCALE_UP", "SCALE_DOWN"):
            # Update signal age
            if self.state.pending_direction == proposed_intent:
                self.state.signal_age += 1
            else:
                # Direction changed — reset signal age
                self.state.pending_direction = proposed_intent
                self.state.signal_age        = 1

            evidence_ok = self._evidence_ok_for_intent(proposed_intent)
            dwell_ok    = self.state.signal_age >= self.cfg.min_dwell_time

            if not evidence_ok:
                # Window not full or not enough hits
                proposed_intent = "HOLD"
                arb_reason      = ArbitrationReason.EVIDENCE_REJECT.value
            elif not dwell_ok:
                # Evidence passes but signal hasn't been consistent long enough
                proposed_intent = "HOLD"
                arb_reason      = ArbitrationReason.MIN_DWELL_BLOCK.value
            else:
                # Both evidence and dwell satisfied — allow switch
                arb_reason = ArbitrationReason.EVIDENCE_ACCEPT.value

        else:
            # HOLD proposed — reset pending direction tracking
            if self.state.pending_direction is not None:
                self.state.pending_direction = None
                self.state.signal_age        = 0

        # ----------------------------------------------------------------
        # STEP 3 — Final intent resolution
        # ----------------------------------------------------------------
        final_intent, intent_changed = self._resolve_final_intent(proposed_intent)

        return self._build_output(
            final_intent, arb_reason, conflict_reason, intent_changed,
            capacity_action_type, capacity_action_mag,
            network_action_type,  network_action_mag,
        )

    def _resolve_final_intent(self, proposed_intent: str) -> tuple:
        """STEP 3 — commit the proposed intent and update age bookkeeping.

        Extracted so the Step-0 invalid-input path commits its HOLD through
        exactly the same bookkeeping as a normal step, rather than a parallel
        copy that could drift.
        """
        if (
            self.state.last_final_intent is None
            or proposed_intent != self.state.last_final_intent
        ):
            intent_changed = True
            self.state.final_intent_age = 0
        else:
            intent_changed = False
            self.state.final_intent_age += 1

        self.state.last_final_intent = proposed_intent
        return proposed_intent, intent_changed

    def _build_output(
        self,
        final_intent:         str,
        arb_reason:           str,
        conflict_reason:      str,
        intent_changed:       bool,
        capacity_action_type: str,
        capacity_action_mag:  float,
        network_action_type:  str,
        network_action_mag:   float,
        invalid_fields:       tuple = (),
    ) -> CCEOutput:
        # ----------------------------------------------------------------
        # STEP 4 — Minimal Intervention Projection
        # ----------------------------------------------------------------
        if final_intent == "HOLD":
            proj_cap_mag = 0.0
            proj_net_mag = 0.0
        elif final_intent == "SCALE_UP":
            proj_cap_mag = max(capacity_action_mag, 0.0)
            proj_net_mag = max(network_action_mag,  0.0)
        elif final_intent == "SCALE_DOWN":
            proj_cap_mag = min(capacity_action_mag, 0.0)
            proj_net_mag = min(network_action_mag,  0.0)
        else:
            proj_cap_mag = 0.0
            proj_net_mag = 0.0

        # ----------------------------------------------------------------
        # STEP 5 — Magnitude Clamping
        # ----------------------------------------------------------------
        final_cap_mag = self._clamp(
            self.state.last_capacity_mag, proj_cap_mag, self.cfg.max_capacity_step
        )
        final_net_mag = self._clamp(
            self.state.last_network_mag,  proj_net_mag, self.cfg.max_network_step
        )

        intervention_distance = (
            abs(final_cap_mag - capacity_action_mag)
            + abs(final_net_mag - network_action_mag)
        )

        self.state.last_capacity_mag = final_cap_mag
        self.state.last_network_mag  = final_net_mag

        return CCEOutput(
            final_intent          = final_intent,
            arbitration_reason    = arb_reason,
            conflict_reason       = conflict_reason,
            capacity_action_type  = capacity_action_type,
            capacity_action_mag   = final_cap_mag,
            network_action_type   = network_action_type,
            network_action_mag    = final_net_mag,
            intent_changed        = intent_changed,
            final_intent_age      = self.state.final_intent_age,
            signal_age            = self.state.signal_age,
            intervention_distance = intervention_distance,
            invalid_fields        = invalid_fields,
        )

    def _evidence_ok_for_intent(self, proposed_intent: str) -> bool:
        # Multi-signal evidence gate (paper §System Design — Multi-Signal
        # Arbitration). SCALE_UP needs persistent danger in EITHER signal;
        # SCALE_DOWN needs latency idle AND CPU not saturating (conservative —
        # never reclaim capacity while CPU is climbing).
        K    = self.cfg.evidence_window
        need = self.cfg.evidence_required_count

        if len(self.state.recent_latency) < K:
            return False

        lat_win = list(self.state.recent_latency)[-K:]
        cpu_win = list(self.state.recent_cpu)[-K:]

        if proposed_intent == "SCALE_UP":
            lat_hits = sum(1 for x in lat_win if x >= self.cfg.up_latency_threshold)
            cpu_hits = sum(1 for x in cpu_win if x >= self.cfg.up_cpu_threshold)
            return lat_hits >= need or cpu_hits >= need

        if proposed_intent == "SCALE_DOWN":
            lat_idle  = sum(1 for x in lat_win if x <= self.cfg.down_latency_threshold)
            cpu_safe  = sum(1 for x in cpu_win if x < self.cfg.up_cpu_threshold)
            return lat_idle >= need and cpu_safe >= need

        return True

    def _clamp(self, prev: float, proposed: float, max_step: float) -> float:
        """Bound the realized per-step magnitude delta (paper §4, Lemma 2 —
        Bounded Per-Step Actuation).

        Default-DENY: the in-range case is positively confirmed before
        `proposed` is allowed through. The previous form tested only the two
        out-of-range branches and fell through to `return proposed`, so a
        non-finite delta — for which every IEEE-754 comparison evaluates
        False in both directions — escaped unclamped, and once written into
        `last_*_mag` it made every subsequent delta non-finite too, disabling
        the bound for the rest of the process lifetime.

        Non-finite proposals now hold position at `prev`. Since `prev` starts
        at 0.0 and every return value here is finite whenever `prev` and
        `max_step` are, the engine's magnitude state is finite by induction:
        a non-finite value cannot enter it at all.
        """
        delta = proposed - prev
        if -max_step <= delta <= max_step:
            return proposed
        if math.isfinite(delta):
            return prev + math.copysign(max_step, delta)
        return prev