import { Trophy } from "lucide-react";
import { useDashboard } from "@/context/DashboardContext";
import { Card, PanelLabel } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import ResearchPanels from "@/components/ResearchPanels";
import { csiColor } from "@/lib/constants";

// ─── shared table header style ────────────────────────────────────────────────

const thCls = "px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-[0.12em] text-faint";
const ELEV  = { background: "rgba(20,20,32,0.7)" };

// ─── Ablation bars — horizontal, winner highlighted ───────────────────────────

function AblationBars({ ablation }) {
  const maxSwitches = Math.max(...ablation.ablation.map((x) => x.intent_switch_count));
  return (
    <div className="flex flex-col gap-4">
      {ablation.ablation.map((r) => {
        const pct      = (r.intent_switch_count / maxSwitches) * 100;
        const isWinner = r.config === ablation.winner;
        const barColor = isWinner ? "#ffd740" : pct > 70 ? "#ff4444" : pct > 40 ? "#ff9800" : "#00ff99";
        return (
          <div key={r.config} className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <span className={cn("flex items-center gap-1.5 text-sm font-medium",
                isWinner ? "text-warn" : "text-ink")}>
                {isWinner && <Trophy size={13} className="text-warn" />}
                {r.config}
              </span>
              <span className={cn("font-mono text-sm tabular-nums", isWinner ? "text-warn" : "text-muted")}>
                CSI {r.csi}
              </span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: barColor }} />
            </div>
            <p className="text-[11px] text-faint">{r.description}</p>
          </div>
        );
      })}
    </div>
  );
}

// ─── Ablation table — compact, auto-width ────────────────────────────────────

function AblationTable({ ablation }) {
  const cols = [
    { key: "config",             label: "Config",      align: "left"  },
    { key: "intent_switch_count",label: "Switches",    align: "right" },
    { key: "intent_switch_rate", label: "Switch Rate", align: "right" },
    { key: "conflict_count",     label: "Conflicts",   align: "right" },
    { key: "avg_trust",          label: "Avg Trust",   align: "right" },
    { key: "csi",                label: "CSI",         align: "right" },
  ];
  return (
    <div className="inline-block overflow-hidden rounded-lg border border-white/10">
      <table className="w-auto border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-white/10" style={ELEV}>
            {cols.map((c) => (
              <th key={c.key} className={cn(thCls, c.align === "right" && "text-right")}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ablation.ablation.map((r) => {
            const isWinner = r.config === ablation.winner;
            return (
              <tr key={r.config}
                className="border-b border-white/5 last:border-0 transition-colors hover:bg-white/[0.025]"
                style={{ background: isWinner ? "rgba(255,215,64,0.06)" : "transparent" }}>
                <td className="whitespace-nowrap px-4 py-2.5 text-sm"
                  style={{ color: isWinner ? "#ffd740" : "#eaeeff" }}>
                  {isWinner ? "★ " : ""}{r.config}
                </td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums text-bad">{r.intent_switch_count}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums text-orange">{r.intent_switch_rate}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums text-faint">{r.conflict_count}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums text-good">{r.avg_trust}</td>
                <td className="px-4 py-2.5 text-right font-mono tabular-nums font-bold"
                  style={{ color: csiColor(r.csi) }}>{r.csi}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Ablation card — Split variant: bars | table side-by-side ────────────────

function AblationCard({ ablation }) {
  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <PanelLabel>Ablation Study — 100 Steps, Noisy Telemetry (σ=20ms)</PanelLabel>
        <span className="text-[11px] text-muted">
          Winner: <span className="font-bold text-warn">{ablation.winner}</span>
        </span>
      </div>

      {/* split: bars left, table right */}
      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <AblationBars ablation={ablation} />
        <div className="overflow-x-auto">
          <AblationTable ablation={ablation} />
        </div>
      </div>
    </Card>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Experiments() {
  const { runAblation, ablationRunning, ablation, token, API } = useDashboard();
  return (
    <div className="flex flex-col gap-stack">
      <Card className="flex flex-wrap items-center gap-4">
        <Button variant="warn" onClick={runAblation} disabled={ablationRunning}>
          {ablationRunning ? "Running…" : "⚗ Run Ablation Study"}
        </Button>
        <span className="text-xs text-muted">
          Strips the evidence gate and dwell time to isolate each component's contribution.
        </span>
      </Card>

      {ablation && <AblationCard ablation={ablation} />}

      <ResearchPanels token={token} API={API} />
    </div>
  );
}
