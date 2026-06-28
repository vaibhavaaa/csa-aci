import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import { LayoutDashboard } from "lucide-react";
import { useDashboard } from "@/context/DashboardContext";
import { Card, PanelLabel } from "@/components/ui/card";
import { IntentBadge, KpiTile, EmptyState } from "@/components/shared";
import { REASON_COLORS, csiColor, trustColor } from "@/lib/constants";
import { computeRunningCSI } from "@/lib/metrics";

const TT = {
  contentStyle: { background: "#0c1226", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, fontSize: 11 },
  labelStyle: { color: "#8b95c9" },
};

// ── KPI tiles row ────────────────────────────────────────────
function KpiRow({ metrics }) {
  const health = metrics.governance_health;
  const healthColor = health === "STABLE" ? "#00ff99" : health === "MODERATE" ? "#ffd740" : "#ff4444";
  const tiles = [
    { label: "Total Runs",    value: metrics.total_runs,               color: "#00e5ff", hint: "all-time decisions" },
    { label: "Avg Trust",     value: metrics.average_trust_score,      color: trustColor(metrics.average_trust_score), hint: "across all runs" },
    { label: "High Trust",    value: `${metrics.high_trust_percent}%`, color: "#00ff99", hint: "≥ 0.85 threshold" },
    { label: "Low Trust",     value: metrics.low_trust_runs,           color: "#ff4444", hint: "runs below 0.65" },
    { label: "System Health", value: health,                           color: healthColor, hint: "governance state" },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      {tiles.map((t) => <KpiTile key={t.label} {...t} />)}
    </div>
  );
}

