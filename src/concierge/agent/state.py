"""Graph state. Everything here is checkpointed to Postgres after every step.

`messages` accumulates across turns; the per-turn fields are reset by the guard node at the
start of each turn so a previous turn's intent or booking never leaks into the next one.
"""

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Outcome = Literal[
    "blocked",
    "answered",
    "no_answer",
    "out_of_scope",
    "handoff",
    "needs_booking_reference",
    "booking_not_found",
    "booking_status",
    "refund_ineligible",
    "refund_pending_approval",
    "refund_completed",
    "refund_rejected",
]

# Why a turn went to a human. The first two are expected product behavior; the rest mean
# something failed or needs attention, and dashboards and evals must be able to tell them apart.
HandoffReason = Literal[
    "customer_request",
    "completed_service_refund",
    "low_confidence",
    "budget",
    "classifier_unavailable",
    "answerer_unavailable",
    "refund_conflict",
]

PER_TURN_RESET: dict[str, Any] = {
    "intent": None,
    "confidence": 0.0,
    "booking_reference": None,
    "search_query": "",
    "sources": [],
    "booking": None,
    "refund": None,
    "outcome": None,
    "handoff_reason": None,
    "reply": "",
}


class ConversationState(TypedDict, total=False):
    conversation_id: str
    customer_email: str
    messages: Annotated[list[AnyMessage], add_messages]

    user_input: str
    intent: str | None
    confidence: float
    booking_reference: str | None
    search_query: str
    sources: list[dict[str, str]]
    booking: dict[str, Any] | None
    refund: dict[str, Any] | None
    outcome: Outcome | None
    handoff_reason: HandoffReason | None
    reply: str
