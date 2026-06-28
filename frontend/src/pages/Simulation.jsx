import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area, Legend, CartesianGrid,
} from "recharts";
import { FlaskConical } from "lucide-react";
import { useDashboard } from "@/context/DashboardContext";
import { Card, PanelLabel } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { KpiTile, IntentBadge, IntentTimeline, EmptyState } from "@/components/shared";
import { INTENT_COLORS, REASON_COLORS, intentColor, csiColor } from "@/lib/constants";

const TT = {
  contentStyle: { background: "#0c1226", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, fontSize: 11 },
  labelStyle: { color: "#8b95c9" },
};

function Controls() {
  const { runSimulation, simRunning, simError } = useDashboard();
  return (
    <Card className="flex flex-wrap items-center gap-4">
      <Button variant="good" size="lg" onClick={runSimulation} disabled={simRunning}>
        {simRunning ? "Simulating…" : "▶ Run Simulation"}
      </Button>
      <span className="text-xs text-muted">
        30-step scenario · low → high → low → high latency regimes · streams trust / CSI convergence
      </span>
      {simError && <span className="text-xs text-bad">✗ {simError}</span>}
    </Card>
  );
}

function Summary({ s }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <KpiTile label="Total Steps"     value={s.total_steps} tone="cyan" />
      <KpiTile label="Intent Switches" value={s.intent_switch_count} tone="warn" />
      <KpiTile label="Switch Rate"     value={`${(s.intent_switch_rate * 100).toFixed(1)}%`} tone="orange" />
      <KpiTile label="Conflicts"       value={s.conflict_count} tone="bad" />
      <KpiTile label="Final Intent"    value={s.last_intent} color={intentColor(s.last_intent)} />
      <KpiTile label="Last Reason"     value={s.last_reason?.replace("_", " ")} color={REASON_COLORS[s.last_reason] || "#8b95c9"} />
    </div>
  );
}

function CsiPanel({ csi }) {
  const c = csi.components;
  const rows = [
    { label: "Trust Contribution (40%)",  value: c.avg_trust_contribution,          max: 0.4 },
    { label: "Switch Stability (40%)",    value: c.switch_stability_contribution,   max: 0.4 },
    { label: "Conflict Stability (20%)",  value: c.conflict_stability_contribution, max: 0.2 },
  ];
  return (
    <Card>
      <PanelLabel className="mb-4">Cognitive Stability Index</PanelLabel>
      <div className="flex flex-wrap items-center gap-stack-lg">
        <div className="flex flex-col items-center rounded-xl border border-white/8 bg-white/[0.025] px-6 py-4">
          <div className="font-mono text-6xl font-extrabold leading-none tabular-nums" style={{ color: csiColor(csi.csi) }}>
            {csi.csi}
          </div>
          <div className="mt-2 text-xs tracking-[2px]" style={{ color: csiColor(csi.csi) }}>{csi.label}</div>
        </div>
        <div className="min-w-[280px] flex-1">
          <div className="mb-3 text-[11px] uppercase tracking-wider text-faint">Component Breakdown</div>
          {rows.map(({ label, value, max }) => {
            const ratio = value / max;
            const col = ratio >= 0.8 ? "#00ff99" : ratio >= 0.6 ? "#ffd740" : "#ff4444";
            return (
              <div key={label} className="mb-2.5">
                <div className="mb-1 flex justify-between text-[11px] text-muted">
                  <span>{label}</span>
                  <span className="font-mono tabular-nums text-ink">{value} / {max}</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full transition-all duration-500" style={{ width: `${ratio * 100}%`, background: col }} />
                </div>
              </div>
            );
          })}
          <div className="mt-3 flex gap-4 text-[11px] text-faint">
            <span>Switch Rate: <span className="font-mono text-warn">{c.switch_rate}</span></span>
            <span>Conflict Rate: <span className="font-mono text-bad">{c.conflict_rate}</span></span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function Charts({ data }) {
  return (
    <div className="grid grid-cols-1 gap-stack lg:grid-cols-2">
      <Card>
        <PanelLabel className="mb-4">Observed Latency (ms)</PanelLabel>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data}>
            <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="step" tickLine={false} axisLine={false} tick={{ fill: "#5b6391", fontSize: 10 }} />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: "#5b6391", fontSize: 10 }} width={32} />
            <Tooltip {...TT} itemStyle={{ color: "#00e5ff" }} />
            <Line type="monotone" dataKey="latency" stroke="#00e5ff" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </Card>
      <Card>
        <PanelLabel className="mb-4">Trust Score Over Time</PanelLabel>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={data}>
            <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="step" tickLine={false} axisLine={false} tick={{ fill: "#5b6391", fontSize: 10 }} />
            <YAxis domain={[0, 1]} tickLine={false} axisLine={false} tick={{ fill: "#5b6391", fontSize: 10 }} width={32} />
            <Tooltip {...TT} />
            <Legend wrapperStyle={{ fontSize: 11, color: "#5b6391" }} />
            <Area type="monotone" dataKey="trust" name="Per-step Trust" stroke="#00ff99" fill="#00ff9911" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Area type="monotone" dataKey="decayed_trust" name="Decayed Trust" stroke="#ffd740" fill="#ffd74011" strokeWidth={2} dot={false} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </Card>
    </div>
  );
}

