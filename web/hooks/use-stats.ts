"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api-client";
import type { Stats } from "@/lib/types";

// One request per page view, shared by everything that needs the stats (the live cost line and
// the "play the support lead" gate). A failure is cached too, so an API that is asleep or too old
// to have the endpoint is not asked again on every render.
let pending: Promise<Stats | null> | null = null;

function loadStats(): Promise<Stats | null> {
  pending ??= api.stats().catch(() => null);
  return pending;
}

/** The API's live stats, or null until loaded and whenever they are unavailable. */
export function useStats(): Stats | null {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    let cancelled = false;
    void loadStats().then((value) => {
      if (!cancelled) setStats(value);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return stats;
}
