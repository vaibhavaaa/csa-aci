import { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
  BarChart, Bar, CartesianGrid, RadialBarChart, RadialBar, PolarAngleAxis,
} from "recharts";
import { Check, X, Zap, Sparkles, Layers, Trophy, Scale } from "lucide-react";
import { Card, PanelLabel } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { csiColor } from "@/lib/constants";
import { useDashboard } from "@/context/DashboardContext";

// ─── tooltip style ───────────────────────────────────────────────────────────

const TT = {
  contentStyle: { background: "#0c1226", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 10, fontSize: 12 },
  labelStyle: { color: "#8b95c9" },
};

// ─── color helpers ────────────────────────────────────────────────────────────

const f1Color  = (v) => v >= 0.85 ? "#00ff99" : v >= 0.65 ? "#ffd740" : "#ff4444";
const regColor = (n, total) => n === total ? "#00ff99" : n >= total * 0.75 ? "#ffd740" : "#ff4444";

// ─── shared table style ───────────────────────────────────────────────────────

const thCls = "px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-faint";
const ELEV  = { background: "rgba(20,20,32,0.7)" };

// ─── Regime Guide ─────────────────────────────────────────────────────────────

function RegimeGuide({ regimes, conflictRegimes }) {
  const conflictSet = new Set(conflictRegimes);
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {regimes.map((r) => {
        const isConflict = conflictSet.has(r.name);
        const shortKey   = r.name.split(" ")[0];
        return (
          <div
            key={r.name}
            className={cn(
              "flex flex-col gap-1.5 rounded-lg border p-3.5",
              isConflict ? "border-warn/30 bg-warn/[0.04]" : "border-white/8"
            )}
            style={isConflict ? {} : ELEV}
          >
            <span className="flex items-center gap-2">
              <span className={cn("font-mono text-sm font-bold", isConflict ? "text-warn" : "text-ink")}>
                {shortKey}
              </span>
              {isConflict && (
                <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-warn ring-1 ring-inset ring-warn/30">
                  <Zap size={9} />
                  Conflict
                </span>
              )}
            </span>
            <span className="text-[11px] leading-relaxed text-muted">{r.description}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Conflict Insight Tiles ───────────────────────────────────────────────────

function ConflictInsightTiles({ conflict }) {
  const results  = conflict.results;
  const analysis = conflict.analysis;
  const cce      = results.find((r) => r.controller === "CSA-ACI CCE");
  const capable  = results.filter((r) => r.regimes_handled === analysis?.total_regimes);
  const peers    = results.filter((r) => r.controller !== "CSA-ACI CCE" && r.regimes_handled === analysis?.total_regimes);
  const thrashWorse = peers.length ? Math.max(...peers.map((r) => r.total_interventions)) : null;

  const tiles = [
    {
      icon: Layers,
      label: "Capability Split",
      value: String(capable.length),
      sub: `handle all ${analysis?.total_regimes} regimes`,
      detail: `${results.length - capable.length} single-signal controllers fail both ⚡ conflict regimes`,
      tone: "text-ink",
    },
    {
      icon: Trophy,
      label: "Stability Winner",
      value: conflict.winner,
      sub: `${cce?.total_interventions} interventions vs ${thrashWorse ?? "—"} (best multi-signal peer)`,
      detail: "Evidence gate + dwell time ignores transient noise spikes",
      tone: "text-cyan",
    },
    {
      icon: Scale,
      label: "Trade-off Cost",
      value: `${analysis?.cce_slo_violation_steps ?? "—"} SLO-lag steps`,
      sub: "cost of correctness",
      detail: "CCE waits for 6/8 consistent evidence — slower scale-up, bounded by lemma 3",
      tone: "text-warn",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
      {tiles.map(({ icon: Icon, label, value, sub, detail, tone }) => (
        <Card key={label}>
          <span className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
            <Icon size={12} />
            {label}
          </span>
          <div className={cn("mt-2 font-mono text-xl font-bold leading-tight tabular-nums", tone)}>{value}</div>
          <div className="mt-1 text-xs font-medium text-ink/80">{sub}</div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{detail}</p>
        </Card>
      ))}
    </div>
  );
}

// ─── Capability Matrix ────────────────────────────────────────────────────────

function CapabilityMatrix({ results, conflictRegimes, total }) {
  const regimeNames = Object.keys(results[0].per_regime);
  const conflictSet = new Set(conflictRegimes);
  return (
    <div className="inline-block overflow-hidden rounded-lg border border-white/10">
      <table className="w-auto border-collapse">
        <thead>
          <tr className="border-b border-white/10" style={ELEV}>
            <th className={thCls}>Controller</th>
            <th className={thCls}>Signal</th>
            {regimeNames.map((n) => (
              <th
                key={n}
                className={cn(
                  "px-4 py-2.5 text-center text-[10px] font-semibold uppercase tracking-[0.12em]",
                  conflictSet.has(n) ? "text-warn" : "text-faint"
                )}
              >
                <span className="inline-flex items-center gap-1">
                  {n.split(" ")[0]}
                  {conflictSet.has(n) && <Zap size={10} />}
                </span>
              </th>
            ))}
            <th className="px-4 py-2.5 text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">Score</th>
            <th className="px-4 py-2.5 text-right text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">Interv.</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r) => {
            const isCCE = r.controller === "CSA-ACI CCE";
            return (
              <tr
                key={r.controller}
                className="border-b border-white/5 last:border-0 transition-colors hover:bg-white/[0.025]"
                style={{ background: isCCE ? "rgba(0,229,255,0.055)" : "transparent" }}
              >
                <td className="whitespace-nowrap px-4 py-2.5 text-sm font-medium"
                  style={{ color: isCCE ? "#00e5ff" : "#eaeeff" }}>
                  <span className="inline-flex items-center gap-1.5">
                    {isCCE && <Sparkles size={12} className="text-cyan" />}
                    {r.controller}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-muted">{r.signal}</td>
                {Object.entries(r.per_regime).map(([n, data]) => {
                  const ok         = data.steady_state_correct;
                  const isConflict = conflictSet.has(n);
                  return (
                    <td
                      key={n}
                      className="px-4 py-2.5 text-center"
                      style={{ background: isConflict ? "rgba(255,215,64,0.04)" : "transparent" }}
                    >
                      {ok
                        ? <Check size={15} className="mx-auto text-good" />
                        : <X     size={15} className="mx-auto text-bad"  />
                      }
                    </td>
                  );
                })}
                <td className="px-4 py-2.5 text-center font-mono text-sm font-bold tabular-nums"
                  style={{ color: regColor(r.regimes_handled, total) }}>
                  {r.regimes_handled}/{total}
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-sm tabular-nums"
                  style={{ color: isCCE ? "#00e5ff" : "rgba(234,238,255,0.75)", fontWeight: isCCE ? 700 : 400 }}>
                  {r.total_interventions}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Controller Cards ─────────────────────────────────────────────────────────

function ControllerCards({ results, conflictRegimes, total }) {
  const conflictSet = new Set(conflictRegimes);
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
      {results.map((r) => {
        const isCCE      = r.controller === "CSA-ACI CCE";
        const score      = r.regimes_handled;
        const scoreColor = regColor(score, total);
        const regimes    = Object.entries(r.per_regime);
        return (
          <div
            key={r.controller}
            className={cn(
              "flex flex-col gap-3 rounded-xl border p-4",
              isCCE ? "border-cyan/40 bg-cyan/[0.04]" : "border-white/8 bg-white/[0.02]"
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex flex-col gap-0.5">
                <span className={cn("flex items-center gap-1.5 text-sm font-semibold leading-tight",
                  isCCE ? "text-cyan" : "text-ink")}>
                  {isCCE && <Sparkles size={12} />}
                  {r.controller}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-wider text-faint">
                  {r.signal}
                </span>
              </div>
              <span
                className="shrink-0 rounded-md px-1.5 py-0.5 font-mono text-[11px] ring-1 ring-inset tabular-nums"
                style={{ color: scoreColor, background: scoreColor + "18", borderColor: scoreColor + "44" }}
              >
                {score}/{total}
              </span>
            </div>

            <div className="grid grid-cols-4 gap-1">
              {regimes.map(([name, data], i) => {
                const ok         = data.steady_state_correct;
                const isConflict = conflictSet.has(name);
                return (
                  <div
                    key={name}
                    className={cn(
                      "flex flex-col items-center gap-1 rounded-md py-1.5",
                      ok ? "bg-good/[0.08]" : "bg-bad/[0.08]"
                    )}
                  >
                    <span className={cn("text-[9px] font-medium uppercase tracking-wide",
                      isConflict ? "text-warn" : "text-faint")}>
                      R{i + 1}
                    </span>
                    {ok
                      ? <Check size={12} className="text-good" />
                      : <X     size={12} className="text-bad"  />
                    }
                  </div>
                );
              })}
            </div>

            <div className="flex flex-col items-center border-t border-white/10 pt-3">
              <span
                className="font-mono text-3xl font-bold tabular-nums leading-none"
                style={{ color: isCCE ? "#00e5ff" : "#eaeeff" }}
              >
                {r.total_interventions}
              </span>
              <span className="mt-1 text-[9px] uppercase tracking-[0.12em] text-faint">Interventions</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── F1 Gauge Card ────────────────────────────────────────────────────────────

function F1GaugeCard({ result }) {
  const isCCE      = result.controller === "CSA-ACI CCE";
  const f1         = result.f1 ?? 0;
  const recall     = result.recall ?? 0;
  const quietTrace = f1 === 0 && recall === 0;
  const color      = quietTrace ? "#5b6391" : f1Color(f1);

  return (
    <div className={cn(
      "flex flex-col items-center gap-2 rounded-xl border p-4",
      isCCE ? "border-cyan/40 bg-cyan/[0.04]" : "border-white/8 bg-white/[0.02]"
    )}>
      <div className="text-center">
        <div className="text-[12px] font-semibold leading-tight" style={{ color: isCCE ? "#00e5ff" : "#eaeeff" }}>
          {isCCE && "★ "}{result.controller}
        </div>
        <div className="mt-0.5 line-clamp-2 text-[10px] leading-tight text-muted">
          {result.description ?? result.signal ?? ""}
        </div>
      </div>

      {quietTrace ? (
        <div className="flex w-full flex-col items-center gap-1 rounded-lg border border-white/7 bg-white/[0.03] px-3 py-4">
          <div className="font-mono text-2xl font-extrabold tabular-nums text-faint">N/A</div>
          <div className="text-center text-[9px] leading-relaxed text-faint">
            Quiet trace — no scale-up events to recall
          </div>
        </div>
      ) : (
        <div className="relative w-full" style={{ height: 90 }}>
          <ResponsiveContainer width="100%" height={90}>
            <RadialBarChart
              cx="50%" cy="90%"
              innerRadius="62%" outerRadius="96%"
              startAngle={180} endAngle={0}
              data={[{ value: f1 * 100 }]}
            >
              <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
              <RadialBar
                dataKey="value"
                cornerRadius={5}
                background={{ fill: "rgba(255,255,255,0.06)" }}
                fill={color}
                angleAxisId={0}
                isAnimationActive={false}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex flex-col items-center">
            <div className="font-mono text-xl font-extrabold tabular-nums leading-none" style={{ color }}>{f1}</div>
            <div className="text-[9px] uppercase tracking-widest text-faint">F1</div>
          </div>
        </div>
      )}

      <div className="mt-1 grid w-full grid-cols-3 gap-1 border-t border-white/10 pt-2.5">
        {[
          ["FP",     result.false_positives ?? "—", (result.false_positives ?? 0) === 0 ? "#00ff99" : "#ff4444", "False positives"],
          ["Recall", result.recall ?? "—",           "#00e5ff", "Fraction of genuine scale-up events detected"],
          ["Switch", result.intent_switches ?? "—",  "#ffd740", "Intent changes — lower = more stable"],
        ].map(([label, val, clr, tip]) => (
          <div key={label} className="text-center" title={tip}>
            <div className="font-mono text-base font-extrabold tabular-nums" style={{ color: clr }}>{val}</div>
            <div className="text-[9px] uppercase tracking-wide text-faint">{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Replay FP Bars ───────────────────────────────────────────────────────────

function ReplayBars({ results }) {
  const hasRecall = results.some((r) => (r.recall ?? 0) > 0);
  const data = results.map((r) => ({
    name: r.controller
      .replace("Reactive", "Rx").replace("Controller", "Ctrl")
      .replace("Kubernetes HPA", "K8s HPA").replace("Multi-Metric", "MM")
      .replace("Multi-Signal", "MS").replace("CSA-ACI CCE", "★ CCE"),
    F1:     r.f1 ?? 0,
    Recall: r.recall ?? 0,
  }));

  return (
    <Card>
      <PanelLabel className="mb-2">Performance Comparison — all controllers on identical trace</PanelLabel>

      {!hasRecall && (
        <div className="my-3 rounded-lg border border-warn/25 bg-warn/5 px-3 py-2.5 text-[11px] text-muted">
          <span className="font-semibold text-warn">Quiet trace: </span>
          Rolling-median latency never crossed 100ms — no genuine scale-up events to detect.{" "}
          <strong className="text-ink">False positives still differentiate controllers.</strong>
        </div>
      )}

      {hasRecall && (
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 36 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="name" stroke="#1a1f35" tick={{ fill: "#8b95c9", fontSize: 10 }} angle={-28} textAnchor="end" interval={0} />
            <YAxis stroke="#1a1f35" tick={{ fill: "#5b6391", fontSize: 9 }} domain={[0, 1]} />
            <Tooltip {...TT} />
            <Bar dataKey="F1"     fill="#00ff99" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="Recall" fill="#00e5ff" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      )}

      <div className={hasRecall ? "mt-3 border-t border-white/10 pt-3" : ""}>
        <div className="mb-2 text-[10px] uppercase tracking-wider text-faint">
          False Positives <span className="normal-case">— unnecessary SCALE_UP decisions (lower = better)</span>
        </div>
        {[...results].sort((a, b) => (a.false_positives ?? 0) - (b.false_positives ?? 0)).map((r) => {
          const isCCE  = r.controller === "CSA-ACI CCE";
          const fp     = r.false_positives ?? 0;
          const maxFp  = Math.max(...results.map((x) => x.false_positives ?? 0), 1);
          const color  = fp === 0 ? "#00ff99" : fp <= 5 ? "#ffd740" : "#ff4444";
          const short  = r.controller
            .replace("Reactive", "Rx").replace("Controller", "Ctrl")
            .replace("Kubernetes HPA", "K8s HPA").replace("Multi-Metric", "MM")
            .replace("Multi-Signal", "MS").replace("CSA-ACI CCE", "★ CCE");
          return (
            <div key={r.controller} className="mb-1.5 flex items-center gap-2">
              <div className="w-24 shrink-0 text-[11px]" style={{ color: isCCE ? "#00e5ff" : "#8b95c9" }}>{short}</div>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full" style={{ width: `${(fp / maxFp) * 100}%`, background: color }} />
              </div>
              <div className="w-5 text-right font-mono text-[11px] font-bold tabular-nums" style={{ color }}>{fp}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ─── Metric Table ─────────────────────────────────────────────────────────────

function MetricTable({ results }) {
  const cols = [
    ["controller", "Controller"], ["f1", "F1"], ["false_positives", "False Pos"],
    ["recall", "Recall"], ["intent_switches", "Switches"], ["avg_response_lag", "Resp Lag"],
  ];
  return (
    <div className="inline-block overflow-hidden rounded-lg border border-white/10">
      <table className="w-auto border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-white/10" style={ELEV}>
            {cols.map(([, h]) => <th key={h} className={thCls}>{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {results.map((r) => {
            const isCCE = r.controller === "CSA-ACI CCE";
            return (
              <tr
                key={r.controller}
                className="border-b border-white/5 last:border-0 transition-colors hover:bg-white/[0.025]"
                style={{ background: isCCE ? "rgba(0,229,255,0.055)" : "transparent" }}
              >
                {cols.map(([k]) => (
                  <td key={k} className="px-4 py-2.5 font-mono tabular-nums"
                    style={{ color: isCCE && k === "controller" ? "#00e5ff" : "#eaeeff", fontWeight: isCCE && k === "controller" ? 700 : 400 }}>
                    {k === "controller" ? `${isCCE ? "★ " : ""}${r[k]}` : r[k]}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Source Badge ─────────────────────────────────────────────────────────────

function SourceBadge({ source }) {
  const real = source === "real";
  const c    = real ? "#00ff99" : "#ff4444";
  return (
    <span className="rounded-md px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider"
      style={{ background: c + "22", color: c, border: `1px solid ${c}55` }}>
      {real ? "● Real data" : "▲ Synthetic fallback — not paper-valid"}
    </span>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ResearchPanels({ token, API: apiProp }) {
  const API = apiProp ?? (import.meta.env.VITE_API_URL || "");
  const { setConflictResult, setReplayResult } = useDashboard();

  const [dataset,      setDataset]      = useState("google");
  const [nSteps,       setNSteps]       = useState(200);
  const [replay,       setReplay]       = useState(null);
  const [replayBusy,   setReplayBusy]   = useState(false);

  const [nRuns,        setNRuns]        = useState(30);
  const [stress,       setStress]       = useState(null);
  const [stressBusy,   setStressBusy]   = useState(false);

  const [sweep,        setSweep]        = useState(null);
  const [sweepBusy,    setSweepBusy]    = useState(false);

  const [conflict,     setConflict]     = useState(null);
  const [conflictBusy, setConflictBusy] = useState(false);

  const [err, setErr] = useState("");

  const auth = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  async function post(path, body) {
    const res = await fetch(`${API}${path}`, { method: "POST", headers: auth, body: JSON.stringify(body || {}) });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
  }

  async function runConflict() {
    if (!token) return setErr("Token required.");
    setConflictBusy(true); setErr("");
    try {
      const data = await post("/tasks/conflict-experiment", {});
      setConflict(data);
      setConflictResult(data);
    } catch (e) { setErr(`Conflict experiment failed: ${e.message}`); }
    setConflictBusy(false);
  }

  async function runReplay() {
    if (!token) return setErr("Token required.");
    setReplayBusy(true); setErr("");
    try {
      const data = await post("/tasks/trace-replay", { dataset, n_steps: Number(nSteps) });
      setReplay(data);
      setReplayResult(data);
    } catch (e) { setErr(`Trace replay failed: ${e.message}`); }
    setReplayBusy(false);
  }

  async function runStress() {
    if (!token) return setErr("Token required.");
    setStressBusy(true); setErr("");
    try { setStress(await post("/tasks/stress-test", { n_runs: Number(nRuns), dataset: null })); }
    catch (e) { setErr(`Stress test failed: ${e.message}`); }
    setStressBusy(false);
  }

  async function runSweep() {
    if (!token) return setErr("Token required.");
    setSweepBusy(true); setErr("");
    try { setSweep(await post("/tasks/sensitivity", {})); }
    catch (e) { setErr(`Sensitivity sweep failed: ${e.message}`); }
    setSweepBusy(false);
  }

  function exportCsv() {
    if (!token) return setErr("Token required.");
    fetch(`${API}/tasks/history/export`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = "csa_aci_history.csv"; a.click();
        URL.revokeObjectURL(url);
      })
      .catch((e) => setErr(`Export failed: ${e.message}`));
  }

  const latencyChart = replay ? replay.latency.map((v, i) => ({ step: i, latency: v })) : [];

  return (
    <div className="flex flex-col gap-3">
      <div className="text-sm font-bold text-cyan">Research Suite — Paper-Grade Experiments</div>
      {err && <div className="text-xs text-bad">✗ {err}</div>}

      {/* ══ Multi-Signal Conflict ══════════════════════════════════════════════ */}
      <Card>
        <div className="mb-1 flex items-start justify-between gap-4">
          <div>
            <PanelLabel>★ Multi-Signal Conflict — CSA-ACI vs Single-Loop Controllers (incl. K8s HPA)</PanelLabel>
            <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
              Two independent signals (CPU + latency), four sustained regimes. Two are{" "}
              <b className="text-warn">conflicts</b> where signals disagree. Single-signal
              controllers are blind to one side — only multi-signal arbitration handles both.
            </p>
          </div>
          <Button variant="cyan" className="shrink-0" onClick={runConflict} disabled={conflictBusy}>
            {conflictBusy ? "Running…" : "▶ Run Conflict Experiment"}
          </Button>
        </div>

        {conflict && (
          <div className="mt-5 flex flex-col gap-4">
            {/* summary line */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
              <span className="text-muted">
                stability winner: <span className="font-bold text-cyan">{conflict.winner}</span>
              </span>
              {conflict.responsiveness_winner && (
                <span className="text-muted">
                  responsiveness winner: <span className="font-semibold text-warn">{conflict.responsiveness_winner}</span>
                </span>
              )}
              <span className="text-muted">
                CCE handled{" "}
                <b className="text-good">{conflict.analysis.cce_regimes_handled}/{conflict.analysis.total_regimes}</b>{" "}
                regimes
              </span>
            </div>

            {/* verdict */}
            {conflict.analysis.verdict && (
              <div className="rounded-lg border border-cyan/25 bg-cyan/[0.06] px-3.5 py-2.5 text-[11px] leading-relaxed text-muted">
                {conflict.analysis.verdict}
              </div>
            )}

            {/* 3 insight tiles */}
            <ConflictInsightTiles conflict={conflict} />

            {/* regime guide */}
            <div>
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
                Regime Guide — what each test scenario evaluates
              </div>
              <RegimeGuide
                regimes={conflict.regimes ?? []}
                conflictRegimes={conflict.analysis?.conflict_regimes}
              />
            </div>

            {/* capability matrix */}
            <div>
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
                Capability Matrix — correct decision in steady-state per regime
              </div>
              <div className="overflow-x-auto">
                <CapabilityMatrix
                  results={conflict.results}
                  conflictRegimes={conflict.analysis?.conflict_regimes}
                  total={conflict.analysis?.total_regimes ?? 4}
                />
              </div>
            </div>

            {/* controller cards */}
            <div>
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
                Stability — per controller
              </div>
              <ControllerCards
                results={conflict.results}
                conflictRegimes={conflict.analysis?.conflict_regimes}
                total={conflict.analysis?.total_regimes ?? 4}
              />
            </div>

            {/* ground truth note */}
            <div className="rounded-lg border border-cyan/20 bg-cyan/[0.05] px-3.5 py-2.5 text-[11px] text-muted">
              {conflict.ground_truth_note}
            </div>
          </div>
        )}
      </Card>

      {/* ══ Trace Replay ═══════════════════════════════════════════════════════ */}
      <Card>
        <PanelLabel className="mb-3">Real-Trace Replay — All Controllers on a Production Trace</PanelLabel>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Dataset">
            <select
              value={dataset}
              onChange={(e) => setDataset(e.target.value)}
              className="glass-inset rounded-lg px-3 py-2 font-mono text-sm text-ink outline-none focus:border-cyan/50"
            >
              <option value="google">Google Cluster Trace</option>
              <option value="wikipedia">Wikipedia Pageviews</option>
            </select>
          </Field>
          <Field label="Steps">
            <Input type="number" value={nSteps} onChange={(e) => setNSteps(e.target.value)} className="w-24" />
          </Field>
          <Button variant="cyan" onClick={runReplay} disabled={replayBusy}>
            {replayBusy ? "Replaying…" : "▶ Replay Trace"}
          </Button>
          <Button variant="warn" onClick={exportCsv}>⬇ Export History CSV</Button>
        </div>

        {replay && (
          <div className="mt-5 flex flex-col gap-4">
            <div className="flex flex-wrap items-center gap-3">
              <SourceBadge source={replay.source} />
              <span className="text-xs text-muted">
                {replay.label} · {replay.telemetry_steps} steps · winner:{" "}
                <span className="text-cyan font-semibold">{replay.winner}</span>
              </span>
            </div>

            {/* SPLIT: trace chart (3/5) + F1 gauges (2/5) */}
            <div className="grid gap-4 xl:grid-cols-5 xl:items-start">
              <div className="xl:col-span-3">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
                  Latency trace
                </div>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={latencyChart}>
                    <XAxis dataKey="step" stroke="#223" tick={{ fill: "#5b6391", fontSize: 10 }} />
                    <YAxis stroke="#223" tick={{ fill: "#5b6391", fontSize: 10 }} unit="ms" width={40} />
                    <Tooltip {...TT} />
                    <ReferenceLine y={100} stroke="#ff444455" strokeDasharray="4 4" />
                    <ReferenceLine y={300} stroke="#ec489955" strokeDasharray="4 4" />
                    <Line type="monotone" dataKey="latency" stroke="#00e5ff" strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="xl:col-span-2">
                <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
                  F1 per controller
                </div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-2">
                  {replay.results.map((r) => (
                    <F1GaugeCard key={r.controller} result={r} />
                  ))}
                </div>
              </div>
            </div>

            {/* full metric table */}
            <div>
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-faint">
                Full metrics
              </div>
              <div className="overflow-x-auto">
                <MetricTable results={replay.results} />
              </div>
            </div>

            {/* FP comparison bars */}
            <ReplayBars results={replay.results} />

            {/* ground truth note */}
            <div className="rounded-lg border border-cyan/20 bg-cyan/[0.05] px-3.5 py-2.5 text-[11px] text-muted">
              {replay.ground_truth_note}
            </div>
          </div>
        )}
      </Card>

      {/* ══ Stress Test ════════════════════════════════════════════════════════ */}
      <Card>
        <PanelLabel className="mb-3">Statistical Stress Test — N Runs, Mean ± Std, Significance</PanelLabel>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="N Runs">
            <Input type="number" value={nRuns} onChange={(e) => setNRuns(e.target.value)} className="w-24" />
          </Field>
          <Button variant="good" onClick={runStress} disabled={stressBusy}>
            {stressBusy ? "Running…" : "▶ Run Stress Test"}
          </Button>
        </div>

        {stress && (
          <div className="mt-4">
            <div className="mb-3 text-xs text-muted">{stress.n_runs} runs · regime: {stress.regime}</div>
            <div className="mb-4 flex flex-wrap gap-2">
              {Object.entries(stress.significance.tests).map(([metric, t]) => {
                const c = t.significant_0_05 ? "#00ff99" : "#ff9800";
                return (
                  <div key={metric} className="rounded-lg px-3.5 py-2 text-[11px]"
                    style={{ background: c + "18", border: `1px solid ${c}55` }}>
                    <span className="text-muted">CCE vs {stress.significance.cce_vs} — {metric}: </span>
                    <span className="font-bold tabular-nums" style={{ color: c }}>
                      p = {t.p_value ?? "n/a"} {t.significant_0_05 ? "(sig.)" : "(n.s.)"}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="overflow-x-auto">
              <div className="inline-block overflow-hidden rounded-lg border border-white/10">
                <table className="w-auto border-collapse text-[13px]">
                  <thead>
                    <tr className="border-b border-white/10" style={ELEV}>
                      {["Controller", "Switches (mean±std)", "95% CI", "F1 (mean±std)", "Recall (mean)"].map((h) => (
                        <th key={h} className={thCls}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(stress.controllers).map(([name, m]) => {
                      const isCCE = name === "CSA-ACI CCE";
                      return (
                        <tr key={name}
                          className="border-b border-white/5 last:border-0 transition-colors hover:bg-white/[0.025]"
                          style={{ background: isCCE ? "rgba(0,229,255,0.055)" : "transparent" }}>
                          <td className="whitespace-nowrap px-4 py-2.5"
                            style={{ color: isCCE ? "#00e5ff" : "#eaeeff", fontWeight: isCCE ? 700 : 400 }}>
                            {isCCE ? "★ " : ""}{name}
                          </td>
                          <td className="px-4 py-2.5 font-mono tabular-nums text-warn">{m.intent_switches.mean} ± {m.intent_switches.std}</td>
                          <td className="px-4 py-2.5 font-mono tabular-nums text-muted">[{m.intent_switches.ci95[0]}, {m.intent_switches.ci95[1]}]</td>
                          <td className="px-4 py-2.5 font-mono tabular-nums text-good">{m.f1.mean} ± {m.f1.std}</td>
                          <td className="px-4 py-2.5 font-mono tabular-nums text-ink">{m.recall.mean}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* ══ Sensitivity Heatmap ════════════════════════════════════════════════ */}
      <Card>
        <PanelLabel className="mb-3">Hyperparameter Sensitivity — CSI across CCE configs</PanelLabel>
        <Button variant="warn" onClick={runSweep} disabled={sweepBusy}>
          {sweepBusy ? "Sweeping…" : "▶ Run Sensitivity Sweep"}
        </Button>

        {sweep && (
          <div className="mt-4">
            <div className="mb-3 text-xs text-muted">
              {sweep.grid.length} configs · best CSI{" "}
              <span className="font-bold tabular-nums" style={{ color: csiColor(sweep.best.csi) }}>{sweep.best.csi}</span>{" "}
              at (window={sweep.best.evidence_window}, req={sweep.best.evidence_required_count}, dwell={sweep.best.min_dwell_time})
              {sweep.default && (
                <> · default(8,6,10) ={" "}
                  <span className="font-bold tabular-nums" style={{ color: csiColor(sweep.default.csi) }}>{sweep.default.csi}</span>
                </>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="border-collapse text-[10px]">
                <thead>
                  <tr>
                    <th className="px-2 py-1 text-left text-faint">win / req \ dwell</th>
                    {sweep.swept.min_dwell_time.map((d) => (
                      <th key={d} className="px-2 py-1 text-center text-faint tabular-nums">{d}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from(new Set(sweep.grid.map((c) => `${c.evidence_window}/${c.evidence_required_count}`))).map((rowKey) => {
                    const [w, req] = rowKey.split("/").map(Number);
                    return (
                      <tr key={rowKey}>
                        <td className="px-2 py-1 text-muted tabular-nums">{w} / {req}</td>
                        {sweep.swept.min_dwell_time.map((d) => {
                          const cell      = sweep.grid.find((c) => c.evidence_window === w && c.evidence_required_count === req && c.min_dwell_time === d);
                          const isDefault = w === 8 && req === 6 && d === 10;
                          return (
                            <td key={d} title={cell ? `CSI ${cell.csi}, switches ${cell.intent_switches}` : ""}
                              className="px-2.5 py-2 text-center tabular-nums"
                              style={{
                                background: cell ? csiColor(cell.csi) + "33" : "transparent",
                                border:     isDefault ? "2px solid #00e5ff" : "1px solid rgba(255,255,255,0.06)",
                                color:      cell ? csiColor(cell.csi) : "#334",
                                fontWeight: isDefault ? 700 : 400,
                              }}>
                              {cell ? cell.csi : "—"}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-2 text-[10px] italic text-faint">
              Cyan border = default config. Flat CSI around the default validates the chosen hyperparameters.
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