function Timeline({ trace }) {
  return (
    <Card>
      <PanelLabel className="mb-3">Intent Timeline — bright border = intent changed</PanelLabel>
      <div className="mb-1 flex flex-wrap gap-4 text-xs text-faint">
        {Object.entries(INTENT_COLORS).map(([k, v]) => (
          <span key={k} className="flex items-center gap-2">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ background: v }} />{k}
          </span>
        ))}
      </div>
      <IntentTimeline trace={trace} />
    </Card>
  );
}

function TraceTable({ trace }) {
  const cols = ["Step", "Latency", "Capacity", "Network", "Final Intent", "Reason", "Trust", "Age"];
  return (
    <Card>
      <PanelLabel className="mb-3">Decision Trace</PanelLabel>
      <div className="overflow-x-auto">
        <div className="inline-block min-w-full overflow-hidden rounded-lg border border-white/10">
          <table className="min-w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-white/10" style={{ background: "rgba(20,20,32,0.7)" }}>
                {cols.map((h) => (
                  <th key={h} className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.1em] text-faint">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trace.map((s) => (
                <tr key={s.step}
                  className="border-b border-white/5 last:border-0 transition-colors hover:bg-white/[0.025]"
                  style={{ background: s.intent_changed ? "rgba(0,229,255,0.05)" : "transparent" }}>
                  <td className="px-3 py-2 font-mono tabular-nums text-faint">{s.step}</td>
                  <td className="px-3 py-2 font-mono tabular-nums text-ink">{s.observed_latency}ms</td>
                  <td className="px-3 py-2"><IntentBadge intent={s.capacity_agent} /></td>
                  <td className="px-3 py-2"><IntentBadge intent={s.network_agent} /></td>
                  <td className="px-3 py-2"><IntentBadge intent={s.final_intent} /></td>
                  <td className="px-3 py-2 text-[11px]" style={{ color: REASON_COLORS[s.reason] || "#eaeeff" }}>{s.reason}</td>
                  <td className="px-3 py-2 font-mono tabular-nums text-good">{s.trust_score}</td>
                  <td className="px-3 py-2 font-mono tabular-nums text-faint">{s.intent_age}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}

export default function Simulation() {
  const { simSummary, csi, chartData, simTrace } = useDashboard();
  const hasRun = simTrace.length > 0;
  return (
    <div className="flex flex-col gap-stack">
      <Controls />
      {simSummary && <Summary s={simSummary} />}
      {csi && <CsiPanel csi={csi} />}
      {hasRun ? (
        <>
          <Charts data={chartData} />
          <Timeline trace={simTrace} />
          <TraceTable trace={simTrace} />
        </>
      ) : (
        <Card>
          <EmptyState icon={FlaskConical} title="Run a multi-step simulation to see the trace">
            Trust and CSI converge as the evidence window fills. Latency, intent timeline, and the full
            decision trace appear here after a run.
          </EmptyState>
        </Card>
      )}
    </div>
  );
}
