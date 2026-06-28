import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-xl font-semibold whitespace-nowrap transition-all duration-150 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed",
  {
    variants: {
      variant: {
        default: "glass text-ink hover:border-white/25 hover:bg-white/[0.08]",
        primary:
          "bg-gradient-to-br from-cyan to-violet text-[#06060f] shadow-[0_6px_24px_rgba(0,229,255,0.22)] hover:brightness-110",
        good: "border border-good/40 bg-good/10 text-good hover:bg-good/20",
        warn: "border border-warn/40 bg-warn/10 text-warn hover:bg-warn/20",
        cyan: "border border-cyan/40 bg-cyan/10 text-cyan hover:bg-cyan/20",
        danger: "border border-bad/30 bg-transparent text-bad hover:bg-bad/10",
        ghost: "text-muted hover:text-ink hover:bg-white/5",
      },
      size: {
        sm: "h-9 px-4 text-xs",
        md: "h-10 px-5 text-sm",
        lg: "h-11 px-7 text-sm",
      },
    },
    defaultVariants: { variant: "default", size: "md" },
  },
);

export function Button({ className, variant, size, ...props }) {
  return (
    <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
