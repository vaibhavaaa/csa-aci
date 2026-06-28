import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// shadcn-style className combiner: merges conditional classes and
// dedupes conflicting Tailwind utilities (last one wins).
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
