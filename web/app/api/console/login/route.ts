import { cookies } from "next/headers";
import type { NextRequest } from "next/server";
import { z } from "zod";

import { errorResponse } from "@/lib/concierge-api";
import {
  SESSION_COOKIE,
  createSessionToken,
  passwordMatches,
  sessionCookieOptions,
} from "@/lib/operator-session";
import { readJson } from "@/lib/validation";

const FAILED_LOGIN_DELAY_MS = 1_000;
const bodySchema = z.object({ password: z.string().min(1).max(200) });

export async function POST(request: NextRequest): Promise<Response> {
  const parsed = bodySchema.safeParse(await readJson(request));
  if (!parsed.success) {
    return errorResponse(400);
  }
  const token = passwordMatches(parsed.data.password) ? createSessionToken() : null;
  if (!token) {
    // Slow every failure and say nothing about why, so guessing is expensive and uninformative.
    await new Promise((resolve) => setTimeout(resolve, FAILED_LOGIN_DELAY_MS));
    return errorResponse(401, "Incorrect password.");
  }
  (await cookies()).set(SESSION_COOKIE, token, sessionCookieOptions);
  return Response.json({ ok: true });
}
