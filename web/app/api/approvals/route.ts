import type { NextRequest } from "next/server";

import { errorResponse, forward } from "@/lib/concierge-api";
import { approvalStatusSchema } from "@/lib/validation";

export async function GET(request: NextRequest): Promise<Response> {
  const status = approvalStatusSchema.safeParse(
    request.nextUrl.searchParams.get("status") ?? "pending",
  );
  if (!status.success) {
    return errorResponse(400);
  }
  const query = new URLSearchParams({ status: status.data, limit: "50" });
  return forward("operator", `/v1/approvals?${query}`);
}
