// Shared color tokens + helpers. Mirrors the design system in index.css so
// data-driven elements (intent/reason badges, trust/CSI coloring) stay
// consistent across every page.

export const INTENT_COLORS = {
  SCALE_UP: "#00e5ff",
  SCALE_DOWN: "#ff9800",
  HOLD: "#5b6391",
};

// Keys mirror the backend ArbitrationReason enum (csa_aci/cce.py) exactly, so
// every reason the UI receives has a defined color instead of falling back to
// gray. Covers both fields: conflict_reason (Step-1 arbitration) and
// arbitration_reason (Step-2 gate / emergency outcome).
export const REASON_COLORS = {
  // conflict-arbitration stage (conflict_reason)
  AGREEMENT: "#00e5ff",          // agents agree — no conflict
  CAPACITY_DEFERRED: "#ffd740",  // conflict resolved by deferring the capacity agent
  NETWORK_DEFERRED: "#ffd740",   // conflict resolved by deferring the network agent
  SAFETY_OVERRIDE: "#a78bfa",    // multi-signal safety override → SCALE_UP
  // evidence + dwell gate stage (arbitration_reason)
  EVIDENCE_REJECT: "#ff4444",
  MIN_DWELL_BLOCK: "#ff9800",
  EVIDENCE_ACCEPT: "#00ff99",
  // emergency bypass
  EMERGENCY_OVERRIDE: "#ec4899",
};

// trust / CSI banding: good ≥ 0.8, moderate ≥ 0.6, else bad
export const csiColor = (v) => (v >= 0.8 ? "#00ff99" : v >= 0.6 ? "#ffd740" : "#ff4444");

// avg-trust banding uses the 0.85 / 0.65 thresholds from the original metrics panel
export const trustColor = (v) => (v >= 0.85 ? "#00ff99" : v >= 0.65 ? "#ffd740" : "#ff4444");

export const intentColor = (intent) => INTENT_COLORS[intent] || "#5b6391";
