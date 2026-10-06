import { z } from "zod";

import { errorResponse, forward } from "@/lib/concierge-api";
import { personaById, PERSONA_IDS } from "@/lib/personas";
import { readJson } from "@/lib/validation";

// Demo only: lets a visitor play the support lead for THEIR OWN pending request. The API refuses
// it outside demo mode, and it only ever decides the open request on a conversation that belongs
// to the persona asking. The real console and its decision route stay behind the password.
const bodySchema = z
  .object({
    persona: z.enum(PERSONA_IDS),
    conversationId: z.uuid(),
    approve: z.boolean(),
    approvedAmountCents: z.number().int().positive().optional(),
  })
  .refine((body) => body.approve || body.approvedAmountCents === undefined, {
    message: "an amount can only accompany an approval",
  });

export async function POST(request: Request): Promise<Response> {
  const parsed = bodySchema.safeParse(await readJson(request));
  if (!parsed.success) {
    return errorResponse(400);
  }
  const { persona, conversationId, approve, approvedAmountCents } = parsed.data;
  return forward("client", "/v1/demo/decide", {
    method: "POST",
    body: {
      conversation_id: conversationId,
      customer_email: personaById(persona).email,
      approve,
      ...(approvedAmountCents === undefined ? {} : { approved_amount_cents: approvedAmountCents }),
    },
  });
}
