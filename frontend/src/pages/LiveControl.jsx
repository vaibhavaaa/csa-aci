import { ArrowRight, Play } from "lucide-react";
import { useDashboard } from "@/context/DashboardContext";
import { Card, PanelLabel } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import { DecisionBadge, TrustBadge, EmptyState } from "@/components/shared";
import { REASON_COLORS } from "@/lib/constants";

const GUIDE = [
  {
    label: "High Latency Spike (single)",
    inputs: "latency=150, cpu=0.9, error_rate=0.3",
    cap: "SCALE_UP", net: "HOLD", arb: "NETWORK_DEFERRED → SCALE_UP",
    gate: "EVIDENCE_REJECT (1/8 hit)", final: "HOLD",
    note: "One spike is noise. CCE suppresses it. Core novelty.", color: "#ff6b6b",
  },
  {
    label: "Sustained High Latency (8+ runs)",
    inputs: "latency=110, cpu=0.75, error_rate=0.05",
    cap: "SCALE_UP", net: "HOLD", arb: "NETWORK_DEFERRED → SCALE_UP",
    gate: "EVIDENCE_ACCEPT after 8 runs", final: "SCALE_UP",
    note: "Run 8+ times. Watch the evidence window fill. Gate opens. Intent switches.", color: "#00ff99",
  },
  {
    label: "Normal Operation",
    inputs: "latency=75, cpu=0.5, error_rate=0.0",
    cap: "HOLD", net: "HOLD", arb: "AGREEMENT → HOLD",
    gate: "Skipped (HOLD always passes)", final: "HOLD",
    note: "Both agents agree. No conflict. No evidence check needed.", color: "#00e5ff",
  },
  {
    label: "Low Latency — Scale Down",
    inputs: "latency=30, cpu=0.2, error_rate=0.0",
    cap: "HOLD", net: "SCALE_DOWN", arb: "CAPACITY_DEFERRED → SCALE_DOWN",
    gate: "EVIDENCE_REJECT until 8 low readings", final: "SCALE_DOWN",
    note: "NetworkAgent wants to throttle. CCE requires 8 consistent low readings.", color: "#ffd740",
  },
  {
    label: "Noisy / Alternating",
    inputs: "Alternate: latency=120 then latency=80",
    cap: "Alternates", net: "HOLD", arb: "Varies each step",
    gate: "EVIDENCE_REJECT — window never hits 6/8", final: "HOLD",
    note: "Oscillating signal. CCE detects inconsistency, stays HOLD. Prevents thrashing.", color: "#ff9800",
  },
  {
    label: "Emergency (≥300ms)",
    inputs: "latency=350, cpu=1.0, error_rate=0.8",
    cap: "SCALE_UP", net: "HOLD", arb: "EMERGENCY_OVERRIDE",
    gate: "BYPASSED — evidence gate skipped entirely", final: "SCALE_UP",
    note: "System already failing. At ≥300ms the CCE bypasses the gate and acts in 1 step. Speed beats stability.", color: "#ec4899",
  },
];

function Row({ k, v }) {
  return (
    <div className="flex items-start gap-2">
      <dt className="w-20 shrink-0 text-faint/60">{k}</dt>
      <dd className="font-mono text-ink/90">{v}</dd>
    </div>
  );
}

