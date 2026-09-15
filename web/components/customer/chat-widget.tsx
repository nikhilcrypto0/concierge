"use client";

import { useEffect, useRef } from "react";

import type { ChatController, ChatItem } from "@/hooks/use-chat";
import { Pill } from "@/components/ui/pill";
import { HANDOFF_COPY } from "@/lib/format";
import type { Persona } from "@/lib/personas";

const SUGGESTIONS = [
  "How long do refunds take to reach my card?",
  "Cancel BK-1042 and refund me",
  "Are your plumbers licensed?",
] as const;

function TypingDots() {
  return (
    <span className="flex items-center gap-1 px-1" aria-label="Assistant is typing">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="typing-dot size-1.5 rounded-full bg-ink-300"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

/** `waiting` means this is the latest reply and a human has not decided yet. */
function OutcomeCard({ item, waiting }: { item: ChatItem; waiting: boolean }) {
  if (waiting) {
    return (
      <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
        <p className="flex items-center gap-2 text-xs font-semibold text-amber-700">
          <span className="size-1.5 animate-pulse rounded-full bg-amber-700" />
          Waiting for a support lead
        </p>
        <p className="mt-1 text-xs text-ink-700">
          The assistant cannot issue this refund. A person has to approve it first.
        </p>
      </div>
    );
  }
  if (item.outcome === "refund_completed") {
    return (
      <div className="mt-2 rounded-xl border border-moss-200 bg-moss-50 p-3">
        <p className="text-xs font-semibold text-moss-700">Refund approved by a support lead</p>
      </div>
    );
  }
  if (item.outcome === "refund_rejected") {
    return (
      <div className="mt-2 rounded-xl border border-rose-200 bg-rose-50 p-3">
        <p className="text-xs font-semibold text-rose-700">Refund declined by a support lead</p>
      </div>
    );
  }
  if (item.outcome === "handoff" && item.handoffReason) {
    return (
      <div className="mt-2">
        <Pill tone="sand">{HANDOFF_COPY[item.handoffReason] ?? "Handed to a person"}</Pill>
      </div>
    );
  }
  return null;
}

function Message({ item, waiting }: { item: ChatItem; waiting: boolean }) {
  if (item.role === "customer") {
    return (
      <li className="animate-rise-in flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-tide-600 px-3.5 py-2.5 text-sm text-white">
          {item.content}
        </p>
      </li>
    );
  }

  return (
    <li className="animate-rise-in flex flex-col items-start">
      <div className="max-w-[92%] rounded-2xl rounded-bl-sm border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink-900 shadow-sm">
        <p className="whitespace-pre-wrap">{item.content}</p>
        <OutcomeCard item={item} waiting={waiting} />
        {item.sources && item.sources.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5 border-t border-sand-200 pt-2">
            {item.sources.map((source) => (
              <li key={source.id}>
                <Pill tone="tide" className="font-normal">
                  {source.title}: {source.heading}
                </Pill>
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

interface ChatWidgetProps {
  persona: Persona;
  chat: ChatController;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  input: string;
  onInputChange: (value: string) => void;
}

export function ChatWidget({
  persona,
  chat,
  open,
  onOpenChange,
  input,
  onInputChange,
}: ChatWidgetProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [chat.messages.length, chat.sending]);

  const submit = () => {
    const text = input;
    onInputChange("");
    void chat.send(text);
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => onOpenChange(true)}
        className="fixed right-5 bottom-5 z-40 flex items-center gap-2 rounded-full bg-ink-950 py-3 pr-5 pl-4 text-sm font-medium text-sand-50 shadow-lg transition-transform hover:-translate-y-0.5"
      >
        <span className="grid size-6 place-items-center rounded-full bg-tide-600 text-[11px]">
          TA
        </span>
        Chat with us
      </button>
    );
  }

  // The newest reply is the one a pending approval belongs to.
  const waitingId = chat.awaitingApproval ? chat.messages.at(-1)?.id : undefined;

  return (
    <section
      aria-label="Tidewell support chat"
      className="fixed inset-x-0 bottom-0 z-40 flex h-[min(78vh,620px)] flex-col overflow-hidden border border-sand-300 bg-sand-50 shadow-[0_30px_80px_-40px_rgba(11,33,36,0.8)] sm:inset-x-auto sm:right-5 sm:bottom-5 sm:w-[400px] sm:rounded-2xl"
    >
      <header className="flex items-center gap-3 border-b border-sand-200 bg-white px-4 py-3">
        <span className="grid size-9 place-items-center rounded-full bg-tide-600 text-sm font-semibold text-white">
          TA
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink-900">Tidewell Assistant</p>
          <p className="truncate text-xs text-ink-500">
            Answers from our help center, {persona.name.split(" ")[0]}
          </p>
        </div>
        <button
          type="button"
          onClick={chat.startNewConversation}
          className="rounded-full px-2 py-1 text-xs text-ink-500 transition-colors hover:bg-sand-100 hover:text-ink-900"
        >
          New chat
        </button>
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="Close chat"
          className="rounded-full px-2 py-1 text-lg leading-none text-ink-500 transition-colors hover:bg-sand-100 hover:text-ink-900"
        >
          ×
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {chat.messages.length === 0 && (
          <div className="rounded-2xl border border-dashed border-sand-300 bg-white/60 p-4">
            <p className="text-sm text-ink-700">
              Hi {persona.name.split(" ")[0]}, ask about a booking, our policies, or a refund.
            </p>
            <ul className="mt-3 space-y-2">
              {SUGGESTIONS.map((suggestion) => (
                <li key={suggestion}>
                  <button
                    type="button"
                    onClick={() => void chat.send(suggestion)}
                    className="w-full rounded-xl border border-sand-200 bg-white px-3 py-2 text-left text-sm text-ink-700 transition-colors hover:border-tide-600 hover:text-tide-700"
                  >
                    {suggestion}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <ul className="space-y-3">
          {chat.messages.map((item) => (
            <Message key={item.id} item={item} waiting={item.id === waitingId} />
          ))}
          {chat.sending && (
            <li className="flex justify-start">
              <div className="rounded-2xl rounded-bl-sm border border-sand-200 bg-white px-3 py-3">
                <TypingDots />
              </div>
            </li>
          )}
        </ul>

        {chat.error && (
          <p role="status" className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {chat.error}
          </p>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="border-t border-sand-200 bg-white p-3"
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
      >
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            rows={1}
            maxLength={2000}
            placeholder="Ask about a booking or a refund"
            aria-label="Message"
            className="max-h-28 min-h-10 flex-1 resize-none rounded-xl border border-sand-300 bg-sand-50 px-3 py-2 text-sm text-ink-900 placeholder:text-ink-300 focus:border-tide-600 focus:outline-none"
          />
          <button
            type="submit"
            disabled={chat.sending || input.trim().length === 0}
            className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm font-medium text-sand-50 transition-colors enabled:hover:bg-tide-700 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </section>
  );
}
