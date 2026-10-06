"use client";

import { useSyncExternalStore } from "react";

// The moment this page was first rendered in the browser, captured once. Sample data is dated
// relative to it, so the same sample looks fresh whenever it is opened. Like `useNow`, it is an
// external store, so no impure call happens during render.
let mountedAt: number | null = null;

function subscribe(): () => void {
  return () => {};
}

function getSnapshot(): number {
  mountedAt ??= Date.now();
  return mountedAt;
}

// Zero on the server, and until hydration finishes: there is no meaningful time yet.
function getServerSnapshot(): number {
  return 0;
}

export function useMountTime(): number {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