function BehaviourGuide() {
  return (
    <Card>
      <PanelLabel className="mb-4">How to Use — Expected CCE Behaviour Per Input</PanelLabel>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {GUIDE.map((g) => (
          <div
            key={g.label}
            className="flex flex-col gap-2.5 rounded-xl border border-l-2 border-white/8 bg-white/[0.025] p-4"
            style={{ borderLeftColor: g.color }}
          >
            <div className="text-[11px] font-semibold" style={{ color: g.color }}>{g.label}</div>
            <p className="font-mono text-[10px] text-faint">{g.inputs}</p>
            <dl className="flex flex-col gap-1 text-[10px]">
              <Row k="Cap Agent" v={g.cap} />
              <Row k="Net Agent" v={g.net} />
              <Row k="Arbitration" v={g.arb} />
              <Row k="Evidence Gate" v={g.gate} />
              <div className="flex items-center gap-2 pt-0.5">
                <dt className="w-20 text-faint/60">Final</dt>
                <DecisionBadge value={g.final} />
              </div>
            </dl>
            <p className="border-t border-white/8 pt-2 text-[10px] italic leading-relaxed text-faint">{g.note}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function EvidenceMeter({ windowSize, history }) {
  const isEmergency = history.length > 0 && history[history.length - 1]?.reason === "EMERGENCY_OVERRIDE";
  const pct = isEmergency ? 100 : Math.min((windowSize / 8) * 100, 100);
  const barColor = isEmergency ? "#ec4899" : windowSize >= 8 ? "#ffd740" : windowSize >= 6 ? "#ff9800" : "#00e5ff";
  return (
    <div className="mt-4 flex items-center gap-3">
      <div className="min-w-[210px] text-[10px] uppercase tracking-wider text-faint">
        {isEmergency ? (
          <span className="font-bold" style={{ color: "#ec4899" }}>⚡ Emergency override — evidence gate bypassed</span>
        ) : (
          <>
            Evidence window: {windowSize}/8
            {windowSize < 8
              ? <span className="ml-1.5" style={{ color: "#ff6b6b" }}>need {8 - windowSize} more to allow switch</span>
              : <span className="ml-1.5" style={{ color: "#ffd740" }}>gate open — switch now possible</span>}
          </>
        )}
      </div>
      <div className="h-1.5 w-full max-w-[200px] overflow-hidden rounded-full bg-black/40">
        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${pct}%`, background: barColor }} />
      </div>
    </div>
  );
}

const FORM_FIELDS = [
  { key: "task_name", label: "Task Name", type: "text", w: "w-44" },
  { key: "observed_latency", label: "Latency (ms)", type: "number", w: "w-28" },
  { key: "cpu_utilisation", label: "CPU (0–1)", type: "number", w: "w-28" },
  { key: "error_rate", label: "Error Rate (0–1)", type: "number", w: "w-28" },
];

function SingleRunForm() {
  const {
    singleRunInput, setSingleRunInput, runSingleStep, singleRunning, singleRunError,
    resetSupervisor, resetting, windowSize, singleRunHistory,
  } = useDashboard();
  return (
    <Card>
      <PanelLabel className="mb-4">Single-Step CCE Run — Fire a Live Operational Decision</PanelLabel>
      <div className="flex flex-wrap items-end gap-3">
        {FORM_FIELDS.map(({ key, label, type, w }) => (
          <Field key={key} label={label}>
            <Input type={type} value={singleRunInput[key]}
              onChange={(e) => setSingleRunInput((p) => ({ ...p, [key]: e.target.value }))} className={w} />
          </Field>
        ))}
        <Button variant="cyan" onClick={runSingleStep} disabled={singleRunning}>
          {singleRunning ? "Running…" : "▶ Run"}
        </Button>
        <Button variant="danger" size="sm" onClick={resetSupervisor} disabled={resetting}>
          {resetting ? "Resetting…" : "↺ Reset"}
        </Button>
        {singleRunError && <div className="text-xs text-bad">✗ {singleRunError}</div>}
      </div>
      <EvidenceMeter windowSize={windowSize} history={singleRunHistory} />
    </Card>
  );
}

function LiveFeed({ liveEvents }) {
  return (
    <Card>
      <PanelLabel className="mb-4">Live Decisions Feed (WebSocket)</PanelLabel>
      {liveEvents.length === 0 ? (
        <EmptyState icon={Play} title="No live events yet">
          Fire a run above to see decisions stream in here.
        </EmptyState>
      ) : (
        <ul className="flex flex-col gap-2">
          {liveEvents.map((e, i) => (
            <li key={i}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-white/8 bg-white/[0.025] px-3.5 py-2.5 transition-colors hover:border-cyan/30">
              <span className="font-mono text-xs text-ink">{e.task}</span>
              {e.result?.observed_latency != null && (
                <span className="font-mono text-[11px] text-muted">lat={e.result.observed_latency}ms</span>
              )}
              <ArrowRight size={12} className="shrink-0 text-faint/40" />
              <DecisionBadge value={e.result?.final_intent} />
              <span className="ml-auto flex items-center gap-1.5">
                <span className="text-[10px] uppercase tracking-wider text-faint">trust</span>
                <TrustBadge trust={e.result?.trust_score ?? 0} />
                {e.result?.reason && (
                  <span className="ml-2 font-mono text-[10px] uppercase tracking-wider"
                    style={{ color: REASON_COLORS[e.result.reason] || "#5b6391" }}>
                    {e.result.reason}
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function LiveControl() {
  const { liveEvents } = useDashboard();
  return (
    <div className="flex flex-col gap-stack">
      <SingleRunForm />
      <BehaviourGuide />
      <LiveFeed liveEvents={liveEvents} />
    </div>
  );
}
