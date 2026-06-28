// Running CSI over a slice of single-step run history.
// Ported verbatim from the original Dashboard so the number is identical:
//   CSI = avgTrust*0.4 + (1 - switchRate)*0.4 + (1 - conflictRate)*0.2
export function computeRunningCSI(history) {
  if (history.length === 0) return null;
  const avgTrust =
    history.reduce((s, r) => s + (r.trust_score || 0), 0) / history.length;
  const switches = history.filter(
    (r, i) => i > 0 && r.final_intent !== history[i - 1].final_intent,
  ).length;
  const switchRate = switches / history.length;
  const conflicts = history.filter((r) => r.conflict).length;
  const conflictRate = conflicts / history.length;
  const val = avgTrust * 0.4 + (1 - switchRate) * 0.4 + (1 - conflictRate) * 0.2;
  const rounded = Math.round(val * 1000) / 1000;
  return {
    csi: rounded,
    label: rounded >= 0.8 ? "STABLE" : rounded >= 0.6 ? "MODERATE" : "DEGRADED",
  };
}
