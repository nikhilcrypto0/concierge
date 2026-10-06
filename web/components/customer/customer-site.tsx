"use client";

import { useCallback, useState } from "react";

import { BookingsPanel } from "@/components/customer/bookings-panel";
import { BreakItPanel } from "@/components/customer/break-it-panel";
import { ChatWidget } from "@/components/customer/chat-widget";
import { PitchBand, type TourProgress } from "@/components/customer/pitch-band";
import { SiteHeader } from "@/components/customer/site-header";
import {
  ServicesSection,
  SiteFooter,
  TrustSection,
} from "@/components/customer/site-sections";
import { Pill } from "@/components/ui/pill";
import { useBookings } from "@/hooks/use-bookings";
import { useChat } from "@/hooks/use-chat";
import { useLocalStorage } from "@/hooks/use-local-storage";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useWarmUp } from "@/hooks/use-warm-up";
import { PERSONA_IDS, personaById, type PersonaId } from "@/lib/personas";
import type { Booking } from "@/lib/types";

const isPersonaId = (value: string): value is PersonaId =>
  (PERSONA_IDS as readonly string[]).includes(value);

export function CustomerSite() {
  useWarmUp();
  const [personaId, setPersonaId] = useLocalStorage<PersonaId>(
    "concierge:persona",
    "maya",
    isPersonaId,
  );
  const persona = personaById(personaId ?? "maya");

  const { bookings, loaded, refresh } = useBookings(persona.id);
  const onBookingsMayHaveChanged = useCallback(() => {
    void refresh();
  }, [refresh]);
  const chat = useChat({ persona, onBookingsMayHaveChanged });

  // The chat docks beside the page on wide screens, so it starts open there. On a phone it is a
  // full-height sheet, and opening it first would cover the pitch a visitor came to read, so it
  // starts closed behind the launcher button. Once the visitor opens or closes it, that wins.
  const wideScreen = useMediaQuery("(min-width: 1280px)");
  const [chatPreference, setChatPreference] = useState<boolean | null>(null);
  const chatOpen = chatPreference ?? wideScreen;
  const setChatOpen = setChatPreference;
  const [input, setInput] = useState("");

  const askAbout = (booking: Booking) => {
    setChatOpen(true);
    setInput(`About booking ${booking.reference}: `);
  };

  // The hero's walkthrough ticks off what this visitor has really done: asking for a refund and
  // seeing it wait are one moment (2 steps), and a decision arriving completes the third.
  const decided = chat.messages.some(
    (message) => message.outcome === "refund_completed" || message.outcome === "refund_rejected",
  );
  const tourProgress: TourProgress = decided ? 3 : chat.awaitingApproval ? 2 : 0;

  // Room for the docked chat. Only the content makes room; the header spans the full width.
  const dock = `transition-[padding] duration-300 ${chatOpen ? "xl:pr-[420px]" : ""}`;

  return (
    <div className="paper flex min-h-full flex-col">
      <SiteHeader persona={persona} onPersonaChange={setPersonaId} />

      <main className={`flex-1 ${dock}`}>
        <PitchBand
          onTry={() => {
            setChatOpen(true);
            setInput("Cancel BK-1042 and refund me");
          }}
          progress={tourProgress}
        />
        <section className="mx-auto w-full max-w-7xl px-4 pt-10 pb-14 sm:px-6 lg:pt-12">
          <div className="grid items-start gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
            <div>
              <Pill tone="tide">Austin · Dallas · Houston · San Antonio · Denver</Pill>
              <h1 className="mt-5 font-display text-4xl leading-[1.05] text-ink-950 sm:text-5xl lg:text-6xl">
                Home care, handled by people who actually show up.
              </h1>
              <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-700 sm:text-lg">
                Cleaning, repairs, plumbing and AC, booked in a couple of minutes. Questions
                answered any hour by our assistant, with a real person on anything that touches
                your money.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setChatOpen(true);
                    setInput("I'd like to book a deep cleaning");
                  }}
                  className="rounded-full bg-ink-950 px-5 py-3 text-sm font-medium text-sand-50 transition-colors hover:bg-tide-700"
                >
                  Book a service
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setChatOpen(true);
                    setInput("Cancel BK-1042 and refund me");
                  }}
                  className="rounded-full border border-ink-900/20 px-5 py-3 text-sm font-medium text-ink-900 transition-colors hover:border-tide-600 hover:text-tide-700"
                >
                  Try a refund request
                </button>
              </div>
            </div>

            <BookingsPanel bookings={bookings} loaded={loaded} onAsk={askAbout} />
          </div>
        </section>

        <ServicesSection />
        <div className="h-16" />
        <TrustSection />
        <BreakItPanel />
        <div className="h-16" />
      </main>

      <div className={dock}>
        <SiteFooter />
      </div>

      <ChatWidget
        persona={persona}
        chat={chat}
        open={chatOpen}
        onOpenChange={setChatOpen}
        input={input}
        onInputChange={setInput}
      />
    </div>
  );
}
