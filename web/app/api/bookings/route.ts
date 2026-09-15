import type { NextRequest } from "next/server";

import { errorResponse, forward } from "@/lib/concierge-api";
import { personaFromQuery } from "@/lib/validation";

export async function GET(request: NextRequest): Promise<Response> {
  const persona = personaFromQuery(request.nextUrl.searchParams);
  if (!persona) {
    return errorResponse(400);
  }
  const query = new URLSearchParams({ customer_email: persona.email });
  return forward("client", `/v1/bookings?${query}`);
}
