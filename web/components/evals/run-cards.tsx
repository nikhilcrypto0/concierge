import { Pill } from "@/components/ui/pill";
import type { RunSummary } from "@/lib/eval-data";

function Figure({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <dd className="font-mono text-2xl text-ink-950">{value}</dd>
      <dt className="mt-0.5 text-xs leading-snug text-ink-500">{label}</dt>
    </div>
  );
}

function RunCard({ run, baseline }: { run: RunSummary; baseline: boolean }) {
  return (
    <article className="rounded-2xl border border-sand-200 bg-white p-5">
      <header className="flex items-center justify-between gap-3">
        <h3 className="font-display text-xl text-ink-950">{run.label}</h3>
        <Pill tone={baseline ? "tide" : "sand"}>{baseline ? "shipped model" : "comparison"}</Pill>
      </header>
      <dl className="mt-4 grid grid-cols-2 gap-4">
        <Figure value={`${run.passed} of ${run.cases}`} label="cases passed" />
        <Figure value={`${run.safetyPassed} of ${run.safetyCases}`} label="safety cases passed" />
        <Figure value={String(run.refundsWithoutHuman)} label="refunds paid without a person" />
        <Figure value={`$${run.usdPerConversation}`} label="cost per conversation" />
        <Figure value={`${(run.p50Ms / 1000).toFixed(1)} s`} label="median turn time" />
        <Figure value={`${(run.p95Ms / 1000).toFixed(1)} s`} label="slowest-case turn time (p95)" />
      </dl>
    </article>
  );
}

export function RunCards({ runs }: { runs: RunSummary[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {runs.map((run, index) => (
        <RunCard key={run.key} run={run} baseline={index === 0} />
      ))}
    </div>
  );
}
