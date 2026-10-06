import { LiveStats } from "@/components/customer/live-stats";
import { Pill } from "@/components/ui/pill";
import { PROOF, PROOF_HREF } from "@/lib/proof";

const README_HREF = "https://github.com/nikhilcrypto0/concierge#readme";

/** How many of the three walkthrough steps the visitor has actually completed. */
export type TourProgress = 0 | 2 | 3;

interface PitchBandProps {
  /** Opens the chat with the refund prompt filled in. */
  onTry: () => void;
  progress: TourProgress;
}

const STATS = [
  { value: `${PROOF.passed} of ${PROOF.conversations}`, label: "test conversations passed" },
  { value: `${PROOF.safetyPassed} of ${PROOF.safetyCases}`, label: "safety cases passed" },
  { value: String(PROOF.refundsWithoutHuman), label: "refunds paid without a person" },
  { value: `$${PROOF.usdPerConversation}`, label: "average cost per conversation" },
] as const;

const STEPS = [
  "Ask the assistant to cancel BK-1042 and refund you.",
  "It applies the written refund policy, then waits. Nothing is paid yet.",
  "A support lead approves, and your chat updates on its own. In this demo you can play the support lead.",
] as const;

export function PitchBand({ onTry, progress }: PitchBandProps) {
  return (
    <section aria-labelledby="pitch-heading" className="mx-auto w-full max-w-7xl px-4 pt-8 sm:px-6">
      <div className="rounded-3xl bg-ink-950 px-6 py-8 text-sand-50 sm:px-10 sm:py-10">
        <Pill tone="ink" className="ring-tide-500/50">
          Concierge · AI support agent · live demo
        </Pill>
        <h2
          id="pitch-heading"
          className="mt-4 max-w-3xl font-display text-3xl leading-tight sm:text-4xl lg:text-5xl"
        >
          A support agent that can&apos;t move money on its own.
        </h2>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-sand-200 sm:text-lg">
          Concierge answers from your help center with citations, applies your refund policy in
          code, and waits for a person before any refund is paid. Try it on the demo company
          below.
        </p>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={onTry}
            className="rounded-full bg-tide-500 px-5 py-3 text-sm font-semibold text-ink-950 transition-colors hover:bg-tide-100"
          >
            Try it in 60 seconds
          </button>
          <a
            href={README_HREF}
            className="rounded-full border border-sand-50/30 px-5 py-3 text-sm font-medium text-sand-50 transition-colors hover:border-tide-100 hover:text-tide-100"
          >
            How it works
          </a>
          <a
            href="#break-it"
            className="px-2 py-3 text-sm font-medium text-tide-100 underline underline-offset-4 transition-colors hover:text-sand-50"
          >
            Try to break it
          </a>
        </div>

        <dl className="mt-8 grid grid-cols-2 gap-4 border-t border-sand-50/15 pt-6 lg:grid-cols-4">
          {STATS.map((stat) => (
            <div key={stat.label}>
              <dd className="font-mono text-2xl text-tide-100 sm:text-3xl">{stat.value}</dd>
              <dt className="mt-1 text-xs leading-snug text-sand-300">{stat.label}</dt>
            </div>
          ))}
        </dl>
        <p className="mt-4 text-xs leading-relaxed text-sand-300">
          Measured on {PROOF.measuredOn} with {PROOF.model} on {PROOF.conversations} test
          conversations.{" "}
          <a href={PROOF_HREF} className="underline underline-offset-2 hover:text-tide-100">
            How it was measured
          </a>
        </p>
        <LiveStats />

        <ol className="mt-6 grid gap-3 border-t border-sand-50/15 pt-6 sm:grid-cols-3">
          {STEPS.map((step, index) => {
            const done = index < progress;
            return (
              <li
                key={step}
                className={`flex gap-3 text-sm leading-snug ${done ? "text-sand-50" : "text-sand-200"}`}
              >
                <span
                  aria-hidden
                  className={`grid size-6 shrink-0 place-items-center rounded-full font-mono text-xs transition-colors ${
                    done ? "bg-tide-500 text-ink-950" : "bg-sand-50/10 text-tide-100"
                  }`}
                >
                  {done ? "✓" : index + 1}
                </span>
                <span>
                  {step}
                  {done && <span className="sr-only"> (done)</span>}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
      <p className="mt-3 text-center text-xs text-ink-500">
        Below is the demo company, Tidewell Home Services (fictional), where the assistant works.
      </p>
    </section>
  );
}
