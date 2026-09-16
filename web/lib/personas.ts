// Demo customers. The browser only ever sends a persona id; the server maps it to an email,
// so a visitor cannot impersonate an arbitrary customer by editing a request.

export const PERSONAS = [
  {
    id: "maya",
    name: "Maya Chen",
    email: "maya@example.com",
    city: "Austin, TX",
    initials: "MC",
    blurb: "Five bookings, including one coming up, one completed, and one already refunded.",
  },
  {
    id: "jordan",
    name: "Jordan Reyes",
    email: "jordan@example.com",
    city: "Denver, CO",
    initials: "JR",
    blurb: "One electrical visit. Try asking about Maya's bookings from this account.",
  },
] as const;

export type Persona = (typeof PERSONAS)[number];
export type PersonaId = Persona["id"];

export const PERSONA_IDS = PERSONAS.map((p) => p.id) as [PersonaId, ...PersonaId[]];

export function personaById(id: PersonaId): Persona {
  const persona = PERSONAS.find((p) => p.id === id);
  if (!persona) {
    throw new Error(`unknown persona: ${id}`);
  }
  return persona;
}
