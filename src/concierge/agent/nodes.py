"""Graph nodes. Only `classify` and `answer` call a model; every other step is plain code.

Replies that state facts about money or bookings come from templates filled with database
values, never from model output, so the assistant cannot misquote a refund amount.
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import anthropic
import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from concierge.agent.state import PER_TURN_RESET, ConversationState, HandoffReason
from concierge.bookings.models import Booking
from concierge.bookings.policy import assess_refund
from concierge.bookings.repository import ApprovalRequest, RefundConflictError
from concierge.budget import BudgetExceededError, UsageLedger
from concierge.guardrails import extract_booking_reference, sanitize
from concierge.llm import LLMOutputError, SupportLLM
from concierge.retrieval.search import RetrievedChunk, reciprocal_rank_fusion

log = structlog.get_logger(__name__)

HISTORY_WINDOW = 8
WITHHELD = "[message withheld by safety filter]"

REPLY_BLOCKED = (
    "I can help with Tidewell bookings, services, and policies. "
    "Could you tell me what you need in a different way?"
)
REPLY_OUT_OF_SCOPE = (
    "I can only help with Tidewell Home Services, like bookings, services, pricing, and "
    "policies. Is there something I can help you with there?"
)
REPLY_HANDOFF = (
    "I'm connecting you with a member of our support team. During support hours they "
    "usually reply here within 15 minutes."
)
REPLY_NO_ANSWER = (
    "I couldn't find that in our help center. Would you like me to connect you with a person?"
)
REPLY_NEEDS_REFERENCE = "Could you share your booking reference? It starts with BK, like BK-1042."
REPLY_NOT_FOUND = (
    "I couldn't find a booking with that reference on your account. "
    "Could you double-check the reference?"
)


class KnowledgeSearch(Protocol):
    async def search(self, query: str, k: int) -> list[RetrievedChunk]: ...


class BookingStore(Protocol):
    async def get_booking_for_customer(
        self, reference: str, customer_email: str
    ) -> Booking | None: ...

    async def get_approval(self, approval_id: UUID) -> ApprovalRequest | None: ...

    async def execute_refund(self, approval_id: UUID) -> bool: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AgentDeps:
    llm: SupportLLM
    knowledge: KnowledgeSearch
    bookings: BookingStore
    ledger: UsageLedger
    max_input_chars: int = 2_000
    top_k: int = 4
    min_similarity: float = 0.55
    confidence_floor: float = 0.6
    clock: Callable[[], datetime] = field(default=_utcnow)


def pending_approval_reply(payload: dict[str, Any]) -> str:
    amount = f"${int(payload['amount_cents']) / 100:.2f}"
    return (
        f"I've sent a refund request of {amount} for booking {payload['booking_reference']} "
        "to our support team for approval. You'll get a confirmation here once it's reviewed."
    )


def _format_when(iso: str) -> str:
    when = datetime.fromisoformat(iso).astimezone(UTC)
    return f"{when:%A, %B} {when.day} at {when:%H:%M} UTC"


def _handoff(reason: HandoffReason, reply: str = REPLY_HANDOFF) -> dict[str, Any]:
    log.info("handoff.requested", reason=reason)
    return {"outcome": "handoff", "handoff_reason": reason, "reply": reply}


class SupportAgentNodes:
    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps

    async def guard(self, state: ConversationState) -> dict[str, Any]:
        last = state["messages"][-1]
        raw = last.content if isinstance(last.content, str) else str(last.content)
        checked = sanitize(raw, self.deps.max_input_chars)
        update: dict[str, Any] = {**PER_TURN_RESET, "user_input": checked.text}
        if checked.injection_suspected or checked.is_empty:
            # Logged for operators, never explained to the sender.
            log.warning("guard.blocked", injection=checked.injection_suspected,
                        empty=checked.is_empty, chars=len(raw))
            update |= {"outcome": "blocked", "reply": REPLY_BLOCKED,
                       "messages": [HumanMessage(WITHHELD, id=last.id)]}
        elif checked.text != raw:
            update["messages"] = [HumanMessage(checked.text, id=last.id)]
        return update

    async def classify(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        conversation_id = UUID(state["conversation_id"])
        history = _recent(state["messages"])
        try:
            await self.deps.ledger.check(conversation_id)
            result = await self.deps.llm.classify(history, config)
            await self.deps.ledger.record(conversation_id, "classify", result.model,
                                          result.input_tokens, result.output_tokens)
        except BudgetExceededError as exc:
            log.error("budget.breach", scope=exc.scope, used=exc.used, limit=exc.limit)
            return _handoff("budget")
        except (LLMOutputError, anthropic.APIError) as exc:
            log.error("classify.failed", error=type(exc).__name__)
            return _handoff("classifier_unavailable")

        decision = result.value
        # The model may only confirm a reference that matches the real format.
        reference = extract_booking_reference(state["user_input"]) or extract_booking_reference(
            decision.booking_reference or ""
        )
        log.info("classify.done", intent=decision.intent, confidence=decision.confidence)
        if decision.confidence < self.deps.confidence_floor:
            return {**_handoff("low_confidence"), "intent": decision.intent,
                    "confidence": decision.confidence}
        return {
            "intent": decision.intent,
            "confidence": decision.confidence,
            "booking_reference": reference,
            "search_query": decision.search_query or state["user_input"],
        }

    async def _search(self, state: ConversationState) -> list[RetrievedChunk]:
        """Search with the customer's own words and the classifier's rewrite, then fuse.

        The rewrite resolves follow-ups ("and what about the fee?") but can drift: in the agent
        eval it added the company name, which matched every article's boilerplate intro and hid
        the real answer. Running both queries keeps the benefit without the failure mode.
        """
        raw = state["user_input"]
        rewrite = (state.get("search_query") or "").strip()
        queries = [raw] if not rewrite or rewrite.lower() == raw.lower() else [raw, rewrite]
        rankings = await asyncio.gather(
            *(self.deps.knowledge.search(q, self.deps.top_k) for q in queries)
        )
        best: dict[str, RetrievedChunk] = {}
        for chunk in (c for ranking in rankings for c in ranking):
            if chunk.id not in best or chunk.similarity > best[chunk.id].similarity:
                best[chunk.id] = chunk
        fused = reciprocal_rank_fusion([[c.id for c in ranking] for ranking in rankings])
        return [best[chunk_id] for chunk_id, _ in fused[: self.deps.top_k]]

    async def retrieve(self, state: ConversationState) -> dict[str, Any]:
        chunks = await self._search(state)
        top = max((c.similarity for c in chunks), default=0.0)
        if top < self.deps.min_similarity:
            log.info("retrieve.below_floor", top_similarity=round(top, 3))
            return {"outcome": "no_answer", "reply": REPLY_NO_ANSWER, "sources": []}
        return {"sources": [
            {"id": c.id, "title": c.doc_title, "heading": c.heading, "content": c.content}
            for c in chunks
        ]}

    async def answer(self, state: ConversationState, config: RunnableConfig) -> dict[str, Any]:
        conversation_id = UUID(state["conversation_id"])
        sources = state.get("sources") or []
        documents = "\n\n".join(
            f'<document id="{s["id"]}" title="{s["title"]} / {s["heading"]}">\n'
            f"{s['content']}\n</document>"
            for s in sources
        )
        try:
            await self.deps.ledger.check(conversation_id)
            result = await self.deps.llm.answer(
                state["user_input"], documents, _recent(state["messages"])[:-1], config
            )
            await self.deps.ledger.record(conversation_id, "answer", result.model,
                                          result.input_tokens, result.output_tokens)
        except BudgetExceededError as exc:
            log.error("budget.breach", scope=exc.scope, used=exc.used, limit=exc.limit)
            return _handoff("budget")
        except (LLMOutputError, anthropic.APIError) as exc:
            log.error("answer.failed", error=type(exc).__name__)
            return _handoff("answerer_unavailable")

        grounded = result.value
        known_ids = {s["id"] for s in sources}
        cited = [cid for cid in grounded.cited_chunk_ids if cid in known_ids]
        if not grounded.answerable:
            log.info("answer.not_answerable", retrieved=sorted(known_ids))
            return {"outcome": "no_answer", "reply": REPLY_NO_ANSWER, "sources": []}
        if not cited or len(cited) != len(grounded.cited_chunk_ids):
            # An answer citing nothing, or citing ids it was never given, is not grounded.
            log.warning("answer.ungrounded", cited=grounded.cited_chunk_ids)
            return {"outcome": "no_answer", "reply": REPLY_NO_ANSWER, "sources": []}
        return {
            "outcome": "answered",
            "reply": grounded.answer.strip(),
            "sources": [{k: s[k] for k in ("id", "title", "heading")}
                        for s in sources if s["id"] in cited],
        }

    async def lookup_booking(self, state: ConversationState) -> dict[str, Any]:
        reference = state.get("booking_reference")
        if not reference:
            return {"outcome": "needs_booking_reference", "reply": REPLY_NEEDS_REFERENCE}
        booking = await self.deps.bookings.get_booking_for_customer(
            reference, state["customer_email"]
        )
        if booking is None:
            log.info("booking.not_found")
            return {"outcome": "booking_not_found", "reply": REPLY_NOT_FOUND}
        return {"booking": booking.to_public_dict()}

    async def booking_status(self, state: ConversationState) -> dict[str, Any]:
        b = state["booking"] or {}
        reply = (
            f"Booking {b['reference']} ({b['service']}) is {b['status']}, scheduled for "
            f"{_format_when(str(b['scheduled_for']))}. Amount paid: {b['amount']}."
        )
        if b["refunded"] != "$0.00":
            reply += f" Refunded so far: {b['refunded']}."
        return {"outcome": "booking_status", "reply": reply}

    async def assess_refund(self, state: ConversationState) -> dict[str, Any]:
        reference = str(state.get("booking_reference"))
        booking = await self.deps.bookings.get_booking_for_customer(
            reference, state["customer_email"]
        )
        if booking is None:
            return {"outcome": "booking_not_found", "reply": REPLY_NOT_FOUND}
        decision = assess_refund(booking, self.deps.clock())
        log.info("refund.assessed", reason=decision.reason, eligible=decision.eligible)
        if decision.needs_human:
            return _handoff("completed_service_refund", reply=(
                f"Booking {reference} is already completed, so a member of our quality team "
                "needs to review it personally. I'm connecting you with them now."
            ))
        if decision.reason == "already_refunded":
            return {"outcome": "refund_ineligible",
                    "reply": f"Booking {reference} has already been refunded in full."}
        if not decision.eligible:
            return {"outcome": "refund_ineligible", "reply": (
                f"Booking {reference} starts in less than 24 hours, so it isn't eligible for a "
                "refund under our refund policy. If something unusual happened, I can connect "
                "you with a person."
            )}
        return {"refund": {
            "booking_reference": reference,
            "amount_cents": decision.amount_cents,
            "policy_reason": decision.reason,
        }}

    async def request_approval(self, state: ConversationState) -> dict[str, Any]:
        """Tell the customer the request is with the team.

        A separate step so the message is checkpointed before the run pauses: the transcript
        shows it while the approval waits, instead of only the final outcome.
        """
        return {"messages": [AIMessage(pending_approval_reply(state["refund"] or {}))]}

    async def await_approval(self, state: ConversationState) -> dict[str, Any]:
        refund = state["refund"] or {}
        # Nothing with side effects may run before interrupt(): this node re-runs on resume.
        resume = interrupt({
            "type": "refund_approval",
            "conversation_id": state["conversation_id"],
            **refund,
        })
        approval = await self.deps.bookings.get_approval(UUID(str(resume["approval_id"])))
        if (
            approval is None
            or str(approval.conversation_id) != state["conversation_id"]
            or approval.booking_reference != refund["booking_reference"]
            or approval.amount_cents != refund["amount_cents"]
        ):
            raise ValueError("resume payload does not match this conversation's refund request")

        reference, amount = approval.booking_reference, f"${approval.amount_cents / 100:.2f}"
        if approval.status == "rejected":
            return {"outcome": "refund_rejected", "reply": (
                f"Our support team reviewed the refund request for booking {reference} and "
                "couldn't approve it. A team member will follow up with the details."
            )}
        if approval.status != "approved":
            raise RuntimeError("graph resumed before the approval was decided")
        try:
            applied = await self.deps.bookings.execute_refund(approval.id)
        except RefundConflictError:
            log.error("refund.conflict")
            return _handoff("refund_conflict")
        log.info("refund.executed", newly_applied=applied)
        return {"outcome": "refund_completed", "reply": (
            f"Your refund of {amount} for booking {reference} has been approved. It will appear "
            "on your original payment method within 5 to 10 business days."
        )}

    async def handoff(self, state: ConversationState) -> dict[str, Any]:
        return _handoff("customer_request")

    async def out_of_scope(self, state: ConversationState) -> dict[str, Any]:
        return {"outcome": "out_of_scope", "reply": REPLY_OUT_OF_SCOPE}

    async def respond(self, state: ConversationState) -> dict[str, Any]:
        return {"messages": [AIMessage(state.get("reply") or REPLY_HANDOFF)]}


def _recent(messages: Sequence[BaseMessage]) -> list[BaseMessage]:
    return list(messages[-HISTORY_WINDOW:])
