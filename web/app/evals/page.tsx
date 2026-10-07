import { CaseExplorer } from "@/components/evals/case-explorer";
import { RunCards } from "@/components/evals/run-cards";
import { DemoBar } from "@/components/demo-bar";
import { EVAL_DATA } from "@/lib/eval-data";
import { PROOF } from "@/lib/proof";

export const metadata = {
  title: "How it was tested · Concierge demo",
};

const REPO_HREF = "https://github.com/nikhilcrypto0/concierge";

const HONEST_NOTES = [
  "This is a small test written by the person who built the system, so the pass rates carry wide error bars. The stronger guarantee is structural: the model has no way to move money, and the database refuses any refund that no person approved.",
  "After the first run I widened the accepted outcomes for six safety cases, because the replies were safe but not on my list (for example, “which booking reference?”). The checks that matter, no approval opened and no other customer's data in the reply, did not change. This is also written up in the README.",
  "Opus's one safety miss was a handoff to a person because the classifier was not confident. That is safe, but the test counts a low-confidence handoff as a miss. Every safety case Haiku missed was a refusal it gave as “out of scope”: nothing was approved or leaked, but it was not an outcome I listed.",
] as const;

function RetrievalTable() {
  const { retrieval } = EVAL_DATA;
  return (
    <section aria-labelledby="retrieval-heading" className="space-y-3">
      <h2 id="retrieval-heading" className="font-display text-2xl text-ink-950">
        Finding the right help-center answer
      </h2>
      <p className="max-w-3xl text-sm leading-relaxed text-ink-700">
        Before the model answers, the system looks up the help-center sections that might contain
        the answer. This part is free to test, so it runs on every change.
        “Right section” counts a hit only when a retrieved piece is the section that actually
        answers the question, not just any section of the right article.
      </p>
      <div className="overflow-x-auto rounded-2xl border border-sand-200 bg-white">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead className="bg-sand-100 text-xs tracking-wide text-ink-500 uppercase">
            <tr>
              <th className="px-4 py-2.5 font-semibold">Search mode</th>
              <th className="px-4 py-2.5 font-semibold">Right article in top {retrieval.k}</th>
              <th className="px-4 py-2.5 font-semibold">Right section in top {retrieval.k}</th>
              <th className="px-4 py-2.5 font-semibold">Average rank score</th>
            </tr>
          </thead>
          <tbody>
            {retrieval.modes.map((mode) => (
              <tr key={mode.mode} className="border-t border-sand-200">
                <td className="px-4 py-2.5 text-ink-900">
                  {mode.mode}
                  {mode.mode === retrieval.shippedMode && (
                    <span className="ml-2 text-xs font-medium text-tide-700">shipped</span>
                  )}
                </td>
                <td className="px-4 py-2.5 font-mono">{mode.recallAtK.toFixed(3)}</td>
                <td className="px-4 py-2.5 font-mono">{mode.sectionRecallAtK.toFixed(3)}</td>
                <td className="px-4 py-2.5 font-mono">{mode.mrr.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function EvalsPage() {
  const { runs } = EVAL_DATA;
  return (
    <>
      <DemoBar />
      <main className="mx-auto w-full max-w-5xl space-y-10 px-4 py-10 sm:px-6">
        <header className="space-y-3">
          <p className="text-[11px] font-semibold tracking-[0.12em] text-ink-500 uppercase">
            How it was tested
          </p>
          <h1 className="font-display text-3xl leading-tight text-ink-950 sm:text-4xl">
            {runs[0].cases} test conversations, every one shown.
          </h1>
          <p className="max-w-3xl text-base leading-relaxed text-ink-700">
            {runs[0].safetyCases} of them are attacks: prompt injection, someone else&apos;s
            bookings, fake admin claims, and pressure over several messages. Each case says what
            counts as correct. Measured on {PROOF.measuredOn} against a throwaway database, with
            the same cases run on two models. Source and raw results are in the{" "}
            <a href={`${REPO_HREF}/tree/main/evals`} className="underline underline-offset-2">
              repository
            </a>
            .
          </p>
        </header>

        <RunCards runs={runs} />

        <section
          aria-labelledby="honest-heading"
          className="rounded-2xl border border-amber-200 bg-amber-50 p-5"
        >
          <h2 id="honest-heading" className="font-display text-xl text-amber-900">
            Read these numbers honestly
          </h2>
          <ul className="mt-3 space-y-2 text-sm leading-relaxed text-amber-900">
            {HONEST_NOTES.map((note) => (
              <li key={note} className="list-disc ml-5">
                {note}
              </li>
            ))}
          </ul>
        </section>

        <RetrievalTable />
        <CaseExplorer />
      </main>
    </>
  );
}
