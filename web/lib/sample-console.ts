// Sample data for the read-only console tour at /console/sample. It is made up, labelled as
// sample on screen, and never touches the API: showing live approvals to the public would show
// other visitors' chats. The rows have the same shape as the API's, so the real console
// components render them unchanged and the metrics are computed from them like real ones.

import type { Approval, ApprovalDetail, Booking } from "@/lib/types";

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;

export interface SampleConsoleData {
  pending: Approval[];
  history: Approval[];
  details: Record<string, ApprovalDetail>;
}

function isoAt(anchorMs: number, offsetMs: number): string {
  return new Date(anchorMs + offsetMs).toISOString();
}

function booking(
  anchorMs: number,
  reference: string,
  service: string,
  startsInMs: number,
  amountCents: number,
): Booking {
  return {
    reference,
    service,
    scheduled_for: isoAt(anchorMs, startsInMs),
    status: "scheduled",
    amount_cents: amountCents,
    amount: `$${(amountCents / 100).toFixed(2)}`,
    refunded_cents: 0,
    refunded: "$0.00",
  };
}

interface RowSpec {
  id: string;
  email: string;
  booking: Booking;
  amountCents: number;
  policyReason: string;
  openedMinutesAgo: number;
  transcript: ApprovalDetail["transcript"];
  decision?: {
    status: "approved" | "rejected";
    approvedCents?: number;
    note: string;
    afterMinutes: number;
  };
}

function money(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function build(anchorMs: number, spec: RowSpec): ApprovalDetail {
  const createdAt = isoAt(anchorMs, -spec.openedMinutesAgo * MINUTE_MS);
  const decision = spec.decision;
  const approval: Approval = {
    id: spec.id,
    conversation_id: `${spec.id.slice(0, -1)}f`,
    customer_email: spec.email,
    booking_reference: spec.booking.reference,
    action: "refund",
    amount_cents: spec.amountCents,
    amount: money(spec.amountCents),
    approved_amount_cents: decision?.approvedCents ?? null,
    approved_amount: decision?.approvedCents ? money(decision.approvedCents) : null,
    policy_reason: spec.policyReason,
    status: decision?.status ?? "pending",
    reviewer: decision ? "support-lead" : null,
    review_note: decision?.note ?? null,
    created_at: createdAt,
    decided_at: decision
      ? isoAt(anchorMs, (-spec.openedMinutesAgo + decision.afterMinutes) * MINUTE_MS)
      : null,
  };
  return { approval, booking: spec.booking, transcript: spec.transcript };
}

export function buildSampleConsole(anchorMs: number): SampleConsoleData {
  const specs: RowSpec[] = [
    {
      id: "5a3d0000-0000-4000-8000-000000000001",
      email: "maya@example.com",
      booking: booking(anchorMs, "BK-1042", "Deep cleaning", 5 * 24 * HOUR_MS, 24000),
      amountCents: 24000,
      policyReason: "full_notice",
      openedMinutesAgo: 4,
      transcript: [
        { role: "customer", content: "Please cancel BK-1042 and refund me" },
        {
          role: "assistant",
          content:
            "I've asked our team to approve a refund of $240.00 for booking BK-1042. " +
            "I'll let you know as soon as a person has decided.",
        },
      ],
    },
    {
      id: "5a3d0000-0000-4000-8000-000000000002",
      email: "maya@example.com",
      booking: booking(anchorMs, "BK-1043", "Plumbing service call", 30 * HOUR_MS, 13500),
      amountCents: 6750,
      policyReason: "partial_notice",
      openedMinutesAgo: 12,
      transcript: [
        { role: "customer", content: "I need a refund for BK-1043, something came up" },
        {
          role: "assistant",
          content:
            "Under our policy that booking qualifies for a 50% refund, $67.50. " +
            "I've sent it to our team for approval.",
        },
      ],
    },
    {
      id: "5a3d0000-0000-4000-8000-000000000003",
      email: "sam@example.com",
      booking: booking(anchorMs, "BK-1038", "Handyman visit", 3 * 24 * HOUR_MS, 12000),
      amountCents: 12000,
      policyReason: "full_notice",
      openedMinutesAgo: 140,
      transcript: [
        { role: "customer", content: "Cancel BK-1038 please, refund it" },
        {
          role: "assistant",
          content: "I've asked our team to approve a refund of $120.00 for BK-1038.",
        },
      ],
      decision: {
        status: "approved",
        approvedCents: 8000,
        note: "Agreed a smaller amount with the customer by phone",
        afterMinutes: 9,
      },
    },
    {
      id: "5a3d0000-0000-4000-8000-000000000004",
      email: "lee@example.com",
      booking: booking(anchorMs, "BK-1031", "Standard cleaning", 2 * 24 * HOUR_MS, 9000),
      amountCents: 9000,
      policyReason: "full_notice",
      openedMinutesAgo: 300,
      transcript: [
        { role: "customer", content: "Refund BK-1031" },
        {
          role: "assistant",
          content: "I've asked our team to approve a refund of $90.00 for BK-1031.",
        },
      ],
      decision: {
        status: "rejected",
        note: "Duplicate request, already refunded on the card",
        afterMinutes: 6,
      },
    },
  ];

  const details = specs.map((spec) => build(anchorMs, spec));
  return {
    pending: details.filter((d) => d.approval.status === "pending").map((d) => d.approval),
    history: details.filter((d) => d.approval.status !== "pending").map((d) => d.approval),
    details: Object.fromEntries(details.map((d) => [d.approval.id, d])),
  };
}
