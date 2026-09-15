"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api-client";
import type { PersonaId } from "@/lib/personas";
import type { Booking } from "@/lib/types";

export interface BookingsController {
  bookings: Booking[];
  loaded: boolean;
  refresh: () => Promise<void>;
}

export function useBookings(personaId: PersonaId): BookingsController {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loaded, setLoaded] = useState(false);

  // Load whenever the persona changes. State is set from the network callback, never
  // synchronously while the effect runs.
  useEffect(() => {
    let cancelled = false;
    api
      .bookings(personaId)
      .then((rows) => {
        if (!cancelled) setBookings(rows);
      })
      .catch(() => {
        // Keep whatever is on screen; a later refresh tries again.
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [personaId]);

  /** Re-read bookings after a turn that may have changed them. Called from event handlers. */
  const refresh = useCallback(async () => {
    try {
      setBookings(await api.bookings(personaId));
    } catch {
      // Ignore: the list simply stays as it is.
    }
  }, [personaId]);

  return { bookings, loaded, refresh };
}
