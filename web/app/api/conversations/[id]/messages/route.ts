import type { NextRequest } from "next/server";

import { errorResponse, forward } from "@/lib/concierge-api";
import { personaFromQuery, uuidSchema } from "@/lib/validation";

export async function GET(
  request: NextRequest,
  ctx: RouteContext<"/api/conversations/[id]/messages">,
): Promise<Response> {
  const { id } = await ctx.params;
  const persona = personaFromQuery(request.nextUrl.searchParams);
  if (!persona || !uuidSchema.safeParse(id).success) {
    return errorResponse(400);
  }
  const query = new URLSearchParams({ customer_email: persona.email });
  return forward("client", `/v1/conversations/${id}/messages?${query}`);
}
