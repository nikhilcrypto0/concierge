"use client";

import { useSyncExternalStore } from "react";

const TICK_MS = 1_000;

function subscribe(onChange: () => void): () => void {
  const timer = setInterval(onChange, TICK_MS);
  return () => clearInterval(timer);
}

// Rounded to the second so the snapshot is stable between ticks; React requires
// getSnapshot to return the same value until the store actually changes.
function getSnapshot(): number {
  return Math.floor(Date.now() / TICK_MS) * TICK_MS;
}

// There is no clock on the server, and elapsed times are meaningless before hydration.
function getServerSnapshot(): number {
  return 0;
}

/**
 * The wall clock as an external store, so elapsed-time figures stay live without
 * calling an impure function during render.
 */
export function useNow(): number {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
