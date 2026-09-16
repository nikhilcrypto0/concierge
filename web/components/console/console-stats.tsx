"use client";

import {
  SLA_MINUTES,
  formatCents,
  formatDuration,
  type ConsoleMetrics,
} from "@/lib/console-metrics";

interface FigureProps {
  label: string;
  value: string;
  hint: string;
  emphasis?: boolean;
  alert?: boolean;
}

function Figure({ label, value, hint, emphasis = false, alert = false }: FigureProps) {
  return (
    <div className="bg-sand-50 px-5 py-4">
      <p className="text-[11px] font-semibold tracking-[0.12em] text-ink-500 uppercase">{label}</p>
      <p
        className={`mt-2 font-mono leading-none tabular-nums ${
          emphasis ? "text-4xl" : "text-2xl"
        } ${alert ? "text-rose-700" : "text-ink-950"}`}
      >
        {value}
      </p>
      <p className={`mt-2 text-xs ${alert ? "font-medium text-rose-700" : "text-ink-500"}`}>
        {hint}
      </p>
    </div>
  );
}

export function ConsoleStats({ metrics }: { metrics: ConsoleMetrics }) {
  const decisions = metrics.approvedTotal + metrics.rejectedTotal;
  const approvalRate =
    decisions > 0 ? `${Math.round((metrics.approvedTotal / decisions) * 100)}% approved` : "—";

  return (
    <section
      aria-label="Queue health"
      className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-sand-200 bg-sand-200 shadow-[0_18px_40px_-34px_rgba(11,33,36,0.6)] sm:grid-cols-3 lg:grid-cols-5"
    >
      <Figure
        label="Waiting now"
        value={String(metrics.waiting)}
        hint={metrics.waiting === 0 ? "queue clear" : "needs a human decision"}
        emphasis
        alert={metrics.breaching}
      />
      <Figure
        label="Oldest wait"
        value={formatDuration(metrics.oldestWaitMs)}
        hint={metrics.breaching ? `past the ${SLA_MINUTES}m target` : `target ${SLA_MINUTES}m`}
        alert={metrics.breaching}
      />
      <Figure
        label="Decided today"
        value={String(metrics.decidedToday)}
        hint={`${decisions} all time`}
      />
      <Figure
        label="Median decision"
        value={formatDuration(metrics.medianDecisionMs)}
        hint="request to decision"
      />
      <Figure
        label="Refunded"
        value={formatCents(metrics.refundedCents)}
        hint={approvalRate}
      />
    </section>
  );
}
