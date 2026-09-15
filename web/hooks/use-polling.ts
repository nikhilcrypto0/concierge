"use client";

import { useEffect, useEffectEvent } from "react";

/** Run `task` every `intervalMs` while enabled, waiting for each run to finish before the next. */
export function usePolling(task: () => Promise<void>, intervalMs: number, enabled: boolean): void {
  const onTick = useEffectEvent(task);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async () => {
      if (!document.hidden) {
        try {
          await onTick();
        } catch {
          // The next tick retries; callers surface their own errors.
        }
      }
      if (!cancelled) {
        timer = setTimeout(tick, intervalMs);
      }
    };

    timer = setTimeout(tick, intervalMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [enabled, intervalMs]);
}
