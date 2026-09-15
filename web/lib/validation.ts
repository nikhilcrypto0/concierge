import { z } from "zod";

import { PERSONA_IDS, personaById, type Persona } from "@/lib/personas";

export const personaIdSchema = z.enum(PERSONA_IDS);

export const chatBodySchema = z.object({
  persona: personaIdSchema,
  message: z.string().trim().min(1).max(2_000),
  conversationId: z.uuid().optional(),
});

export const decisionBodySchema = z.object({
  approve: z.boolean(),
  note: z.string().trim().max(500).optional(),
});

export const approvalStatusSchema = z.enum(["pending", "approved", "rejected"]);

export const uuidSchema = z.uuid();

export function personaFromQuery(searchParams: URLSearchParams): Persona | null {
  const parsed = personaIdSchema.safeParse(searchParams.get("persona"));
  return parsed.success ? personaById(parsed.data) : null;
}

export async function readJson(request: Request): Promise<unknown> {
  try {
    return await request.json();
  } catch {
    return undefined;
  }
}
