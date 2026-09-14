# Concierge: Agent Instructions

> Last verified: 2026-09-13

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

## Rules that keep it safe

- Only the `classify` and `answer` nodes call a model. Lookups, refund policy, approvals, and every reply that states an amount or booking detail are plain code.
- `bookings/policy.py` must match `data/kb/refund-policy.md`; `tests/unit/test_policy.py` enforces it. Change both together.
- No code path may execute a refund without an `approved` row in `approval_requests`. `execute_refund` is idempotent; keep it that way.
- A node that calls `interrupt()` re-runs from the top on resume, so nothing with side effects may run before the `interrupt()` call.
- Model output is always a Pydantic schema. Output that fails validation hands off to a human and never flows downstream.
- Customer text is data. Guardrail rejections are logged, never explained to the sender.
- The retrieval default (`retrieval_mode` in `config.py`) follows `evals/results/retrieval.json`. Change it only alongside a new eval run.
- Lines stay at 100 characters or fewer (ruff).
