import { cn } from "@/lib/utils";

// Data-driven badge: tinted from a hex color (intent / reason colors are
// resolved at runtime, so the tint rides in inline style rather than a class).
export function Badge({ tint = "#00e5ff", className, style, children, ...props }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider",
        className,
      )}
      style={{
        background: tint + "22",
        color: tint,
        border: `1px solid ${tint}55`,
        ...style,
      }}
      {...props}
    >
      {children}
    </span>
  );
}
