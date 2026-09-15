"use client";

import { Pill, type PillTone } from "@/components/ui/pill";
import { BOOKING_STATUS_COPY, formatDateTime } from "@/lib/format";
import type { Booking } from "@/lib/types";

const STATUS_TONE: Record<Booking["status"], PillTone> = {
  scheduled: "tide",
  completed: "sand",
  cancelled: "rose",
};

interface BookingsPanelProps {
  bookings: Booking[];
  loaded: boolean;
  onAsk: (booking: Booking) => void;
}

export function BookingsPanel({ bookings, loaded, onAsk }: BookingsPanelProps) {
  return (
    <section
      aria-labelledby="bookings-heading"
      className="rounded-2xl border border-sand-300 bg-white/80 p-5 shadow-[0_18px_40px_-28px_rgba(11,33,36,0.55)] backdrop-blur"
    >
      <div className="flex items-baseline justify-between gap-4">
        <h2 id="bookings-heading" className="font-display text-lg text-ink-900">
          Your bookings
        </h2>
        <span className="text-xs text-ink-500">Live from the database</span>
      </div>

      <ul className="mt-4 space-y-3">
        {!loaded &&
          [0, 1, 2].map((row) => (
            <li key={row} className="h-20 animate-pulse rounded-xl bg-sand-200/70" />
          ))}

        {loaded && bookings.length === 0 && (
          <li className="rounded-xl border border-dashed border-sand-300 p-4 text-sm text-ink-500">
            No bookings on this account.
          </li>
        )}

        {bookings.map((booking) => (
          <li
            key={booking.reference}
            className="group rounded-xl border border-sand-200 bg-sand-50 p-4 transition-colors hover:border-tide-100"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-medium text-ink-900">{booking.service}</p>
                <p className="mt-0.5 text-sm text-ink-500">
                  {formatDateTime(booking.scheduled_for)}
                </p>
              </div>
              <Pill tone={STATUS_TONE[booking.status]}>
                {BOOKING_STATUS_COPY[booking.status]}
              </Pill>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm">
                <code className="rounded bg-sand-200 px-1.5 py-0.5 font-mono text-xs text-ink-700">
                  {booking.reference}
                </code>
                <span className="text-ink-700">{booking.amount}</span>
                {booking.refunded_cents > 0 && (
                  <span className="text-ink-500">refunded {booking.refunded}</span>
                )}
              </div>
              <button
                type="button"
                onClick={() => onAsk(booking)}
                className="rounded-full border border-sand-300 px-3 py-1 text-xs font-medium text-ink-700 transition-colors hover:border-tide-600 hover:text-tide-700"
              >
                Ask about this
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
