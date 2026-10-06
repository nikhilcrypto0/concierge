import { forward } from "@/lib/concierge-api";

// Aggregate cost figures from the API's token ledger (no customer or chat data), shown on the
// landing page. It uses the client key, like the chat, so it needs no login.
export async function GET(): Promise<Response> {
  return forward("client", "/v1/stats");
}
