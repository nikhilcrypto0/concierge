import { errorResponse, forward } from "@/lib/concierge-api";
import { personaById } from "@/lib/personas";
import { chatBodySchema, readJson } from "@/lib/validation";

export async function POST(request: Request): Promise<Response> {
  const parsed = chatBodySchema.safeParse(await readJson(request));
  if (!parsed.success) {
    return errorResponse(400);
  }
  const { persona, message, conversationId } = parsed.data;
  return forward("client", "/v1/chat", {
    method: "POST",
    body: {
      customer_email: personaById(persona).email,
      message,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    },
  });
}
