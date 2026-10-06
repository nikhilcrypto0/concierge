"""A reviewer may approve a LOWER amount; the customer is told the real figure."""

from uuid import uuid4

from concierge.agent.graph import resume_after_decision, run_turn
from concierge.bookings.repository import ApprovalRequest

from .test_graph import EMAIL, FakeLLM, booking, classification, make


async def _paused_full_notice_refund():
    graph, store, _ = make(FakeLLM(classification("refund_request", "BK-1042")),
                           bookings=[booking(hours=120)])
    conversation_id = uuid4()
    paused = await run_turn(graph, conversation_id, EMAIL, "Cancel BK-1042 and refund me")
    assert paused.approval_request is not None
    return graph, store, conversation_id, paused.approval_request


async def test_a_lower_approval_tells_the_customer_the_real_amount() -> None:
    graph, store, conversation_id, request = await _paused_full_notice_refund()
    approval_id = store.record_decision(conversation_id, request, "approved",
                                        approved_amount_cents=10_000)
    done = await resume_after_decision(graph, conversation_id, approval_id)
    assert done.outcome == "refund_completed"
    assert "$100.00" in done.reply
    assert "less than the $240.00 originally requested" in done.reply
    assert "has been approved" in done.reply  # the web UI keys on this phrase
    assert store.executed == [approval_id]


async def test_a_full_approval_does_not_mention_an_adjustment() -> None:
    graph, store, conversation_id, request = await _paused_full_notice_refund()
    approval_id = store.record_decision(conversation_id, request, "approved")
    done = await resume_after_decision(graph, conversation_id, approval_id)
    assert "$240.00" in done.reply
    assert "less than" not in done.reply


def test_the_authorised_amount_is_the_approved_one_when_present() -> None:
    def approval(approved: int | None) -> ApprovalRequest:
        return ApprovalRequest(
            id=uuid4(), conversation_id=uuid4(), booking_reference="BK-1042", action="refund",
            amount_cents=24_000, policy_reason="full_notice", status="approved", reviewer="lead",
            review_note=None, created_at=None, decided_at=None,  # type: ignore[arg-type]
            approved_amount_cents=approved,
        )

    assert approval(None).authorised_cents == 24_000
    assert approval(10_000).authorised_cents == 10_000
