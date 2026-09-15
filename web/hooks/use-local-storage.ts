"use client";

import { useCallback, useSyncExternalStore } from "react";

// A tiny external store over localStorage, so every component reading a key stays in sync and
// server rendering uses the fallback instead of touching window.

const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function readRaw(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function useLocalStorage<T extends string>(
  key: string,
  fallback: T | null,
  isValid: (value: string) => value is T,
): [T | null, (next: T | null) => void] {
  const raw = useSyncExternalStore(
    subscribe,
    () => readRaw(key),
    () => null,
  );
  const value = raw !== null && isValid(raw) ? raw : fallback;

  const setValue = useCallback(
    (next: T | null) => {
      try {
        if (next === null) {
          window.localStorage.removeItem(key);
        } else {
          window.localStorage.setItem(key, next);
        }
      } catch {
        // Private browsing can block storage; the value simply won't persist.
      }
      listeners.forEach((listener) => listener());
    },
    [key],
  );

  return [value, setValue];
}
