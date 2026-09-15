import "server-only";

// Server-side proxy to the Concierge API. API keys live only in server environment variables
// (never NEXT_PUBLIC_), and upstream error details are replaced with safe, friendly messages.

export type Role = "client" | "operator";

interface ForwardOptions {
  method?: "GET" | "POST";
  body?: unknown;
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 90_000;

const FRIENDLY_ERRORS: Record<number, string> = {
  400: "That request wasn't valid.",
  404: "We couldn't find that.",
  409: "This conversation is still being processed. Try again in a moment.",
  413: "That message is too long.",
  422: "That request wasn't valid.",
  429: "Too many requests right now. Please wait a moment and try again.",
};

function apiBaseUrl(): string {
  return process.env.CONCIERGE_API_URL ?? "http://127.0.0.1:8000";
}

function apiKey(role: Role): string | undefined {
  return role === "client"
    ? process.env.CONCIERGE_CLIENT_KEY
    : process.env.CONCIERGE_OPERATOR_KEY;
}

export function errorResponse(status: number, message?: string): Response {
  return Response.json(
    { error: message ?? FRIENDLY_ERRORS[status] ?? "Something went wrong." },
    { status },
  );
}

export async function forward(
  role: Role,
  path: string,
  options: ForwardOptions = {},
): Promise<Response> {
  const key = apiKey(role);
  if (!key) {
    console.error(`[concierge-proxy] missing API key for role "${role}"`);
    return errorResponse(503, "The support service isn't configured yet.");
  }

  const { method = "GET", body, timeoutMs = DEFAULT_TIMEOUT_MS } = options;
  let upstream: Response;
  try {
    upstream = await fetch(new URL(path, apiBaseUrl()), {
      method,
      headers: {
        "X-API-Key": key,
        ...(body === undefined ? {} : { "content-type": "application/json" }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error: unknown) {
    const reason = error instanceof Error ? error.name : "unknown";
    console.error(`[concierge-proxy] ${method} ${path} failed: ${reason}`);
    return errorResponse(502, "The support service is unavailable. Please try again.");
  }

  if (upstream.ok) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  }

  const requestId = upstream.headers.get("x-request-id") ?? "none";
  console.error(`[concierge-proxy] ${method} ${path} -> ${upstream.status} (request ${requestId})`);
  if (upstream.status === 401 || upstream.status >= 500) {
    // A 401 here means this server's key is wrong: a configuration problem, not the visitor's.
    return errorResponse(502, "The support service is unavailable. Please try again.");
  }
  const response = errorResponse(upstream.status);
  const retryAfter = upstream.headers.get("retry-after");
  if (retryAfter) {
    response.headers.set("retry-after", retryAfter);
  }
  return response;
}
