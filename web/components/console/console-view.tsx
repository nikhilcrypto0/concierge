"use client";

import Link from "next/link";
import { useMemo } from "react";

import { ApprovalDetailPanel } from "@/components/console/approval-detail";
import { ApprovalQueue } from "@/components/console/approval-queue";
import { ConsoleStats } from "@/components/console/console-stats";
import { ResetDemoButton } from "@/components/console/reset-demo-button";
import { LiveDot } from "@/components/ui/pill";
import type { ApprovalQueueController } from "@/hooks/use-approvals";
import { computeMetrics } from "@/lib/console-metrics";

interface ConsoleViewProps {
  queue: ApprovalQueueController;
  now: number;
  /** The public tour: made-up rows, no buttons, no reset, no live indicator. */
  sample?: boolean;
}

/** The support console's display. Where its rows come from is the caller's business. */
export function ConsoleView({ queue, now, sample = false }: ConsoleViewProps) {
  const { pending, history } = queue;
  const metrics = useMemo(() => computeMetrics(pending, history, now), [pending, history, now]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-sand-100">
      <header className="border-b border-sand-200 bg-sand-50">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <span
              aria-hidden
              className="grid size-10 place-items-center rounded-xl bg-ink-950 font-mono text-sm text-sand-50"
            >
              TW
            </span>
            <div>
              <p className="text-[11px] font-semibold tracking-[0.12em] text-ink-500 uppercase">
                Tidewell operations
              </p>
              <h1 className="font-display text-xl leading-tight text-ink-950">Refund approvals</h1>
            </div>
          </div>

          <div className="ml-auto flex flex-wrap items-center gap-4">
            {sample ? (
              <>
                <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-900">
                  Sample data, view only
                </span>
                <Link
                  href="/console"
                  className="rounded-full border border-sand-300 px-3 py-1.5 text-xs text-ink-700 transition-colors hover:border-tide-600 hover:text-tide-700"
                >
                  Operator sign in
                </Link>
              </>
            ) : (
              <>
                <LiveDot label="Live, refreshed every 4s" />
                <span className="flex items-center gap-2 text-xs text-ink-500">
                  <span
                    aria-hidden
                    className="grid size-6 place-items-center rounded-full bg-tide-600 text-[10px] font-semibold text-white"
                  >
                    SL
                  </span>
                  Signed in as <span className="font-medium text-ink-900">support-lead</span>
                </span>
                <ResetDemoButton onReset={queue.resetDemo} resetting={queue.resetting} />
              </>
            )}
            <Link
              href="/"
              className="rounded-full border border-sand-300 px-3 py-1.5 text-xs text-ink-700 transition-colors hover:border-tide-600 hover:text-tide-700"
            >
              Open customer site
            </Link>
          </div>
        </div>
      </header>

      {sample && (
        <p className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 sm:px-6">
          This is a tour with made-up requests. Nothing here is live, no customer data is shown, and
          nothing can be approved. To decide a real request, send a refund request on the customer
          site and play the support lead there.
        </p>
      )}

      {queue.error && (
        <p role="status" className="bg-rose-50 px-6 py-2 text-sm text-rose-700">
          {queue.error}
        </p>
      )}

      <div className="mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6">
        <ConsoleStats metrics={metrics} />
      </div>

      <div className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 gap-5 px-4 py-6 sm:px-6 lg:grid-cols-[340px_1fr]">
        <ApprovalQueue
          pending={pending}
          history={history}
          selectedId={queue.selectedId}
          onSelect={queue.select}
          now={now}
        />
        <div className="min-h-[520px]">
          <ApprovalDetailPanel
            // A fresh panel per request, so a typed amount never carries over to another one.
            key={queue.detail?.approval.id ?? "none"}
            detail={queue.detail}
            loading={queue.detailLoading}
            deciding={queue.deciding}
            lastDecision={queue.lastDecision}
            onDecide={queue.decide}
            readOnly={sample}
          />
        </div>
      </div>
    </div>
  );
}
