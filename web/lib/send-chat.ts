import { api, ApiRequestError } from "@/lib/api-client";
import type { PersonaId } from "@/lib/personas";
import type { ChatReply } from "@/lib/types";

// The demo's free API host sleeps when idle and takes up to a minute to boot. While it does, the
// site answers 502, 503 or 504; retry quietly instead of showing an error.
const API_STARTING_STATUSES = new Set([502, 503, 504]);
const WAKE_RETRY_DELAY_MS = 8_000;
const MAX_WAKE_RETRIES = 8;

export const WAKING_NOTICE =
  "The assistant was asleep and is waking up. This can take up to a minute, so hang on.";

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

interface ChatBody {
  persona: PersonaId;
  message: string;
  conversationId?: string;
}

/** Sends one chat turn, retrying while the API host wakes up. Any other error is thrown as is. */
export async function sendChatWithWakeRetry(
  body: ChatBody,
  onWaking: () => void,
): Promise<ChatReply> {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await api.chat(body);
    } catch (failure: unknown) {
      const starting =
        failure instanceof ApiRequestError && API_STARTING_STATUSES.has(failure.status);
      if (!starting || attempt >= MAX_WAKE_RETRIES) throw failure;
      onWaking();
      await wait(WAKE_RETRY_DELAY_MS);
    }
  }
}
