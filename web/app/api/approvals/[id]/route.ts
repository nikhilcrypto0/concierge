import type { NextRequest } from "next/server";

import { errorResponse, forward } from "@/lib/concierge-api";
import { uuidSchema } from "@/lib/validation";

export async function GET(
  _request: NextRequest,
  ctx: RouteContext<"/api/approvals/[id]">,
): Promise<Response> {
  const { id } = await ctx.params;
  if (!uuidSchema.safeParse(id).success) {
    return errorResponse(400);
  }
  return forward("operator", `/v1/approvals/${id}`);
}
