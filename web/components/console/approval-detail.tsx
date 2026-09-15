"use client";

import { useState } from "react";

import { Pill } from "@/components/ui/pill";
import { formatDateTime, policyCopy, timeAgo } from "@/lib/format";
import type { ApprovalDetail as Detail, DecisionResult } from "@/lib/types";

interface ApprovalDetailProps {
  detail: Detail | null;
  loading: boolean;
  deciding: boolean;
  lastDecision: DecisionResult | null;
  onDecide: (approve: boolean, note: string) => Promise<void>;
}

function Transcript({ detail }: { detail: Detail }) {
  return (
    <ol className="space-y-3">
      {detail.transcript.map((message, index) => (
        <li
          key={`${index}-${message.role}`}
          className={message.role === "customer" ? "flex justify-end" : "flex justify-start"}
        >
          <div
            className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm ${
              message.role === "customer"
                ? "rounded-br-sm bg-tide-600 text-white"
                : "rounded-bl-sm border border-sand-200 bg-white text-ink-900"
            }`}
          >
            {message.content}
          </div>
        </li>
      ))}
      {detail.transcript.length === 0 && (
        <li className="text-sm text-ink-500">No messages recorded.</li>
      )}
    </ol>
  );
}

function Facts({ detail }: { detail: Detail }) {
  const { approval, booking } = detail;
  const policy = policyCopy(approval.policy_reason);
  return (
    <dl className="grid gap-3 text-sm">
      <div className="flex justify-between gap-4">
        <dt className="text-ink-500">Customer</dt>
        <dd className="text-right text-ink-900">{approval.customer_email ?? "unknown"}</dd>
      </div>
      <div className="flex justify-between gap-4">
        <dt className="text-ink-500">Booking</dt>
        <dd className="text-right">
          <span className="font-mono text-ink-900">{approval.booking_reference}</span>
          {booking && <span className="block text-ink-500">{booking.service}</span>}
        </dd>
      </div>
      {booking && (
        <>
          <div className="flex justify-between gap-4">
            <dt className="text-ink-500">Scheduled</dt>
            <dd className="text-right text-ink-900">{formatDateTime(booking.scheduled_for)}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-ink-500">Paid</dt>
            <dd className="text-right font-mono text-ink-900">{booking.amount}</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-ink-500">Already refunded</dt>
            <dd className="text-right font-mono text-ink-900">{booking.refunded}</dd>
          </div>
        </>
      )}
      <div className="rounded-xl bg-sand-100 p-3">
        <dt className="text-xs font-semibold tracking-wide text-ink-500 uppercase">
          Why this amount
        </dt>
        <dd className="mt-1 text-ink-900">
          <span className="font-mono text-lg">{approval.amount}</span> · {policy.label}
          <p className="mt-1 text-sm text-ink-700">{policy.detail}</p>
          <p className="mt-2 text-xs text-ink-500">
            Calculated by the refund policy in code, not by the AI.
          </p>
        </dd>
      </div>
    </dl>
  );
}

export function ApprovalDetailPanel({
  detail,
  loading,
  deciding,
  lastDecision,
  onDecide,
}: ApprovalDetailProps) {
  const [note, setNote] = useState("");

  if (loading && !detail) {
    return <div className="h-full animate-pulse rounded-2xl bg-sand-200/60" />;
  }

  if (!detail) {
    return (
      <div className="grid h-full place-items-center rounded-2xl border border-dashed border-sand-300 p-8 text-center">
        <div>
          <p className="font-display text-xl text-ink-900">Nothing selected</p>
          <p className="mt-2 max-w-sm text-sm text-ink-500">
            Open the customer site, ask to cancel BK-1042 and get a refund, then come back. The
            request appears in the queue within seconds.
          </p>
        </div>
      </div>
    );
  }

  const { approval } = detail;
  const pending = approval.status === "pending";

  return (
    <div className="grid min-h-0 gap-4 lg:grid-cols-[1.2fr_1fr]">
      <section
        aria-label="Conversation"
        className="flex min-h-0 flex-col rounded-2xl border border-sand-200 bg-sand-50 p-4"
      >
        <header className="flex items-center justify-between gap-3 pb-3">
          <h2 className="font-display text-lg text-ink-900">Conversation</h2>
          <span className="text-xs text-ink-500">
            opened {timeAgo(approval.created_at)}
          </span>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          <Transcript detail={detail} />
        </div>
      </section>

      <section
        aria-label="Decision"
        className="flex min-h-0 flex-col gap-4 overflow-y-auto rounded-2xl border border-sand-200 bg-white p-4"
      >
        <header className="flex items-center justify-between gap-3">
          <h2 className="font-display text-lg text-ink-900">Refund request</h2>
          <Pill tone={pending ? "amber" : approval.status === "approved" ? "moss" : "rose"}>
            {pending ? "Waiting for you" : approval.status}
          </Pill>
        </header>

        <Facts detail={detail} />

        {pending ? (
          <div className="mt-auto space-y-3">
            <label className="block text-sm">
              <span className="text-ink-500">Note for the record</span>
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={2}
                maxLength={500}
                placeholder="Checked the cancellation time"
                className="mt-1 w-full resize-none rounded-xl border border-sand-300 bg-sand-50 px-3 py-2 text-sm text-ink-900 placeholder:text-ink-300 focus:border-tide-600 focus:outline-none"
              />
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={deciding}
                onClick={() => void onDecide(true, note)}
                className="flex-1 rounded-xl bg-tide-600 px-4 py-2.5 text-sm font-medium text-white transition-colors enabled:hover:bg-tide-700 disabled:opacity-50"
              >
                {deciding ? "Working…" : `Approve ${approval.amount}`}
              </button>
              <button
                type="button"
                disabled={deciding}
                onClick={() => void onDecide(false, note)}
                className="rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-medium text-rose-700 transition-colors enabled:hover:bg-rose-50 disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </div>
        ) : (
          <div className="mt-auto rounded-xl bg-sand-100 p-3 text-sm">
            <p className="text-ink-900">
              {approval.status === "approved" ? "Approved" : "Rejected"} by{" "}
              <span className="font-medium">{approval.reviewer ?? "unknown"}</span>
              {approval.decided_at && <> · {timeAgo(approval.decided_at)}</>}
            </p>
            {approval.review_note && (
              <p className="mt-1 text-ink-700">Note: {approval.review_note}</p>
            )}
            {lastDecision && (
              <p className="mt-2 rounded-lg bg-white p-2 text-xs text-ink-700">
                Sent to the customer: “{lastDecision.customer_reply}”
              </p>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
