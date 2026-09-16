"use client";

import Link from "next/link";
import { useMemo } from "react";

import { ApprovalDetailPanel } from "@/components/console/approval-detail";
import { ApprovalQueue } from "@/components/console/approval-queue";
import { ConsoleStats } from "@/components/console/console-stats";
import { ResetDemoButton } from "@/components/console/reset-demo-button";
import { LiveDot } from "@/components/ui/pill";
import { useApprovalQueue } from "@/hooks/use-approvals";
import { useNow } from "@/hooks/use-now";
import { computeMetrics } from "@/lib/console-metrics";

export function SupportConsole() {
  const queue = useApprovalQueue();
  const { pending, history } = queue;
  const now = useNow();
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
            <Link
              href="/"
              className="rounded-full border border-sand-300 px-3 py-1.5 text-xs text-ink-700 transition-colors hover:border-tide-600 hover:text-tide-700"
            >
              Open customer site
            </Link>
          </div>
        </div>
      </header>

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
            detail={queue.detail}
            loading={queue.detailLoading}
            deciding={queue.deciding}
            lastDecision={queue.lastDecision}
            onDecide={queue.decide}
          />
        </div>
      </div>
    </div>
  );
}
