"use client";

import { useStats } from "@/hooks/use-stats";

const USD = (value: number) => `$${value.toFixed(4)}`;
const COUNT = (value: number) => value.toLocaleString("en-US");

/**
 * What this live demo is costing right now, read from the same token ledger that enforces the
 * spending limits. The measured figures above it come from the eval; these come from real use.
 * If the API cannot be reached the line simply does not appear.
 */
export function LiveStats() {
  const stats = useStats();
  if (!stats) return null;

  const guard = `${COUNT(stats.tokens_in_window)} of ${COUNT(stats.daily_token_budget)} tokens used against the daily spending limit.`;
  const usage =
    stats.conversations === 0 || stats.usd_per_conversation === null
      ? "No conversations have reached the AI in the last 24 hours."
      : `${COUNT(stats.conversations)} conversation${stats.conversations === 1 ? "" : "s"} reached the AI in the last 24 hours, about ${USD(stats.usd_per_conversation)} each (${USD(stats.usd_total)} in total).`;

  return (
    <p className="mt-2 text-xs leading-relaxed text-sand-300">
      <span className="font-medium text-tide-100">Live on this demo:</span> {usage} {guard}
    </p>
  );
}
