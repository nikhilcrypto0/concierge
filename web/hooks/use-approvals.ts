"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ApiRequestError } from "@/lib/api-client";
import { usePolling } from "@/hooks/use-polling";
import type { Approval, ApprovalDetail, DecisionResult } from "@/lib/types";

export interface ApprovalQueueController {
  pending: Approval[];
  history: Approval[];
  selectedId: string | null;
  select: (id: string | null) => void;
  detail: ApprovalDetail | null;
  detailLoading: boolean;
  deciding: boolean;
  lastDecision: DecisionResult | null;
  error: string | null;
  decide: (approve: boolean, note: string) => Promise<void>;
  resetDemo: () => Promise<void>;
  resetting: boolean;
}

const POLL_MS = 4_000;

function byNewestDecision(a: Approval, b: Approval): number {
  return (b.decided_at ?? "").localeCompare(a.decided_at ?? "");
}

async function fetchQueues(): Promise<{ pending: Approval[]; history: Approval[] }> {
  const [pending, approved, rejected] = await Promise.all([
    api.approvals("pending"),
    api.approvals("approved"),
    api.approvals("rejected"),
  ]);
  return { pending, history: [...approved, ...rejected].sort(byNewestDecision) };
}

export function useApprovalQueue(): ApprovalQueueController {
  const [pending, setPending] = useState<Approval[]>([]);
  const [history, setHistory] = useState<Approval[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailState, setDetailState] = useState<ApprovalDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [lastDecision, setLastDecision] = useState<DecisionResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyQueues = useCallback((queues: { pending: Approval[]; history: Approval[] }) => {
    setPending(queues.pending);
    setHistory(queues.history);
    setSelectedId((current) => current ?? queues.pending[0]?.id ?? null);
  }, []);

  const refreshLists = useCallback(async () => {
    applyQueues(await fetchQueues());
  }, [applyQueues]);

  // First load: state is set from the network callback, never synchronously in the effect.
  useEffect(() => {
    let cancelled = false;
    fetchQueues()
      .then((queues) => {
        if (!cancelled) applyQueues(queues);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load the queue.");
      });
    return () => {
      cancelled = true;
    };
  }, [applyQueues]);

  // Heartbeat: refresh the queues AND the open request, so a refund requested on the customer
  // site appears here on its own, and a request decided elsewhere stops offering buttons.
  usePolling(
    async () => {
      applyQueues(await fetchQueues());
      if (!selectedId || deciding) return;
      const fresh = await api.approval(selectedId);
      setDetailState((current) => (current?.approval.id === fresh.approval.id ? fresh : current));
    },
    POLL_MS,
    true,
  );

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    api
      .approval(selectedId)
      .then((value) => {
        if (!cancelled) {
          setDetailState(value);
          setDetailLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDetailState(null);
          setDetailLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const decide = useCallback(
    async (approve: boolean, note: string) => {
      if (!selectedId || deciding) return;
      setDeciding(true);
      setError(null);
      try {
        const result = await api.decide(selectedId, {
          approve,
          note: note.trim() || undefined,
        });
        setLastDecision(result);
        setDetailState((current) =>
          current ? { ...current, approval: result.approval } : current,
        );
        await refreshLists();
      } catch (failure: unknown) {
        setError(
          failure instanceof ApiRequestError ? failure.message : "Could not record that decision.",
        );
        // Someone else may have decided it first; show the current state rather than stale buttons.
        try {
          setDetailState(await api.approval(selectedId));
        } catch {
          // Leave the panel as it is; the heartbeat will catch up.
        }
      } finally {
        setDeciding(false);
      }
    },
    [deciding, refreshLists, selectedId],
  );

  const resetDemo = useCallback(async () => {
    setResetting(true);
    setError(null);
    try {
      await api.resetDemo();
      setSelectedId(null);
      setDetailState(null);
      setLastDecision(null);
      await refreshLists();
    } catch (failure: unknown) {
      setError(failure instanceof ApiRequestError ? failure.message : "Could not reset the demo.");
    } finally {
      setResetting(false);
    }
  }, [refreshLists]);

  const select = useCallback((id: string | null) => {
    setSelectedId(id);
    setLastDecision(null);
    setDetailLoading(id !== null);
  }, []);

  // Derived, so clearing the selection needs no effect.
  const detail = selectedId && detailState?.approval.id === selectedId ? detailState : null;

  return {
    pending,
    history,
    selectedId,
    select,
    detail,
    detailLoading,
    deciding,
    lastDecision,
    error,
    decide,
    resetDemo,
    resetting,
  };
}
