import "server-only";

import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

// Operator login for the support console: one shared password, checked on the server, that
// sets a signed HttpOnly cookie. If either secret is missing, every check fails closed.

export const SESSION_COOKIE = "concierge_operator";
const SESSION_TTL_SECONDS = 8 * 60 * 60;
const MIN_PASSWORD_LENGTH = 16;
const MIN_SECRET_LENGTH = 32;

function config(): { password: string; secret: string } | null {
  const password = process.env.CONSOLE_PASSWORD ?? "";
  const secret = process.env.CONSOLE_SESSION_SECRET ?? "";
  if (password.length < MIN_PASSWORD_LENGTH || secret.length < MIN_SECRET_LENGTH) {
    console.error("[operator-session] CONSOLE_PASSWORD / CONSOLE_SESSION_SECRET missing or short");
    return null;
  }
  return { password, secret };
}

function sign(secret: string, expiresAt: number): string {
  return createHmac("sha256", secret).update(String(expiresAt)).digest("hex");
}

function sameString(a: string, b: string): boolean {
  // Hash first so the comparison is constant-length and does not leak the password length.
  const digest = (value: string) => createHash("sha256").update(value).digest();
  return timingSafeEqual(digest(a), digest(b));
}

export function passwordMatches(presented: string): boolean {
  const cfg = config();
  return cfg !== null && sameString(presented, cfg.password);
}

export function createSessionToken(nowMs: number = Date.now()): string | null {
  const cfg = config();
  if (!cfg) return null;
  const expiresAt = nowMs + SESSION_TTL_SECONDS * 1000;
  return `${expiresAt}.${sign(cfg.secret, expiresAt)}`;
}

export function verifySessionToken(token: string | undefined, nowMs: number = Date.now()): boolean {
  const cfg = config();
  if (!cfg || !token) return false;
  const [expiresRaw, signature] = token.split(".");
  const expiresAt = Number(expiresRaw);
  if (!signature || !Number.isFinite(expiresAt) || expiresAt <= nowMs) return false;
  return sameString(signature, sign(cfg.secret, expiresAt));
}

export const sessionCookieOptions = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "strict" as const,
  path: "/",
  maxAge: SESSION_TTL_SECONDS,
};

export async function isOperator(): Promise<boolean> {
  return verifySessionToken((await cookies()).get(SESSION_COOKIE)?.value);
}

/** Returns a 401 response when the caller is not a logged-in operator, otherwise null. */
export async function requireOperator(): Promise<Response | null> {
  if (await isOperator()) return null;
  return Response.json({ error: "Operator login required." }, { status: 401 });
}
