"""HTTP service: startup wiring, request correlation, chat, transcripts, and human approvals.

Run: uv run uvicorn --factory concierge.api.app:create_app
"""

import asyncio
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph

from concierge.agent.graph import build_graph, resume_after_decision, run_turn
from concierge.agent.nodes import AgentDeps, pending_approval_reply
from concierge.api.schemas import (
    ApprovalDetail,
    ApprovalOut,
    BookingOut,
    ChatRequest,
    ChatResponse,
    DecisionRequest,
    DecisionResponse,
    Source,
    TranscriptMessage,
)
from concierge.api.security import Principal, SlidingWindowRateLimiter, require_role
from concierge.bookings.repository import SupportRepository
from concierge.budget import PostgresUsageLedger
from concierge.config import Settings, get_settings
from concierge.db import create_pool, run_migrations
from concierge.llm import AnthropicSupportLLM, SupportLLM
from concierge.locks import conversation_lock
from concierge.observability import (
    configure_logging,
    init_tracing,
    shutdown_tracing,
    trace_session,
    tracing_callbacks,
)
from concierge.retrieval.embeddings import Embedder, FastEmbedEmbedder
from concierge.retrieval.ingest import DEMO_SEED
from concierge.retrieval.search import KnowledgeBase

log = structlog.get_logger(__name__)

_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
MAX_BODY_BYTES = 64 * 1024
ClientPrincipal = Annotated[Principal, Depends(require_role("client"))]
OperatorPrincipal = Annotated[Principal, Depends(require_role("operator"))]
CustomerEmail = Annotated[str, Query(max_length=254)]


class ConversationBusyError(HTTPException):
    """Raised as a class so every request gets a fresh exception object."""

    def __init__(self) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "conversation is busy, retry shortly")


BUSY = ConversationBusyError


def _thread(conversation_id: UUID) -> RunnableConfig:
    return {"configurable": {"thread_id": str(conversation_id)}}


async def _transcript(
    graph: CompiledStateGraph[Any, Any, Any, Any], conversation_id: UUID
) -> list[TranscriptMessage]:
    snapshot = await graph.aget_state(_thread(conversation_id))
    return [
        TranscriptMessage(role="customer" if m.type == "human" else "assistant",
                          content=str(m.content))
        for m in snapshot.values.get("messages", [])
    ]


