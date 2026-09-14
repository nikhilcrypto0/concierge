"""MCP server: read-only support tools for MCP clients (Claude Code, Claude Desktop, Cursor).

Run: uv run concierge-mcp    (stdio transport)

Deliberately read-only. Refunds exist only behind the human-approval workflow in the HTTP API,
so no MCP client, and no model driving one, can move money through this server.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver import Context

from concierge.bookings.repository import SupportRepository
from concierge.config import get_settings
from concierge.db import create_pool
from concierge.guardrails import extract_booking_reference
from concierge.retrieval.embeddings import FastEmbedEmbedder
from concierge.retrieval.search import KnowledgeBase

MAX_RESULTS = 8
MAX_QUERY_CHARS = 500


@dataclass(frozen=True)
class ServerContext:
    knowledge: KnowledgeBase
    repository: SupportRepository


@asynccontextmanager
async def lifespan(server: MCPServer) -> AsyncIterator[ServerContext]:
    settings = get_settings()
    pool = create_pool(settings.database_url, max_size=4)
    await pool.open(wait=True, timeout=30)
    try:
        embedder = FastEmbedEmbedder(
            settings.embedding_model, settings.embedding_dimensions, settings.embedding_cache_dir
        )
        knowledge = KnowledgeBase(
            pool,
            embedder,
            default_mode=settings.retrieval_mode,
            keyword_weight=settings.retrieval_keyword_weight,
        )
        yield ServerContext(knowledge=knowledge, repository=SupportRepository(pool))
    finally:
        await pool.close()


mcp = MCPServer(
    "concierge",
    instructions=(
        "Read-only tools over the Tidewell Home Services help center and bookings. "
        "Refunds cannot be issued through this server."
    ),
    lifespan=lifespan,
)


@mcp.tool()
async def search_help_center(
    query: str, ctx: Context[ServerContext], limit: int = 4
) -> list[dict[str, Any]]:
    """Search Tidewell help-center articles. Returns the most relevant passages with source ids."""
    chunks = await ctx.request_context.lifespan_context.knowledge.search(
        query[:MAX_QUERY_CHARS], max(1, min(limit, MAX_RESULTS))
    )
    return [
        {
            "id": c.id,
            "title": c.doc_title,
            "heading": c.heading,
            "content": c.content,
            "similarity": round(c.similarity, 3),
        }
        for c in chunks
    ]


@mcp.tool()
async def get_booking(
    booking_reference: str, customer_email: str, ctx: Context[ServerContext]
) -> dict[str, Any]:
    """Look up a booking by reference (like BK-1042) for the customer who owns it.

    A booking that belongs to a different email is reported as not found.
    """
    reference = extract_booking_reference(booking_reference)
    if reference is None:
        return {"found": False, "error": "booking references look like BK-1042"}
    booking = await ctx.request_context.lifespan_context.repository.get_booking_for_customer(
        reference, customer_email
    )
    return {"found": True, **booking.to_public_dict()} if booking else {"found": False}


@mcp.tool()
async def list_pending_refund_approvals(ctx: Context[ServerContext]) -> list[dict[str, Any]]:
    """List refund requests waiting for a human decision. Decisions are made in the operator API."""
    approvals = await ctx.request_context.lifespan_context.repository.list_approvals("pending")
    return [
        {
            "id": str(a.id),
            "booking_reference": a.booking_reference,
            "amount": f"${a.amount_cents / 100:.2f}",
            "policy_reason": a.policy_reason,
            "created_at": a.created_at.isoformat(),
        }
        for a in approvals
    ]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
