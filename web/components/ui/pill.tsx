import type { ReactNode } from "react";

export type PillTone = "sand" | "tide" | "amber" | "moss" | "rose" | "ink";

const TONES: Record<PillTone, string> = {
  sand: "bg-sand-200 text-ink-700 ring-sand-300",
  tide: "bg-tide-50 text-tide-700 ring-tide-100",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  moss: "bg-moss-50 text-moss-700 ring-moss-200",
  rose: "bg-rose-50 text-rose-700 ring-rose-200",
  ink: "bg-ink-900 text-sand-50 ring-ink-900",
};

interface PillProps {
  tone?: PillTone;
  children: ReactNode;
  className?: string;
}

export function Pill({ tone = "sand", children, className = "" }: PillProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

export function LiveDot({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-ink-500">
      <span className="relative inline-flex size-2 text-tide-600">
        <span className="live-pulse absolute inset-0 rounded-full" />
        <span className="relative size-2 rounded-full bg-tide-600" />
      </span>
      {label}
    </span>
  );
}
