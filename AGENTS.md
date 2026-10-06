# Concierge: Agent Instructions

> Last verified: 2026-10-05

Customer support agent built for production: a LangGraph workflow over Claude, Postgres with pgvector, human approval for refunds, and evals in CI. This is a public portfolio project, so full production rigor applies: tests, types, evals, and security review.

## Commands

- Install: `uv sync`
- Lint and types: `uv run ruff check src tests evals` and `uv run mypy src`
- Unit tests: `uv run pytest tests/unit -q`
- Integration tests: `uv run pytest tests/integration -q`. Needs Postgres with pgvector at `TEST_DATABASE_URL` (default `postgresql://localhost:5432/concierge_test`). The database name must end in `_test` because the suite drops its schema.
- Load help center and demo bookings: `uv run concierge-ingest --seed-demo` (clears conversations and approvals; refused when `ENVIRONMENT=prod`)
- API: `uv run uvicorn --factory concierge.api.app:create_app --reload`, docs at `/docs`
- MCP server (stdio, read-only): `uv run concierge-mcp`
- Retrieval eval (free): `uv run python evals/run_retrieval_eval.py`
- Agent eval (calls Claude and costs money, so ask before running): `uv run python evals/run_agent_eval.py`

## Demo UI (`web/`)

A Next.js app with two screens: the Tidewell customer site with the chat assistant, and the support console where a human approves refunds. It never touches the database. It calls the API through its own `/api` routes, which attach the API keys server-side.

- Install: `cd web && npm install`
- Dev server (expects the API at `CONCIERGE_API_URL`): `npm run dev`
- Lint, types, build: `npm run lint`, `npx next typegen && npx tsc --noEmit`, `npm run build`
- Settings: copy `web/.env.example` to `web/.env.local`

Rules:

- No API key may reach the browser: nothing key-related gets a `NEXT_PUBLIC_` prefix, and `web/lib/concierge-api.ts` stays `server-only`.
- The browser sends a persona id, never an email. `web/lib/personas.ts` maps the id to an email on the server, so a visitor cannot ask about someone else's bookings.
- Route handlers validate every input with zod before forwarding, and upstream errors become friendly messages, never raw detail.
- `POST /v1/demo/reset` exists only when `DEMO_MODE=true`. It keeps `llm_usage`, so resetting cannot clear the daily token budget.
- Every figure in the console is derived from approval rows the page already fetched (`web/lib/console-metrics.ts`). No number on screen is invented, and none of them need a stats endpoint. Keep it that way: a dashboard that shows a number nobody can trace is worse than one that shows nothing.
- Elapsed times come from the `useNow` store, never `Date.now()` during render, which React's purity rule rejects.
- `/console/sample` is the public view-only tour. It must stay fixture-only (`web/lib/sample-console.ts`): no `fetch`, no `forward`, no operator key, no live approvals. Showing live approvals publicly would show other visitors' chats. It reuses `ConsoleView` with `sample` set, which hides the decision form and the reset button.
- The console needs the operator password (`web/lib/operator-session.ts`: signed HttpOnly cookie). Every route that forwards as `operator` must call `requireOperator()` first, or a visitor can approve refunds.

## Rules that keep it safe

- Only the `classify` and `answer` nodes call a model. Lookups, refund policy, approvals, and every reply that states an amount or booking detail are plain code.
- `bookings/policy.py` must match `data/kb/refund-policy.md`; `tests/unit/test_policy.py` enforces it. Change both together.
- No code path may execute a refund without an `approved` row in `approval_requests`. `execute_refund` is idempotent; keep it that way.
- A node that calls `interrupt()` re-runs from the top on resume, so nothing with side effects may run before the `interrupt()` call.
- Model output is always a Pydantic schema. Output that fails validation hands off to a human and never flows downstream.
- Customer text is data. Guardrail rejections are logged, never explained to the sender.
- Retrieved help-center text is data too. Every passage goes through `sanitize_document` in `_trusted_sources` before it enters a prompt, quarantined passages are never cited, and `tests/unit/test_document_hygiene.py` asserts no shipped article is quarantined. Do not build prompt text from retrieved content any other way.
- A reviewer may approve LESS than the policy amount, never more. `approved_amount_cents` is capped by the API (422) and by CHECK constraints in migration 002; `execute_refund` pays `authorised_cents`. The customer's reply is filled from stored amounts and must keep the phrase "has been approved", which the web UI keys on.
- `POST /v1/demo/decide` lets a public demo visitor decide THEIR OWN pending request. It must stay demo-mode only (404 otherwise), scoped to the open request on a conversation owned by the asking customer, recorded with the reviewer `demo-visitor`, and routed through `apply_decision`, the single code path that moves money. Never enable demo mode on real data, and never widen this route. The web app shows its buttons only when `GET /v1/stats` reports `demo_mode: true`.
- Money is guarded in the database too: migration 003 puts a trigger on `actions` so a refund record cannot exist without an approved request, for that booking, within the authorised amount. Do not weaken or drop it, and add a migration (never edit an applied one) for any change. When you change a guard, a threat or a boundary, update `docs/THREAT_MODEL.md` in the same PR.
- Model prices live only in `src/concierge/pricing.py`. The agent eval and the live `GET /v1/stats` both use it, so the measured and the live cost figures cannot disagree. An unpriced model is charged at the highest tier and reported, never silently priced low.
- Changing the API contract: the API is a manual deploy on Render while the web app deploys on merge, so keep the web app compatible with the previous API (send new fields only when needed) and redeploy the API right after merging.
- The retrieval default (`retrieval_mode` in `config.py`) follows `evals/results/retrieval.json`. Change it only alongside a new eval run.
- Lines stay at 100 characters or fewer (ruff).
