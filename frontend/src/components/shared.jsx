import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { intentColor } from "@/lib/constants";
import { cn } from "@/lib/utils";

// ── KPI tile (v0 style) — bordered/elevated, mono number ──────────────
const TONE_HEX = {
  cyan: "#00e5ff", good: "#00ff99", warn: "#ffd740",
  orange: "#ff9800", bad: "#ff4444", neutral: "#eaeeff",
};

export function KpiTile({ label, value, hint, tone = "neutral", color }) {
  const c = color ?? TONE_HEX[tone] ?? TONE_HEX.neutral;
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-white/8 bg-white/[0.025] p-[clamp(0.75rem,1vw,1.25rem)]">
      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">{label}</span>
      <span className="font-mono text-3xl font-bold leading-none tabular-nums" style={{ color: c }}>
        {value ?? "—"}
      </span>
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </div>
  );
}

// Legacy glass KPI tile (kept for callers that pass sub).
export function StatCard({ label, value, color = "#00e5ff", sub, className }) {
  return (
    <Card className={className || ""}>
      <div className="text-[10px] font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-1 font-mono text-2xl font-extrabold leading-none tabular-nums tracking-tight" style={{ color }}>
        {value}
      </div>
      {sub && <div className="mt-1 text-[10px] text-faint">{sub}</div>}
    </Card>
  );
}

// ── Intent badge (data-driven tint) ──────────────────────────────────
export function IntentBadge({ intent }) {
  if (!intent) return <span className="text-faint">—</span>;
  return <Badge tint={intentColor(intent)}>{intent}</Badge>;
}

// ── Decision badge (v0 ring-inset mono) ──────────────────────────────
const DECISION_STYLES = {
  SCALE_UP:   "bg-cyan/10 text-cyan ring-cyan/25",
  SCALE_DOWN: "bg-orange/10 text-orange ring-orange/25",
  HOLD:       "bg-white/5 text-muted ring-white/10",
  EMERGENCY:  "bg-bad/10 text-bad ring-bad/25",
};

export function DecisionBadge({ value, className }) {
  if (!value) return <span className="text-faint">—</span>;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[11px] font-medium ring-1 ring-inset",
        DECISION_STYLES[value] ?? "bg-white/5 text-muted ring-white/10",
        className,
      )}
    >
      {value}
    </span>
  );
}

// ── Trust badge (color-banded numeric) ───────────────────────────────
export function TrustBadge({ trust }) {
  const color = trust >= 0.9 ? "#00ff99" : trust >= 0.75 ? "#ffd740" : "#ff4444";
  return (
    <span className="font-mono text-xs tabular-nums" style={{ color }}>
      {typeof trust === "number" ? trust.toFixed(2) : trust}
    </span>
  );
}

// ── Icon empty-state (v0) ────────────────────────────────────────────
export function EmptyState({ icon: Icon, title, children }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/10 opacity-30">
        {Icon && <Icon size={20} className="text-muted" />}
      </div>
      {title && <p className="text-sm font-medium text-muted">{title}</p>}
      {children && <p className="max-w-sm text-xs text-faint">{children}</p>}
    </div>
  );
}

// ── Intent timeline — one cell per step; bright border = changed ──────
export function IntentTimeline({ trace }) {
  if (!trace.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {trace.map((s, i) => (
        <div
          key={i}
          title={`Step ${s.step}: ${s.final_intent} (${s.reason})`}
          className="h-10 w-10 rounded-md"
          style={{
            background: intentColor(s.final_intent),
            opacity: s.intent_changed ? 1 : 0.45,
            border: s.intent_changed ? "2px solid #fff" : "2px solid transparent",
          }}
        />
      ))}
    </div>
  );
}

export function WsStatus({ connected }) {
  return (
    <div className="flex items-center gap-2 text-xs font-medium" style={{ color: connected ? "#00ff99" : "#ff4444" }}>
      <span
        className="h-2 w-2 rounded-full"
        style={{ background: connected ? "#00ff99" : "#ff4444", boxShadow: connected ? "0 0 8px #00ff99" : "none" }}
      />
      {connected ? "WebSocket Live" : "Disconnected"}
    </div>
  );
}
