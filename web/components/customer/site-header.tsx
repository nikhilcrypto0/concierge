"use client";

import { PersonaSwitcher } from "@/components/customer/persona-switcher";
import type { Persona, PersonaId } from "@/lib/personas";

const NAV = ["Cleaning", "Repairs", "Heating & AC", "Help center"] as const;

interface SiteHeaderProps {
  persona: Persona;
  onPersonaChange: (id: PersonaId) => void;
}

export function SiteHeader({ persona, onPersonaChange }: SiteHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-sand-200 bg-sand-50/85 backdrop-blur">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-4 px-4 py-3 sm:px-6">
        <span className="flex items-center gap-2">
          <span aria-hidden className="text-tide-600">
            <svg width="26" height="26" viewBox="0 0 26 26" fill="none">
              <path
                d="M2 16c3.2 0 3.2-4 6.4-4s3.2 4 6.4 4 3.2-4 6.4-4 3.2 4 4.8 4"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M2 21c3.2 0 3.2-4 6.4-4s3.2 4 6.4 4 3.2-4 6.4-4 3.2 4 4.8 4"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                opacity="0.45"
              />
            </svg>
          </span>
          <span className="font-display text-xl tracking-tight text-ink-950">Tidewell</span>
          <span className="hidden text-xs text-ink-500 sm:block">Home Services</span>
        </span>

        <nav aria-label="Services" className="hidden items-center gap-5 lg:flex">
          {NAV.map((item) => (
            <span key={item} className="text-sm text-ink-700">
              {item}
            </span>
          ))}
        </nav>

        <div className="ml-auto">
          <PersonaSwitcher current={persona} onChange={onPersonaChange} />
        </div>
      </div>
    </header>
  );
}
