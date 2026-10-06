"use client";

import { useMemo, useState } from "react";

import { ConsoleView } from "@/components/console/console-view";
import type { ApprovalQueueController } from "@/hooks/use-approvals";
import { useMountTime } from "@/hooks/use-mount-time";
import { useNow } from "@/hooks/use-now";
import { buildSampleConsole } from "@/lib/sample-console";

const NOTHING = async (): Promise<void> => {};

/**
 * A public, read-only tour of the console on made-up data. It makes no network request at all:
 * the real console needs the operator password, and showing live approvals would show other
 * visitors' chats. Do not wire this to the API.
 */
export function SampleConsole() {
  const now = useNow();
  const anchor = useMountTime();
  const data = useMemo(() => buildSampleConsole(anchor), [anchor]);
  const [picked, setPicked] = useState<string | null>(null);

  // Until the page has hydrated there is no clock, so there is nothing sensible to show.
  if (anchor === 0) return null;

  const selectedId = picked ?? data.pending[0]?.id ?? null;
  const queue: ApprovalQueueController = {
    pending: data.pending,
    history: data.history,
    selectedId,
    select: setPicked,
    detail: selectedId ? (data.details[selectedId] ?? null) : null,
    detailLoading: false,
    deciding: false,
    lastDecision: null,
    error: null,
    decide: NOTHING,
    resetDemo: NOTHING,
    resetting: false,
  };
  return <ConsoleView queue={queue} now={now} sample />;
}
