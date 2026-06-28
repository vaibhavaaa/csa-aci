import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useDashboard } from "@/context/DashboardContext";
import { LayoutDashboard, Radio, FlaskConical, Beaker } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/overview",     label: "Overview",     icon: LayoutDashboard, sub: "Governance health · all-time telemetry" },
  { to: "/live",         label: "Live Control",  icon: Radio,           sub: "Fire single CCE decisions" },
  { to: "/simulation",   label: "Simulation",    icon: FlaskConical,    sub: "Run a multi-step scenario" },
  { to: "/experiments",  label: "Experiments",   icon: Beaker,          sub: "Ablation · comparison · paper §5" },
];

function Aurora() {
  return (
    <div className="aurora" aria-hidden="true">
      <div className="blob b1" />
      <div className="blob b2" />
      <div className="blob b3" />
    </div>
  );
}

export default function AppLayout() {
  const { connected, onLogout } = useDashboard();
  const { pathname } = useLocation();

  return (
    <div className="relative min-h-screen text-ink">
      <Aurora />

      <div className="relative z-10 flex min-h-screen">
        {/* ── sidebar ─────────────────────────────────────────── */}
        <aside className="fixed inset-y-0 left-0 z-30 flex w-56 flex-col border-r border-white/8 bg-bg/70 backdrop-blur-xl">
          {/* brand */}
          <div className="flex items-center gap-3 px-5 py-5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-cyan/15 text-cyan ring-1 ring-cyan/30">
              <span className="font-mono text-sm font-bold">C</span>
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold tracking-tight text-ink">CSA-ACI</span>
              <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-faint">
                Cognitive Arbiter
              </span>
            </div>
          </div>

          {/* nav */}
          <nav className="flex flex-1 flex-col gap-0.5 px-3 py-2">
            <p className="px-3 pb-2 pt-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-faint/70">
              Console
            </p>
            {NAV.map(({ to, label, icon: Icon, sub }) => {
              const isActive = pathname.startsWith(to);
              return (
                <NavLink
                  key={to}
                  to={to}
                  className={cn(
                    "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
                    isActive
                      ? "bg-white/[0.07] text-ink"
                      : "text-muted hover:bg-white/[0.04] hover:text-ink"
                  )}
                >
                  {isActive && (
                    <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-cyan" />
                  )}
                  <Icon
                    size={15}
                    className={cn("shrink-0 transition-colors", isActive ? "text-cyan" : "text-muted group-hover:text-ink")}
                  />
                  <div className="flex flex-col">
                    <span className="font-medium leading-tight">{label}</span>
                    <span className="text-[10px] leading-tight text-faint/60">{sub}</span>
                  </div>
                </NavLink>
              );
            })}
          </nav>

          {/* live status + logout */}
          <div className="border-t border-white/8 px-4 py-4">
            <div className="flex items-center gap-2 rounded-lg bg-good/10 px-3 py-2 ring-1 ring-good/20">
              <span className="relative flex h-2 w-2 shrink-0">
                {connected && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-good opacity-60" />
                )}
                <span
                  className="relative inline-flex h-2 w-2 rounded-full"
                  style={{ background: connected ? "#00ff99" : "#5b6391" }}
                />
              </span>
              <span className="text-xs font-medium" style={{ color: connected ? "#00ff99" : "#5b6391" }}>
                {connected ? "Live" : "Offline"}
              </span>
              <span className="ml-auto font-mono text-[9px] uppercase tracking-wider text-faint/50">CCE</span>
            </div>
          </div>
        </aside>

        {/* ── main ────────────────────────────────────────────── */}
        <main className="ml-56 flex h-screen flex-1 flex-col overflow-y-auto">
          {/* sticky page header */}
          <header className="sticky top-0 z-20 flex items-center justify-between border-b border-white/8 bg-bg/70 px-shell py-3 backdrop-blur-xl">
            <div>
              {(() => {
                const active = NAV.find((n) => pathname.startsWith(n.to)) ?? NAV[0];
                return (
                  <>
                    <h1 className="text-base font-bold tracking-tight">{active.label}</h1>
                    <div className="text-[10px] text-faint">{active.sub}</div>
                  </>
                );
              })()}
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 rounded-full border px-3 py-1.5"
                style={{ borderColor: connected ? "rgba(0,255,153,0.25)" : "rgba(91,99,145,0.3)", background: connected ? "rgba(0,255,153,0.08)" : "transparent" }}>
                <span className="relative flex h-1.5 w-1.5 shrink-0">
                  {connected && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-good opacity-60" />}
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full" style={{ background: connected ? "#00ff99" : "#5b6391" }} />
                </span>
                <span className="text-[11px] font-medium" style={{ color: connected ? "#00ff99" : "#5b6391" }}>
                  {connected ? "WebSocket Live" : "Disconnected"}
                </span>
              </div>
              {onLogout && (
                <button onClick={onLogout}
                  className="rounded-md border border-white/10 px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-white/[0.06] hover:text-ink">
                  Logout
                </button>
              )}
            </div>
          </header>

          <div className="px-shell py-shell-y">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
