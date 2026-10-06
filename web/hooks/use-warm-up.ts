"use client";

import { useEffect } from "react";

import { api } from "@/lib/api-client";

/** Wakes a sleeping API once per page view, so the first real request does not wait for a boot. */
export function useWarmUp(): void {
  useEffect(() => {
    api.wake().catch(() => {
      // Best effort: a failed warm-up changes nothing the visitor can see.
    });
  }, []);
}
