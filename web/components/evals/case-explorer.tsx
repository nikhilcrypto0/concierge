"use client";

import { useMemo, useState } from "react";

import { Pill } from "@/components/ui/pill";
import {
  CATEGORIES,
  EVAL_DATA,
  type CaseResult,
  type EvalCase,
  type ModelKey,
  type RunSummary,
} from "@/lib/eval-data";

const PROMPT_PREVIEW_CHARS = 140;

type Filter ="all" | "missed" | (typeof CATEGORIES)[number];

const FILTER_LABELS: Record<Filter, string> = {
  all: "All",
  missed: "Missed by a model",
  safety: "Safety",
  refund: "Refunds",
  booking: "Bookings",
  routing: "Routing",
  question: "Questions",
};

function missedByAny(testCase: EvalCase): boolean {
  return Object.values(testCase.results).some((result) => !result.passed);
}

function matches(testCase: EvalCase, filter: Filter): boolean {
  if (filter === "all") return true;
  if (filter === "missed") return missedByAny(testCase);
  return testCase.category === filter;
}

function ResultLine({ run, result }: { run: RunSummary; result: CaseResult }) {
  return (
    <li className="rounded-xl bg-sand-100 p-3 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-ink-900">{run.label}</span>
        <Pill tone={result.passed ? "moss" : "rose"}>{result.passed ? "passed" : "missed"}</Pill>
        <span className="text-ink-500">
          outcome <code className="font-mono text-ink-900">{result.outcome}</code>
        </span>
      </p>
      {result.failures.length > 0 && (
        <p className="mt-1 text-ink-700">Why it counted as missed: {result.failures.join("; ")}</p>
      )}
      {result.replyExcerpt && (
        <p className="mt-1 text-ink-700">Reply: “{result.replyExcerpt}”</p>
      )}
    </li>
  );
}

function Expected({ testCase }: { testCase: EvalCase }) {
  const { expect } = testCase;
  return (
    <ul className="list-disc space-y-1 pl-5 text-sm text-ink-700">
      <li>
        Outcome must be one of:{" "}
        {expect.outcomes.map((outcome) => (
          <code key={outcome} className="mr-1.5 font-mono text-ink-900">
            {outcome}
          </code>
        ))}
      </li>
      {expect.noApprovalRequest && <li>No refund request may be opened</li>}
      {expect.approvalAmountCents !== null && (
        <li>The proposed refund must be exactly ${(expect.approvalAmountCents / 100).toFixed(2)}</li>
      )}
      {expect.replyMustNotContain.length > 0 && (
        <li>The reply must not contain: {expect.replyMustNotContain.join(", ")}</li>
      )}
    </ul>
  );
}

function CaseRow({ testCase, runs }: { testCase: EvalCase; runs: RunSummary[] }) {
  const last = testCase.turns[testCase.turns.length - 1];
  const prompt = last.length > PROMPT_PREVIEW_CHARS ? `${last.slice(0, PROMPT_PREVIEW_CHARS)}…` : last;
  return (
    <li>
      <details className="group rounded-2xl border border-sand-200 bg-white open:shadow-sm">
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-2 p-4">
          <code className="font-mono text-xs text-ink-500">{testCase.id}</code>
          <span className="min-w-0 flex-1 basis-64 truncate text-sm text-ink-900">{prompt}</span>
          <span className="flex gap-1.5">
            {runs.map((run) => (
              <Pill key={run.key} tone={testCase.results[run.key].passed ? "moss" : "rose"}>
                {run.key === "opus" ? "Opus" : "Haiku"} {testCase.results[run.key].passed ? "✓" : "✗"}
              </Pill>
            ))}
          </span>
        </summary>
        <div className="space-y-4 border-t border-sand-200 p-4">
          <div>
            <h4 className="text-xs font-semibold tracking-wide text-ink-500 uppercase">
              {testCase.turns.length > 1 ? "The customer's messages, in order" : "What the customer said"}
            </h4>
            <ol className="mt-1 space-y-1 text-sm text-ink-900">
              {testCase.turns.map((turn, index) => (
                <li key={`${index}-${turn.slice(0, 12)}`} className="rounded-lg bg-sand-100 px-3 py-2">
                  {turn.length > 400 ? `${turn.slice(0, 400)}…` : turn}
                </li>
              ))}
            </ol>
          </div>
          <div>
            <h4 className="text-xs font-semibold tracking-wide text-ink-500 uppercase">
              What counts as correct
            </h4>
            <div className="mt-1">
              <Expected testCase={testCase} />
            </div>
          </div>
          <ul className="grid gap-2 md:grid-cols-2">
            {runs.map((run) => (
              <ResultLine key={run.key} run={run} result={testCase.results[run.key as ModelKey]} />
            ))}
          </ul>
        </div>
      </details>
    </li>
  );
}

export function CaseExplorer() {
  const [filter, setFilter] = useState<Filter>("all");
  const { cases, runs } = EVAL_DATA;
  const shown = useMemo(() => cases.filter((c) => matches(c, filter)), [cases, filter]);
  const filters = Object.keys(FILTER_LABELS) as Filter[];

  return (
    <section aria-labelledby="cases-heading" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id="cases-heading" className="font-display text-2xl text-ink-950">
          Every test case
        </h2>
        <p className="text-sm text-ink-500">
          Showing {shown.length} of {cases.length}
        </p>
      </div>
      <div role="group" aria-label="Filter cases" className="flex flex-wrap gap-2">
        {filters.map((name) => (
          <button
            key={name}
            type="button"
            aria-pressed={filter === name}
            onClick={() => setFilter(name)}
            className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
              filter === name
                ? "border-ink-950 bg-ink-950 text-sand-50"
                : "border-sand-300 text-ink-700 hover:border-ink-900"
            }`}
          >
            {FILTER_LABELS[name]}
          </button>
        ))}
      </div>
      <ul className="space-y-2">
        {shown.map((testCase) => (
          <CaseRow key={testCase.id} testCase={testCase} runs={runs} />
        ))}
      </ul>
    </section>
  );
}
