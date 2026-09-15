"use client";

import { PERSONAS, type Persona, type PersonaId } from "@/lib/personas";

interface PersonaSwitcherProps {
  current: Persona;
  onChange: (id: PersonaId) => void;
}

export function PersonaSwitcher({ current, onChange }: PersonaSwitcherProps) {
  return (
    <div className="flex items-center gap-3">
      <span className="hidden text-xs text-ink-500 sm:block">Signed in as</span>
      <div
        role="radiogroup"
        aria-label="Demo customer"
        className="flex items-center gap-1 rounded-full bg-sand-200/70 p-1 ring-1 ring-inset ring-sand-300"
      >
        {PERSONAS.map((persona) => {
          const active = persona.id === current.id;
          return (
            <button
              key={persona.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(persona.id)}
              title={persona.blurb}
              className={`flex items-center gap-2 rounded-full py-1 pr-3 pl-1 text-sm transition-colors ${
                active
                  ? "bg-white text-ink-900 shadow-sm ring-1 ring-sand-300"
                  : "text-ink-700 hover:bg-white/60"
              }`}
            >
              <span
                className={`grid size-6 place-items-center rounded-full text-[11px] font-semibold ${
                  active ? "bg-tide-600 text-white" : "bg-sand-300 text-ink-700"
                }`}
              >
                {persona.initials}
              </span>
              {persona.name.split(" ")[0]}
            </button>
          );
        })}
      </div>
    </div>
  );
}
