"use client";

import { useState } from "react";

interface ResetDemoButtonProps {
  onReset: () => Promise<void>;
  resetting: boolean;
}

/** Two-step confirm in the page itself: browser dialogs block everything behind them. */
export function ResetDemoButton({ onReset, resetting }: ResetDemoButtonProps) {
  const [armed, setArmed] = useState(false);

  if (!armed) {
    return (
      <button
        type="button"
        onClick={() => setArmed(true)}
        className="rounded-full border border-sand-300 px-3 py-1.5 text-xs text-ink-700 transition-colors hover:border-ink-900 hover:text-ink-900"
      >
        Reset demo data
      </button>
    );
  }

  return (
    <span className="flex items-center gap-2 text-xs">
      <span className="text-ink-500">Clear all conversations and refunds?</span>
      <button
        type="button"
        disabled={resetting}
        onClick={() => {
          void onReset().finally(() => setArmed(false));
        }}
        className="rounded-full bg-ink-950 px-3 py-1.5 font-medium text-sand-50 disabled:opacity-50"
      >
        {resetting ? "Resetting…" : "Yes, reset"}
      </button>
      <button
        type="button"
        onClick={() => setArmed(false)}
        className="rounded-full px-2 py-1.5 text-ink-500 hover:text-ink-900"
      >
        Cancel
      </button>
    </span>
  );
}
