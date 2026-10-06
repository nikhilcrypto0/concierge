"use client";

import { useSyncExternalStore } from "react";

/**
 * Whether a CSS media query currently matches. On the server, and on the first render before the
 * browser can answer, it is `false`, so server HTML and the first client render always agree.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
