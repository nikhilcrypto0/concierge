# Concierge: Agent Instructions

> Last verified: 2026-09-15

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
- The console has no login: it is demo-only. A public deployment needs operator auth first.

## Rules that keep it safe

- Only the `classify` and `answer` nodes call a model. Lookups, refund policy, approvals, and every reply that states an amount or booking detail are plain code.
- `bookings/policy.py` must match `data/kb/refund-policy.md`; `tests/unit/test_policy.py` enforces it. Change both together.
- No code path may execute a refund without an `approved` row in `approval_requests`. `execute_refund` is idempotent; keep it that way.
- A node that calls `interrupt()` re-runs from the top on resume, so nothing with side effects may run before the `interrupt()` call.
- Model output is always a Pydantic schema. Output that fails validation hands off to a human and never flows downstream.
- Customer text is data. Guardrail rejections are logged, never explained to the sender.
- The retrieval default (`retrieval_mode` in `config.py`) follows `evals/results/retrieval.json`. Change it only alongside a new eval run.
- Lines stay at 100 characters or fewer (ruff).
