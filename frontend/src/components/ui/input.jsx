import { cn } from "@/lib/utils";

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "glass-inset w-full rounded-lg px-3 py-2 font-mono text-sm text-ink outline-none transition-colors placeholder:text-faint focus:border-cyan/50",
        className,
      )}
      {...props}
    />
  );
}

export function Field({ label, className, children }) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label className="text-[10px] uppercase tracking-wider text-faint">{label}</label>
      {children}
    </div>
  );
}
