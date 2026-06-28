// Shared color tokens + helpers. Mirrors the design system in index.css so
// data-driven elements (intent/reason badges, trust/CSI coloring) stay
// consistent across every page.

export const INTENT_COLORS = {
  SCALE_UP: "#00e5ff",
  SCALE_DOWN: "#ff9800",
  HOLD: "#5b6391",
};

export const REASON_COLORS = {
  EVIDENCE_REJECT: "#ff4444",
  MIN_DWELL_BLOCK: "#ff9800",
  EVIDENCE_ACCEPT: "#00ff99",
  CONFLICT_RESOLVED: "#ffd740",
  NO_CONFLICT: "#00e5ff",
  EMERGENCY_OVERRIDE: "#ec4899",
};

// trust / CSI banding: good ≥ 0.8, moderate ≥ 0.6, else bad
export const csiColor = (v) => (v >= 0.8 ? "#00ff99" : v >= 0.6 ? "#ffd740" : "#ff4444");

// avg-trust banding uses the 0.85 / 0.65 thresholds from the original metrics panel
export const trustColor = (v) => (v >= 0.85 ? "#00ff99" : v >= 0.65 ? "#ffd740" : "#ff4444");

export const intentColor = (intent) => INTENT_COLORS[intent] || "#5b6391";
