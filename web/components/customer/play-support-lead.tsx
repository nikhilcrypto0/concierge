"use client";

import { useState } from "react";

import { api, ApiRequestError } from "@/lib/api-client";
import { parseDollarsToCents } from "@/lib/money";
import type { Persona } from "@/lib/personas";

interface PlaySupportLeadProps {
  persona: Persona;
  conversationId: string;
  /** Called after the decision is recorded, so the chat shows the outcome straight away. */
  onDecided: () => Promise<void>;
}

const NOT_FOUND = "That request was already decided, or the demo was reset. Ask again to try once more.";
const TOO_HIGH = "That is more than this request allows. A reviewer can lower the amount, never raise it.";

export function PlaySupportLead({ persona, conversationId, onDecided }: PlaySupportLeadProps) {
  const [amountText, setAmountText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const decide = async (approve: boolean) => {
    const typed = amountText.trim();
    const cents = typed === "" ? undefined : parseDollarsToCents(typed);
    if (typed !== "" && cents === null) {
      setError("Enter an amount like 100 or 100.50, or leave it empty.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.demoDecide({
        persona: persona.id,
        conversationId,
        approve,
        approvedAmountCents: approve ? (cents ?? undefined) : undefined,
      });
      await onDecided();
    } catch (failure: unknown) {
      if (failure instanceof ApiRequestError && failure.status === 404) setError(NOT_FOUND);
      else if (failure instanceof ApiRequestError && failure.status === 422) setError(TOO_HIGH);
      else setError(failure instanceof ApiRequestError ? failure.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      aria-label="Play the support lead"
      className="mt-3 rounded-xl border border-tide-100 bg-tide-50 p-3 text-xs text-ink-700"
    >
      <p className="font-semibold text-tide-700">Try the support lead&apos;s side</p>
      <p className="mt-1">
        In the real product only signed-in staff can decide this. In this demo you can play the
        support lead for your own request.
      </p>
      <label className="mt-2 block">
        <span className="text-ink-500">Approve a lower amount (optional)</span>
        <input
          type="text"
          inputMode="decimal"
          value={amountText}
          onChange={(event) => setAmountText(event.target.value)}
          placeholder="Leave empty to approve the full amount"
          className="mt-1 w-full rounded-lg border border-sand-300 bg-white px-2.5 py-1.5 font-mono text-xs text-ink-900 placeholder:text-ink-300 focus:border-tide-600 focus:outline-none"
        />
      </label>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void decide(true)}
          className="flex-1 rounded-lg bg-tide-600 px-3 py-2 text-xs font-medium text-white transition-colors enabled:hover:bg-tide-700 disabled:opacity-50"
        >
          {busy ? "Working…" : "Approve"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void decide(false)}
          className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-xs font-medium text-rose-700 transition-colors enabled:hover:bg-rose-50 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
      {error && (
        <p role="alert" className="mt-2 text-rose-700">
          {error}
        </p>
      )}
    </section>
  );
}
