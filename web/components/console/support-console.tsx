"use client";

import { ConsoleView } from "@/components/console/console-view";
import { useApprovalQueue } from "@/hooks/use-approvals";
import { useNow } from "@/hooks/use-now";
import { useWarmUp } from "@/hooks/use-warm-up";

/** The real console: live approvals from the API, behind the operator password. */
export function SupportConsole() {
  useWarmUp();
  const queue = useApprovalQueue();
  const now = useNow();
  return <ConsoleView queue={queue} now={now} />;
}
