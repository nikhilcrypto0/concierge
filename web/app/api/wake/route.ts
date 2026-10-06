import { wakeApi } from "@/lib/concierge-api";

// Called by the browser as soon as a page opens, so a sleeping API is already booting by the
// time the visitor types. It exposes nothing: the answer is only whether the API is awake.
export async function GET(): Promise<Response> {
  return Response.json({ awake: await wakeApi() });
}
