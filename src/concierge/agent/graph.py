"""The support workflow as an explicit LangGraph state machine, plus the turn runner.

    guard ──(blocked)──────────────────────────────────────────────► respond ─► END
      └─► classify
            ├─ question ─────────► retrieve ──► answer ────────────► respond
            │                         └─(no relevant docs)─────────► respond
            ├─ booking_status ───► lookup_booking ──► booking_status ► respond
            ├─ refund_request ───► lookup_booking ──► assess_refund
            │                                          ├─(eligible)► request_approval
            │                                          │               └► await_approval ⏸ ► respond
            │                                          └─(not)─────► respond
            ├─ human_handoff ────► handoff ────────────────────────► respond
            └─ out_of_scope ─────► out_of_scope ───────────────────► respond

A routed workflow instead of a free-form tool-calling loop: every path is enumerable, testable,
and auditable, and the model can never choose to move money. request_approval pauses the run
with interrupt(); the run resumes only after a human decision is recorded in Postgres.
"""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

import psycopg
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, RetryPolicy

from concierge.agent.nodes import AgentDeps, SupportAgentNodes, pending_approval_reply
from concierge.agent.state import ConversationState

DB_RETRY = RetryPolicy(max_attempts=3, initial_interval=0.2, retry_on=psycopg.OperationalError)

INTENT_ROUTES = {
    "question": "retrieve",
    "booking_status": "lookup_booking",
    "refund_request": "lookup_booking",
    "human_handoff": "handoff",
    "out_of_scope": "out_of_scope",
}


def _after_guard(state: ConversationState) -> str:
    return "respond" if state.get("outcome") else "classify"


def _after_classify(state: ConversationState) -> str:
    if state.get("outcome"):
        return "respond"
    return INTENT_ROUTES.get(state.get("intent") or "", "handoff")


def _after_retrieve(state: ConversationState) -> str:
    return "respond" if state.get("outcome") else "answer"


def _after_lookup(state: ConversationState) -> str:
    if state.get("outcome"):
        return "respond"
    return "assess_refund" if state.get("intent") == "refund_request" else "booking_status"


def _after_assess(state: ConversationState) -> str:
    return "respond" if state.get("outcome") else "request_approval"


def build_graph(
    deps: AgentDeps, checkpointer: BaseCheckpointSaver[Any] | None
) -> CompiledStateGraph[Any, Any, Any, Any]:
    nodes = SupportAgentNodes(deps)
    graph = StateGraph(ConversationState)
    graph.add_node("guard", nodes.guard)
    graph.add_node("classify", nodes.classify)
    graph.add_node("retrieve", nodes.retrieve, retry_policy=DB_RETRY)
    graph.add_node("answer", nodes.answer)
    graph.add_node("lookup_booking", nodes.lookup_booking, retry_policy=DB_RETRY)
    graph.add_node("booking_status", nodes.booking_status)
    graph.add_node("assess_refund", nodes.assess_refund, retry_policy=DB_RETRY)
    graph.add_node("request_approval", nodes.request_approval)
    graph.add_node("await_approval", nodes.await_approval)
    graph.add_node("handoff", nodes.handoff)
    graph.add_node("out_of_scope", nodes.out_of_scope)
    graph.add_node("respond", nodes.respond)

    graph.add_edge(START, "guard")
    graph.add_conditional_edges("guard", _after_guard, ["classify", "respond"])
    graph.add_conditional_edges(
        "classify", _after_classify, [*set(INTENT_ROUTES.values()), "respond"]
    )
    graph.add_conditional_edges("retrieve", _after_retrieve, ["answer", "respond"])
    graph.add_conditional_edges(
        "lookup_booking", _after_lookup, ["booking_status", "assess_refund", "respond"]
    )
    graph.add_conditional_edges("assess_refund", _after_assess, ["request_approval", "respond"])
    graph.add_edge("request_approval", "await_approval")
    for terminal in ("answer", "booking_status", "await_approval", "handoff", "out_of_scope"):
        graph.add_edge(terminal, "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer, name="concierge")


@dataclass(frozen=True)
class TurnResult:
    status: Literal["completed", "pending_approval"]
    reply: str
    outcome: str | None
    intent: str | None
    sources: list[dict[str, str]]
    approval_request: dict[str, Any] | None
    handoff_reason: str | None = None


def _config(
    conversation_id: UUID, callbacks: list[BaseCallbackHandler] | None
) -> RunnableConfig:
    return {
        "configurable": {"thread_id": str(conversation_id)},
        "callbacks": callbacks or [],
        "metadata": {"conversation_id": str(conversation_id)},
    }


def _to_result(output: dict[str, Any]) -> TurnResult:
    interrupts = output.get("__interrupt__") or []
    if interrupts:
        payload = dict(interrupts[0].value)
        return TurnResult(
            status="pending_approval",
            reply=pending_approval_reply(payload),
            outcome="refund_pending_approval",
            intent=output.get("intent"),
            sources=[],
            approval_request=payload,
        )
    return TurnResult(
        status="completed",
        reply=str(output.get("reply") or ""),
        outcome=output.get("outcome"),
        intent=output.get("intent"),
        sources=list(output.get("sources") or []),
        approval_request=None,
        handoff_reason=output.get("handoff_reason"),
    )


async def run_turn(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    conversation_id: UUID,
    customer_email: str,
    message: str,
    callbacks: list[BaseCallbackHandler] | None = None,
) -> TurnResult:
    output = await graph.ainvoke(
        {
            "conversation_id": str(conversation_id),
            "customer_email": customer_email,
            "messages": [HumanMessage(message, id=str(uuid4()))],
        },
        _config(conversation_id, callbacks),
    )
    return _to_result(output)


async def resume_after_decision(
    graph: CompiledStateGraph[Any, Any, Any, Any],
    conversation_id: UUID,
    approval_id: UUID,
    callbacks: list[BaseCallbackHandler] | None = None,
) -> TurnResult:
    output = await graph.ainvoke(
        Command(resume={"approval_id": str(approval_id)}), _config(conversation_id, callbacks)
    )
    return _to_result(output)
