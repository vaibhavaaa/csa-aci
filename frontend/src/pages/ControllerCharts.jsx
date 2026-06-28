import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadialBarChart, RadialBar, Cell,
} from "recharts";
import { useDashboard } from "@/context/DashboardContext";
import { Card, PanelLabel } from "@/components/ui/card";

const TT = {
  contentStyle: { background: "#0c1226", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#8b95c9" },
};
const f1Color  = (v) => v >= 0.85 ? "#00ff99" : v >= 0.65 ? "#ffd740" : "#ff4444";
const regColor = (n, total) => n === total ? "#00ff99" : n >= total * 0.75 ? "#ffd740" : "#ff4444";

function Pill({ children, color }) {
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide"
      style={{ background: color + "22", color, border: `1px solid ${color}44` }}>
      {children}
    </span>
  );
}

function EmptyState({ hint }) {
  return (
    <Card>
      <div className="flex flex-col items-center gap-2 py-10 text-center">
        <div className="text-4xl opacity-20">⚗</div>
        <div className="text-[13px] text-muted">No data yet</div>
        <div className="text-[11px] text-faint">{hint}</div>
      </div>
    </Card>
  );
}

// ── Conflict: Regime legend ───────────────────────────────────
function RegimeLegend({ regimes, conflictRegimes }) {
  const conflictSet = new Set(conflictRegimes);
  return (
    <Card>
      <PanelLabel className="mb-3">Regime Guide — what each test scenario evaluates</PanelLabel>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {regimes.map((r) => {
          const isConflict = conflictSet.has(r.name);
          const color = isConflict ? "#ffd740" : "#5b6391";
          const shortKey = r.name.split(" ")[0]; // "R1", "R2", etc.
          return (
            <div key={r.name} className="rounded-lg p-2.5"
              style={{ background: isConflict ? "#ffd74012" : "#ffffff07", border: `1px solid ${isConflict ? "#ffd74035" : "rgba(255,255,255,0.08)"}` }}>
              <div className="mb-1 flex items-center gap-1.5">
                <span className="text-[13px] font-extrabold" style={{ color }}>{shortKey}</span>
                {isConflict && <Pill color="#ffd740">⚡ conflict</Pill>}
              </div>
              <div className="text-[11px] leading-relaxed text-muted">{r.description}</div>
            </div>
          );
        })}
      </div>
      <div className="mt-2.5 text-[10px] text-faint">
        ⚡ = conflict regime: CPU and latency signals <em>disagree</em>. Single-signal controllers see only one and get it wrong.
        Multi-signal controllers arbitrate both — that's the CCE advantage.
      </div>
    </Card>
  );
}

// ── Conflict: Key insight row ────────────────────────────────
function ConflictInsight({ conflictResult }) {
  const results = conflictResult.results;
  const analysis = conflictResult.analysis;
  const cce = results.find((r) => r.controller === "CSA-ACI CCE");
  const capable = results.filter((r) => r.regimes_handled === analysis?.total_regimes);
  const thrashWorse = Math.max(...results
    .filter((r) => r.controller !== "CSA-ACI CCE" && r.regimes_handled === analysis?.total_regimes)
    .map((r) => r.total_interventions));

  return (
    <div className="grid grid-cols-3 gap-stack">
      <Card className="border border-good/20">
        <div className="text-[10px] uppercase tracking-wider text-faint">Capability split</div>
        <div className="mt-1 flex items-baseline gap-1.5">
          <span className="text-2xl font-extrabold text-good">{capable.length}</span>
          <span className="text-[12px] text-muted">controllers handle all {analysis?.total_regimes} regimes</span>
        </div>
        <div className="mt-1 text-[10px] text-faint">
          {results.length - capable.length} single-signal controllers fail both ⚡ conflict regimes
        </div>
      </Card>

      <Card className="border border-cyan/20">
        <div className="text-[10px] uppercase tracking-wider text-faint">Stability winner</div>
        <div className="mt-1 text-[14px] font-bold text-cyan">★ {conflictResult.winner}</div>
        <div className="mt-1 text-[10px] text-faint">
          {cce?.total_interventions} interventions vs {thrashWorse || "—"} (best multi-signal peer)
          — evidence gate + dwell ignores transient noise spikes
        </div>
      </Card>

      <Card className="border border-warn/20">
        <div className="text-[10px] uppercase tracking-wider text-faint">Trade-off (CCE cost)</div>
        <div className="mt-1 text-[14px] font-bold text-warn">{analysis?.cce_slo_violation_steps ?? "—"} SLO-lag steps</div>
        <div className="mt-1 text-[10px] text-faint">
          Response lag ≤ dwell time — CCE waits for {"{"}6/8{"}"}
          consistent evidence before acting; bounded by lemma 3
        </div>
      </Card>
    </div>
  );
}

