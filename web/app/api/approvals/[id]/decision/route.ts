import type { NextRequest } from "next/server";

import { errorResponse, forward } from "@/lib/concierge-api";
import { decisionBodySchema, readJson, uuidSchema } from "@/lib/validation";

export async function POST(
  request: NextRequest,
  ctx: RouteContext<"/api/approvals/[id]/decision">,
): Promise<Response> {
  const { id } = await ctx.params;
  const parsed = decisionBodySchema.safeParse(await readJson(request));
  if (!uuidSchema.safeParse(id).success || !parsed.success) {
    return errorResponse(400);
  }
  return forward("operator", `/v1/approvals/${id}/decision`, {
    method: "POST",
    body: { approve: parsed.data.approve, note: parsed.data.note || null },
  });
}