def create_app(
    settings: Settings | None = None,
    llm: SupportLLM | None = None,
    embedder: Embedder | None = None,
) -> FastAPI:
    """App factory. Tests inject a fake LLM/embedder; production uses Claude and fastembed."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level, json_logs=settings.environment == "prod")
        init_tracing(settings)
        pool = create_pool(settings.database_url, settings.db_pool_min, settings.db_pool_max)
        await pool.open(wait=True, timeout=30)
        try:
            async with pool.connection() as conn:
                await run_migrations(conn)
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            repository = SupportRepository(pool)
            knowledge = KnowledgeBase(
                pool,
                embedder or FastEmbedEmbedder(
                    settings.embedding_model,
                    settings.embedding_dimensions,
                    settings.embedding_cache_dir,
                ),
                default_mode=settings.retrieval_mode,
                keyword_weight=settings.retrieval_keyword_weight,
            )
            deps = AgentDeps(
                llm=llm or AnthropicSupportLLM(settings),
                knowledge=knowledge,
                bookings=repository,
                ledger=PostgresUsageLedger(
                    pool, settings.max_tokens_per_conversation, settings.max_tokens_per_day
                ),
                max_input_chars=settings.max_input_chars,
                top_k=settings.retrieval_top_k,
                min_similarity=settings.retrieval_min_similarity,
                confidence_floor=settings.classification_confidence_floor,
            )
            app.state.settings = settings
            app.state.pool = pool
            app.state.repository = repository
            app.state.graph = build_graph(deps, checkpointer)
            app.state.rate_limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute)
            log.info("app.started", environment=settings.environment,
                     model=settings.primary_model, tracing=settings.tracing_enabled,
                     demo_mode=settings.demo_mode)
            yield
        finally:
            await pool.close()
            shutdown_tracing(settings)

    public_docs = settings.environment != "prod"
    app = FastAPI(
        title="Concierge",
        version="0.1.0",
        description="Customer support agent with human approval for refunds.",
        lifespan=lifespan,
        docs_url="/docs" if public_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if public_docs else None,
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _REQUEST_ID.match(supplied) else uuid4().hex
        request.state.request_id = request_id
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            # Reject before the body is buffered: schema length limits only apply after parsing.
            # Chunked uploads without a length header should be capped at the reverse proxy.
            return JSONResponse(
                {"detail": "request body too large", "request_id": request_id},
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                headers={"X-Request-ID": request_id},
            )
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, method=request.method, path=request.url.path
        )
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request.failed")
            response = JSONResponse(
                {"detail": "internal error", "request_id": request_id},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        response.headers["X-Request-ID"] = request_id
        log.info("request.completed", status=response.status_code,
                 duration_ms=round((time.perf_counter() - started) * 1000, 1))
        return response

    @app.get("/", include_in_schema=False)
    async def root() -> Response:
        if public_docs:
            return RedirectResponse("/docs")
        return JSONResponse({"service": "concierge"})

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz(request: Request) -> JSONResponse:
        try:
            async with request.app.state.pool.connection() as conn:
                await conn.execute("SELECT 1")
        except Exception:
            log.warning("readiness.database_unavailable")
            return JSONResponse({"status": "unavailable"}, status.HTTP_503_SERVICE_UNAVAILABLE)
        return JSONResponse({"status": "ready"})

    @app.post("/v1/chat", response_model=ChatResponse, tags=["customer"])
    async def chat(body: ChatRequest, request: Request, _: ClientPrincipal) -> ChatResponse:
        state = request.app.state
        repository: SupportRepository = state.repository
        conversation_id = body.conversation_id or uuid4()
        if not await repository.claim_conversation(conversation_id, body.customer_email):
            # Someone else's conversation looks exactly like a missing one.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
        structlog.contextvars.bind_contextvars(conversation_id=str(conversation_id))

        async with conversation_lock(state.pool, conversation_id) as acquired:
            if not acquired:
                raise BUSY
            paused = await state.graph.aget_state(_thread(conversation_id))
            if paused.interrupts:
                # The run is waiting on a human. Never start a new run on top of it. Re-opening
                # the approval request is idempotent and self-heals a crash between pause and
                # insert.
                payload = dict(paused.interrupts[0].value)
                await _open_approval(repository, conversation_id, payload)
                return _chat_response(request, conversation_id, "pending_approval",
                                      pending_approval_reply(payload),
                                      "refund_pending_approval", "refund_request", [], None)

            with trace_session(settings, conversation_id):
                result = await run_turn(state.graph, conversation_id, body.customer_email,
                                        body.message, tracing_callbacks(settings))
            if result.approval_request is not None:
                await _open_approval(repository, conversation_id, result.approval_request)
        log.info("chat.turn", outcome=result.outcome, intent=result.intent,
                 handoff_reason=result.handoff_reason)
        return _chat_response(request, conversation_id, result.status, result.reply,
                              result.outcome, result.intent, result.sources,
                              result.handoff_reason)

    @app.get("/v1/conversations/{conversation_id}/messages",
             response_model=list[TranscriptMessage], tags=["customer"])
    async def transcript(
        conversation_id: UUID,
        customer_email: CustomerEmail,
        request: Request,
        _: ClientPrincipal,
    ) -> list[TranscriptMessage]:
        owner = await request.app.state.repository.conversation_owner(conversation_id)
        if owner is None or owner.lower() != customer_email.strip().lower():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
        return await _transcript(request.app.state.graph, conversation_id)

    @app.get("/v1/bookings", response_model=list[BookingOut], tags=["customer"])
    async def my_bookings(
        customer_email: CustomerEmail, request: Request, _: ClientPrincipal
    ) -> list[BookingOut]:
        repository: SupportRepository = request.app.state.repository
        bookings = await repository.list_bookings_for_customer(customer_email.strip())
        return [BookingOut.from_domain(b) for b in bookings]

    @app.get("/v1/approvals", response_model=list[ApprovalOut], tags=["operator"])
    async def list_approvals(
        request: Request,
        _: OperatorPrincipal,
        status_filter: Annotated[
            Literal["pending", "approved", "rejected"], Query(alias="status")
        ] = "pending",
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[ApprovalOut]:
        approvals = await request.app.state.repository.list_approvals(status_filter, limit)
        return [ApprovalOut.from_domain(a) for a in approvals]

    @app.get("/v1/approvals/{approval_id}", response_model=ApprovalDetail, tags=["operator"])
    async def approval_detail(
        approval_id: UUID, request: Request, _: OperatorPrincipal
    ) -> ApprovalDetail:
        repository: SupportRepository = request.app.state.repository
        approval = await repository.get_approval(approval_id)
        if approval is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "approval not found")
        booking = await repository.get_booking(approval.booking_reference)
        return ApprovalDetail(
            approval=ApprovalOut.from_domain(approval),
            booking=BookingOut.from_domain(booking) if booking else None,
            transcript=await _transcript(request.app.state.graph, approval.conversation_id),
        )

    @app.post("/v1/approvals/{approval_id}/decision", response_model=DecisionResponse,
              tags=["operator"])
    async def decide(
        approval_id: UUID, body: DecisionRequest, request: Request, principal: OperatorPrincipal
    ) -> DecisionResponse:
        state = request.app.state
        repository: SupportRepository = state.repository
        existing = await repository.get_approval(approval_id)
        if existing is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "approval not found")
        conversation_id = existing.conversation_id
        structlog.contextvars.bind_contextvars(conversation_id=str(conversation_id))

        async with conversation_lock(state.pool, conversation_id) as acquired:
            if not acquired:
                raise BUSY
            decided = await repository.decide_approval(approval_id, body.approve,
                                                       principal.name, body.note)
            if decided is None:
                current = await repository.get_approval(approval_id) or existing
                paused = await state.graph.aget_state(_thread(conversation_id))
                if not paused.interrupts:
                    raise HTTPException(status.HTTP_409_CONFLICT,
                                        f"approval already {current.status}")
                # Decided earlier but the run never resumed (e.g. a crash): finish it now.
                # Safe, because executing the refund is idempotent.
                decided = current
            log.info("approval.decided", approval_id=str(decided.id), status=decided.status)
            with trace_session(settings, conversation_id):
                result = await resume_after_decision(state.graph, conversation_id, decided.id,
                                                     tracing_callbacks(settings))
        final = await repository.get_approval(decided.id) or decided
        return DecisionResponse(
            approval=ApprovalOut.from_domain(final),
            outcome=result.outcome,
            customer_reply=result.reply,
        )

    @app.post("/v1/demo/reset", tags=["operator"])
    async def reset_demo(request: Request, principal: OperatorPrincipal) -> dict[str, str]:
        if not settings.demo_mode:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
        seed_sql = await asyncio.to_thread(DEMO_SEED.read_text)
        await request.app.state.repository.reset_demo_data(seed_sql)
        log.warning("demo.reset", principal=principal.name)
        return {"status": "reset"}

    return app


async def _open_approval(
    repository: SupportRepository, conversation_id: UUID, payload: dict[str, Any]
) -> None:
    approval = await repository.open_approval_request(
        conversation_id, str(payload["booking_reference"]), int(payload["amount_cents"]),
        str(payload["policy_reason"]),
    )
    log.info("approval.requested", approval_id=str(approval.id),
             amount_cents=approval.amount_cents)


def _chat_response(
    request: Request,
    conversation_id: UUID,
    status_: Literal["completed", "pending_approval"],
    reply: str,
    outcome: str | None,
    intent: str | None,
    sources: list[dict[str, str]],
    handoff_reason: str | None,
) -> ChatResponse:
    return ChatResponse(
        conversation_id=conversation_id,
        status=status_,
        reply=reply,
        outcome=outcome,
        intent=intent,
        handoff_reason=handoff_reason,
        sources=[Source(**s) for s in sources],
        request_id=request.state.request_id,
    )