// ── Conflict: Capability matrix ──────────────────────────────
function CapabilityMatrix({ results, conflictRegimes, total }) {
  const regimeNames = Object.keys(results[0].per_regime);
  const conflictSet = new Set(conflictRegimes);
  return (
    <Card>
      <PanelLabel className="mb-3">Capability Matrix — correct decision in steady-state for each regime</PanelLabel>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-white/10">
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-faint">Controller</th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-faint">Reads</th>
              {regimeNames.map((n) => (
                <th key={n} title={n} className="px-3 py-2 text-center text-[11px] font-semibold"
                  style={{ color: conflictSet.has(n) ? "#ffd740" : "#5b6391" }}>
                  {n.split(" ")[0]}{conflictSet.has(n) ? " ⚡" : ""}
                </th>
              ))}
              <th className="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-wider text-faint" title="Regimes handled correctly">Score</th>
              <th className="px-3 py-2 text-center text-[11px] font-semibold uppercase tracking-wider text-faint" title="Total SCALE_UP / SCALE_DOWN actions — lower = more stable">Interv. ↓</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => {
              const isCCE = r.controller === "CSA-ACI CCE";
              return (
                <tr key={r.controller} className="border-t border-white/5"
                  style={{ background: isCCE ? "rgba(0,229,255,0.055)" : "transparent" }}>
                  <td className="px-3 py-2.5 text-[13px] font-semibold" style={{ color: isCCE ? "#00e5ff" : "#eaeeff" }}>
                    {isCCE ? "★ " : ""}{r.controller}
                  </td>
                  <td className="px-3 py-2.5 text-[11px] text-muted">{r.signal}</td>
                  {regimeNames.map((n) => {
                    const ok = r.per_regime[n].steady_state_correct;
                    return (
                      <td key={n} className="px-3 py-2.5 text-center">
                        <span className="inline-flex h-6 w-6 items-center justify-center rounded-md text-sm font-bold"
                          style={{ background: ok ? "#00ff9920" : "#ff444420", color: ok ? "#00ff99" : "#ff4444" }}>
                          {ok ? "✓" : "✗"}
                        </span>
                      </td>
                    );
                  })}
                  <td className="px-3 py-2.5 text-center font-bold"
                    style={{ color: regColor(r.regimes_handled, total) }}>
                    {r.regimes_handled}/{total}
                  </td>
                  <td className="px-3 py-2.5 text-center text-[13px]"
                    style={{ color: isCCE ? "#00e5ff" : "#8b95c9", fontWeight: isCCE ? 700 : 400 }}>
                    {r.total_interventions}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ── Conflict: Intervention ranking ───────────────────────────
function InterventionRank({ results, total }) {
  const sorted = [...results].sort((a, b) => a.total_interventions - b.total_interventions);
  const max = sorted[sorted.length - 1].total_interventions;
  return (
    <Card>
      <PanelLabel className="mb-1">Stability — intervention count</PanelLabel>
      <div className="mb-3 text-[10px] text-faint">
        Fewer interventions = more stable. CCE's evidence gate ignores noise; reactive controllers switch on every spike.
      </div>
      <div className="flex flex-col gap-2">
        {sorted.map((r) => {
          const isCCE = r.controller === "CSA-ACI CCE";
          const allRegimes = r.regimes_handled === total;
          const color = isCCE ? "#00e5ff" : allRegimes ? "#00ff99" : "#8b95c9";
          const pct = (r.total_interventions / max) * 100;
          const short = r.controller
            .replace("Reactive", "Rx").replace("Controller", "Ctrl")
            .replace("Kubernetes HPA", "K8s HPA").replace("Multi-Metric", "MM")
            .replace("Multi-Signal", "MS").replace("CSA-ACI CCE", "★ CCE");
          return (
            <div key={r.controller}>
              <div className="mb-1 flex items-center justify-between text-[11px]">
                <span className="font-medium" style={{ color }}>{short}</span>
                <span className="font-bold tabular-nums" style={{ color }}>{r.total_interventions}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ── Conflict: Per-controller card ────────────────────────────
function ConflictCard({ result, conflictRegimes, total }) {
  const isCCE = result.controller === "CSA-ACI CCE";
  const regimes = Object.entries(result.per_regime);
  const conflictSet = new Set(conflictRegimes);
  const score = result.regimes_handled;
  const scoreColor = regColor(score, total);
  return (
    <Card className={isCCE ? "ring-1 ring-cyan/30" : ""}>
      <div className="flex items-start justify-between gap-1">
        <div>
          <div className="text-[12px] font-bold leading-tight" style={{ color: isCCE ? "#00e5ff" : "#eaeeff" }}>
            {isCCE ? "★ " : ""}{result.controller}
          </div>
          <div className="text-[10px] text-muted">{result.signal}</div>
        </div>
        <Pill color={scoreColor}>{score}/{total}</Pill>
      </div>

      <div className="mt-2.5 grid grid-cols-2 gap-1">
        {regimes.map(([name, data]) => {
          const ok = data.steady_state_correct;
          const isConflict = conflictSet.has(name);
          return (
            <div key={name} className="flex items-center gap-1.5 rounded-md px-2 py-1.5"
              style={{ background: ok ? "#00ff9915" : "#ff444415", border: `1px solid ${ok ? "#00ff9930" : "#ff444430"}` }}>
              <span className="text-sm font-bold" style={{ color: ok ? "#00ff99" : "#ff4444" }}>{ok ? "✓" : "✗"}</span>
              <span className="text-[10px] text-faint leading-none">{name.split(" ")[0]}{isConflict ? " ⚡" : ""}</span>
            </div>
          );
        })}
      </div>

      <div className="mt-3 border-t border-white/10 pt-2.5 text-center">
        <div className="text-2xl font-extrabold leading-none" style={{ color: isCCE ? "#00e5ff" : "#8b95c9" }}>
          {result.total_interventions}
        </div>
        <div className="mt-0.5 text-[9px] uppercase tracking-wider text-faint">interventions</div>
      </div>
    </Card>
  );
}

// ── Trace replay: F1 gauge ────────────────────────────────────
function F1GaugeCard({ result }) {
  const isCCE = result.controller === "CSA-ACI CCE";
  const f1 = result.f1 ?? 0;
  const recall = result.recall ?? 0;
  const quietTrace = f1 === 0 && recall === 0;
  const color = quietTrace ? "#5b6391" : f1Color(f1);

  return (
    <Card className={isCCE ? "ring-1 ring-cyan/30" : ""}>
      <div className="flex items-start justify-between gap-1 mb-1">
        <div>
          <div className="text-[12px] font-bold leading-tight" style={{ color: isCCE ? "#00e5ff" : "#eaeeff" }}>
            {isCCE ? "★ " : ""}{result.controller}
          </div>
          <div className="text-[10px] text-muted leading-tight">{result.description ?? result.signal ?? ""}</div>
        </div>
      </div>

      {quietTrace ? (
        <div className="my-3 flex flex-col items-center gap-1 rounded-lg py-4"
          style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
          <div className="text-2xl font-extrabold text-faint">N/A</div>
          <div className="text-[10px] text-faint text-center px-2 leading-relaxed">
            Quiet trace — rolling-median latency never crossed 100ms.
            No scale-up events to recall.
          </div>
        </div>
      ) : (
        <div className="relative" style={{ height: 90 }}>
          <ResponsiveContainer width="100%" height={90}>
            <RadialBarChart cx="50%" cy="90%" innerRadius="70%" outerRadius="100%"
              startAngle={180} endAngle={0} data={[{ value: f1 * 100, fill: color }]}>
              <RadialBar dataKey="value" cornerRadius={4}
                background={{ fill: "rgba(255,255,255,0.06)" }} isAnimationActive={false}>
                <Cell fill={color} />
              </RadialBar>
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute bottom-0 inset-x-0 flex flex-col items-center">
            <div className="text-2xl font-extrabold leading-none" style={{ color }}>{f1}</div>
            <div className="text-[9px] uppercase tracking-widest text-faint">F1 Score</div>
          </div>
        </div>
      )}

      <div className="mt-2.5 grid grid-cols-3 gap-1 border-t border-white/10 pt-2.5">
        {[
          ["FP", result.false_positives ?? "—", (result.false_positives ?? 0) === 0 ? "#00ff99" : "#ff4444", "False positives — SCALE_UP when not needed"],
          ["Recall", result.recall ?? "—", "#00e5ff", "Fraction of genuine scale-up events detected"],
          ["Switch", result.intent_switches ?? "—", "#ffd740", "Total intent changes — lower = more stable"],
        ].map(([label, val, color, tip]) => (
          <div key={label} className="text-center" title={tip}>
            <div className="text-base font-extrabold" style={{ color }}>{val}</div>
            <div className="text-[9px] text-faint uppercase tracking-wide">{label}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Trace replay: Comparison bars ────────────────────────────
function ReplayBars({ results }) {
  const hasRecall = results.some((r) => (r.recall ?? 0) > 0);
  const data = results.map((r) => ({
    name: r.controller.replace("Reactive", "Rx").replace("Controller", "Ctrl")
      .replace("Kubernetes HPA", "K8s HPA").replace("Multi-Metric", "MM")
      .replace("Multi-Signal", "MS").replace("CSA-ACI CCE", "★ CCE"),
    F1: r.f1 ?? 0,
    Recall: r.recall ?? 0,
    FP: r.false_positives ?? 0,
  }));

  return (
    <Card>
      <PanelLabel className="mb-1">Performance Comparison — all controllers on identical trace</PanelLabel>

      {!hasRecall && (
        <div className="my-3 rounded-lg border border-warn/25 bg-warn/5 px-3 py-2.5 text-[11px] text-muted">
          <span className="font-semibold text-warn">Quiet trace result: </span>
          Rolling-median ground truth never exceeded 100ms on this dataset — no genuine scale-up events to detect.
          F1 and Recall are 0 for all controllers. <strong className="text-ink">False positives still differentiate</strong>:
          controllers that noise-chase make unnecessary SCALE_UP decisions; CCE's evidence gate suppresses these.
        </div>
      )}

      {hasRecall && (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 36 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="name" stroke="#1a1f35" tick={{ fill: "#8b95c9", fontSize: 11 }} angle={-28} textAnchor="end" interval={0} />
            <YAxis stroke="#1a1f35" tick={{ fill: "#5b6391", fontSize: 10 }} domain={[0, 1]} />
            <Tooltip {...TT} />
            <Bar dataKey="F1" fill="#00ff99" radius={[3, 3, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="Recall" fill="#00e5ff" radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      )}

      <div className={hasRecall ? "mt-3 border-t border-white/10 pt-3" : ""}>
        <div className="mb-2 flex items-center justify-between">
          <div className="text-[10px] uppercase tracking-wider text-faint">
            False Positives <span className="normal-case text-faint">— unnecessary SCALE_UP decisions (lower = better)</span>
          </div>
        </div>
        {[...results].sort((a, b) => (a.false_positives ?? 0) - (b.false_positives ?? 0)).map((r) => {
          const isCCE = r.controller === "CSA-ACI CCE";
          const fp = r.false_positives ?? 0;
          const maxFp = Math.max(...results.map((x) => x.false_positives ?? 0), 1);
          const color = fp === 0 ? "#00ff99" : fp <= 5 ? "#ffd740" : "#ff4444";
          const short = r.controller.replace("Reactive", "Rx").replace("Controller", "Ctrl")
            .replace("Kubernetes HPA", "K8s HPA").replace("Multi-Metric", "MM")
            .replace("Multi-Signal", "MS").replace("CSA-ACI CCE", "★ CCE");
          return (
            <div key={r.controller} className="mb-1.5 flex items-center gap-2">
              <div className="w-24 shrink-0 text-[11px]" style={{ color: isCCE ? "#00e5ff" : "#8b95c9" }}>{short}</div>
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                <div className="h-full rounded-full" style={{ width: `${(fp / maxFp) * 100}%`, background: color }} />
              </div>
              <div className="w-5 text-right text-[11px] font-bold tabular-nums" style={{ color }}>{fp}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ── Page ─────────────────────────────────────────────────────
export default function ControllerCharts() {
  const { conflictResult, replayResult } = useDashboard();

  return (
    <div className="flex flex-col gap-stack-lg max-w-5xl mx-auto">

      {/* ══ Conflict section ══ */}
      <div>
        <div className="mb-1 text-base font-extrabold text-cyan">Multi-Signal Conflict — Controller Profiles</div>
        <div className="mb-3 text-[11px] text-muted">
          8 controllers run on identical two-signal telemetry (CPU + latency) across 4 sustained regimes.
          Two regimes are conflicts where the signals disagree — only multi-signal controllers handle them.
        </div>

        {!conflictResult ? (
          <EmptyState hint="Go to Experiments → Run Conflict Experiment, then return here." />
        ) : (
          <div className="flex flex-col gap-stack">
            <RegimeLegend regimes={conflictResult.regimes ?? []} conflictRegimes={conflictResult.analysis?.conflict_regimes} />
            <ConflictInsight conflictResult={conflictResult} />
            <CapabilityMatrix results={conflictResult.results} conflictRegimes={conflictResult.analysis?.conflict_regimes} total={conflictResult.analysis?.total_regimes ?? 4} />
            <div className="grid gap-stack lg:grid-cols-[1fr_2fr]">
              <InterventionRank results={conflictResult.results} total={conflictResult.analysis?.total_regimes ?? 4} />
              <div className="grid grid-cols-2 gap-stack sm:grid-cols-3">
                {conflictResult.results.map((r) => (
                  <ConflictCard key={r.controller} result={r} conflictRegimes={conflictResult.analysis?.conflict_regimes} total={conflictResult.analysis?.total_regimes ?? 4} />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ══ Trace replay section ══ */}
      <div>
        <div className="mb-1 text-base font-extrabold text-cyan">Real-Trace Replay — Controller Breakdown</div>
        <div className="mb-3 text-[11px] text-muted">
          All controllers run on an identical real production trace. Ground truth = rolling-median latency ≥ 100ms.
          False positives = unnecessary scale-up decisions (noise-chasing).
        </div>

        {!replayResult ? (
          <EmptyState hint="Go to Experiments → Real-Trace Replay, select a dataset, and run it." />
        ) : (
          <div className="flex flex-col gap-stack">
            <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted">
              <span>Dataset: <span className="font-semibold text-ink">{replayResult.label}</span></span>
              <span className="text-white/20">·</span>
              <span>{replayResult.telemetry_steps} steps</span>
              <span className="text-white/20">·</span>
              <span className={`font-semibold ${replayResult.source === "real" ? "text-good" : "text-bad"}`}>
                {replayResult.source === "real" ? "● Real data" : "▲ Synthetic fallback — not paper-valid"}
              </span>
            </div>

            <ReplayBars results={replayResult.results} />

            <div className="grid grid-cols-2 gap-stack sm:grid-cols-3 lg:grid-cols-4">
              {replayResult.results.map((r) => (
                <F1GaugeCard key={r.controller} result={r} />
              ))}
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
