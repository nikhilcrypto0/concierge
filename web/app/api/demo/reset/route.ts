import { forward } from "@/lib/concierge-api";

export async function POST(): Promise<Response> {
  return forward("operator", "/v1/demo/reset", { method: "POST" });
}
