import { forward } from "@/lib/concierge-api";
import { requireOperator } from "@/lib/operator-session";

export async function POST(): Promise<Response> {
  const denied = await requireOperator();
  if (denied) return denied;
  return forward("operator", "/v1/demo/reset", { method: "POST" });
}
