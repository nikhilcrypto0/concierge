import type { NextRequest } from "next/server";

import { errorResponse, forward } from "@/lib/concierge-api";
import { requireOperator } from "@/lib/operator-session";
import { decisionBodySchema, readJson, uuidSchema } from "@/lib/validation";

export async function POST(
  request: NextRequest,
  ctx: RouteContext<"/api/approvals/[id]/decision">,
): Promise<Response> {
  const denied = await requireOperator();
  if (denied) return denied;
  const { id } = await ctx.params;
  const parsed = decisionBodySchema.safeParse(await readJson(request));
  if (!uuidSchema.safeParse(id).success || !parsed.success) {
    return errorResponse(400);
  }
  return forward("operator", `/v1/approvals/${id}/decision`, {
    method: "POST",
    body: {
      approve: parsed.data.approve,
      note: parsed.data.note || null,
      // Sent only when a lower amount was chosen, so plain approvals still work against an API
      // that has not been redeployed yet (it rejects fields it does not know).
      ...(parsed.data.approved_amount_cents === undefined
        ? {}
        : { approved_amount_cents: parsed.data.approved_amount_cents }),
    },
  });
}
