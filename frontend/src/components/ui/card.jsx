import { cn } from "@/lib/utils";

// Glass panel — the base surface for every section.
export function Card({ className, accent, ...props }) {
  return (
    <div
      className={cn("glass rounded-xl p-[clamp(0.5rem,0.75vw,0.75rem)]", className)}
      style={accent ? { borderColor: accent + "55" } : undefined}
      {...props}
    />
  );
}

// Eyebrow label with a gradient accent bar — the standard panel header.
export function PanelLabel({ className, children }) {
  return (
    <div className={cn("flex items-center gap-2.5 label-eyebrow", className)}>
      <span className="h-3.5 w-1 rounded-full bg-gradient-to-b from-cyan to-violet" />
      <span>{children}</span>
    </div>
  );
}
