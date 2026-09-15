"use client";

import Link from "next/link";

import { ApprovalDetailPanel } from "@/components/console/approval-detail";
import { ApprovalQueue } from "@/components/console/approval-queue";
import { ResetDemoButton } from "@/components/console/reset-demo-button";
import { LiveDot } from "@/components/ui/pill";
import { useApprovalQueue } from "@/hooks/use-approvals";

export function SupportConsole() {
  const queue = useApprovalQueue();

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-sand-100">
      <header className="border-b border-sand-200 bg-sand-50">
        <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-4 sm:px-6">
          <div>
            <h1 className="font-display text-xl text-ink-950">Refund approvals</h1>
            <p className="text-sm text-ink-500">
              Tidewell support · every refund the assistant proposes stops here
            </p>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-4">
            <LiveDot label="Live, refreshed every 4s" />
            <span className="text-xs text-ink-500">
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

      <div className="mx-auto grid w-full max-w-7xl flex-1 grid-cols-1 gap-5 px-4 py-6 sm:px-6 lg:grid-cols-[320px_1fr]">
        <ApprovalQueue
          pending={queue.pending}
          history={queue.history}
          selectedId={queue.selectedId}
          onSelect={queue.select}
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