// ── CSI trend sparkline ──────────────────────────────────────
function CsiTrendCard({ csiHistory }) {
  if (!csiHistory.length) {
    return (
      <Card className="flex items-center justify-center text-[12px] text-faint" style={{ minHeight: 180 }}>
        Run single-step decisions to see CSI trend.
      </Card>
    );
  }
  const latest = csiHistory[csiHistory.length - 1];
  const min = Math.min(...csiHistory.map((d) => d.csi));
  const max = Math.max(...csiHistory.map((d) => d.csi));
  return (
    <Card>
      <div className="mb-2 flex items-start justify-between">
        <PanelLabel>CSI Trend</PanelLabel>
        <div className="text-right">
          <div className="font-mono text-3xl font-extrabold leading-none tabular-nums" style={{ color: csiColor(latest.csi) }}>
            {latest.csi}
          </div>
          <div className="mt-0.5 text-[10px] tracking-widest" style={{ color: csiColor(latest.csi) }}>{latest.label}</div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={110}>
        <LineChart data={csiHistory} margin={{ top: 2, right: 4, bottom: 0, left: -28 }}>
          <XAxis dataKey="run" stroke="#1a1f35" tick={{ fill: "#5b6391", fontSize: 9 }} />
          <YAxis domain={[0, 1]} stroke="#1a1f35" tick={{ fill: "#5b6391", fontSize: 9 }} />
          <Tooltip {...TT} formatter={(v) => [v, "CSI"]} />
          <Line type="monotone" dataKey="csi" stroke="#ffd740" strokeWidth={2} dot={{ r: 2, fill: "#ffd740" }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-1.5 flex justify-between text-[10px] text-faint">
        <span>{csiHistory.length} runs</span>
        <span>min {min.toFixed(2)} · max {max.toFixed(2)}</span>
      </div>
    </Card>
  );
}

// ── Intent distribution donut ─────────────────────────────────
const DONUT_INTENTS = [
  { key: "SCALE_UP",   color: "#00e5ff", label: "Scale Up"   },
  { key: "SCALE_DOWN", color: "#ff9800", label: "Scale Down" },
  { key: "HOLD",       color: "#5b6391", label: "Hold"       },
];

function IntentDonutCard({ metrics }) {
  const dist  = metrics.intent_distribution || {};
  const total = Object.values(dist).reduce((s, v) => s + v, 0);
  const data  = DONUT_INTENTS.map(({ key, color, label }) => ({ key, color, label, count: dist[key] || 0 }));
  return (
    <Card>
      <PanelLabel className="mb-3">Intent Distribution</PanelLabel>
      {total === 0 ? (
        <div className="text-[12px] text-faint">No runs yet.</div>
      ) : (
        <div className="flex flex-col items-center gap-4 sm:flex-row">
          <div className="relative shrink-0" style={{ width: 150, height: 150 }}>
            <ResponsiveContainer width="100%" height={150}>
              <PieChart>
                <Pie data={data} dataKey="count" nameKey="label" innerRadius={46} outerRadius={70} strokeWidth={3} stroke="transparent" isAnimationActive={false}>
                  {data.map(({ key, color }) => <Cell key={key} fill={color} />)}
                </Pie>
                <Tooltip {...TT} formatter={(v, n) => [v, n]} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-mono text-2xl font-bold tabular-nums text-ink">{total}</span>
              <span className="text-[9px] uppercase tracking-widest text-faint">decisions</span>
            </div>
          </div>
          <div className="flex flex-1 flex-col gap-2.5">
            {data.map(({ key, color, label, count }) => {
              const pct = total > 0 ? ((count / total) * 100).toFixed(0) : "0";
              return (
                <div key={key} className="flex items-center gap-3">
                  <span className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: color }} />
                  <span className="flex-1 font-mono text-xs text-ink">{label}</span>
                  <span className="font-mono text-xs tabular-nums text-muted">{count}</span>
                  <span className="w-9 text-right font-mono text-xs tabular-nums text-faint">{pct}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}

// ── Recent live decisions ─────────────────────────────────────
function LiveDecisionsCard({ liveEvents }) {
  return (
    <Card>
      <PanelLabel className="mb-2">Live Decisions</PanelLabel>
      {liveEvents.length === 0 ? (
        <div className="mt-2 text-[12px] text-faint">No live events yet — fire a decision on Live Control.</div>
      ) : (
        <div className="flex flex-col">
          {liveEvents.slice(0, 7).map((e, i) => (
            <div key={i} className="flex items-center justify-between gap-2 border-b border-white/5 py-1.5 last:border-0">
              <span className="truncate text-[12px] text-muted">{e.task}</span>
              <div className="flex shrink-0 items-center gap-2">
                <IntentBadge intent={e.result?.final_intent} />
                <span className="font-mono text-[11px] text-good">{e.result?.trust_score}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── Compact run history table ────────────────────────────────
function CompactRunHistory({ history, csiHistory }) {
  const cols = ["#", "Task", "Latency", "Intent", "Reason", "Trust", "CSI"];
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <PanelLabel>Run History</PanelLabel>
        <span className="text-[10px] text-faint">{history.length} total</span>
      </div>
      <div className="overflow-x-auto">
        <div className="inline-block min-w-full overflow-hidden rounded-lg border border-white/10">
          <table className="min-w-full border-collapse text-[11px]">
            <thead>
              <tr className="border-b border-white/10" style={{ background: "rgba(20,20,32,0.7)" }}>
                {cols.map((h) => (
                  <th key={h} className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.1em] text-faint">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...history].reverse().slice(0, 8).map((r, revIdx) => {
                const runNum = history.length - revIdx;
                const csiAfter = csiHistory[runNum - 1];
                return (
                  <tr key={r.id} className="border-b border-white/5 last:border-0 transition-colors hover:bg-white/[0.025]">
                    <td className="px-3 py-2 text-faint">#{runNum}</td>
                    <td className="px-3 py-2 text-ink">{r.task_name}</td>
                    <td className="px-3 py-2 font-mono tabular-nums text-muted">{r.observed_latency != null ? `${r.observed_latency}ms` : "—"}</td>
                    <td className="px-3 py-2"><IntentBadge intent={r.final_intent} /></td>
                    <td className="px-3 py-2 text-[10px]" style={{ color: REASON_COLORS[r.reason] || "#8b95c9" }}>{r.reason ?? "—"}</td>
                    <td className="px-3 py-2 font-mono tabular-nums text-good">{r.trust_score ?? "—"}</td>
                    <td className="px-3 py-2 font-mono font-bold tabular-nums" style={{ color: csiColor(csiAfter?.csi ?? 0) }}>{csiAfter?.csi}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}

// ── Page ─────────────────────────────────────────────────────
export default function Overview() {
  const { metrics, singleRunHistory, liveEvents } = useDashboard();

  const csiHistory = singleRunHistory.map((_, idx) => {
    const slice = singleRunHistory.slice(0, idx + 1);
    const c = computeRunningCSI(slice);
    return { run: idx + 1, csi: c?.csi ?? 0, label: c?.label ?? "-" };
  });

  const empty = !metrics && singleRunHistory.length === 0;

  if (empty) {
    return (
      <Card>
        <EmptyState icon={LayoutDashboard} title="No governance data yet">
          Fire a decision on <span className="text-cyan">Live Control</span> or run a{" "}
          <span className="text-cyan">Simulation</span> to see data here.
        </EmptyState>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-stack">
      {metrics && <KpiRow metrics={metrics} />}

      <div className="grid grid-cols-1 gap-stack lg:grid-cols-3">
        <CsiTrendCard csiHistory={csiHistory} />
        {metrics
          ? <IntentDonutCard metrics={metrics} />
          : <Card className="flex items-center justify-center text-[12px] text-faint">No metrics yet.</Card>}
        <LiveDecisionsCard liveEvents={liveEvents} />
      </div>

      {singleRunHistory.length > 0 && <CompactRunHistory history={singleRunHistory} csiHistory={csiHistory} />}
    </div>
  );
}
