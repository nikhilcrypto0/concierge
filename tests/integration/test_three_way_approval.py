"""Approve in full, approve less, or reject: the money, the records, and the customer's message
must always agree, and no path can pay more than the policy amount."""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from concierge.api.app import create_app
from concierge.retrieval.embeddings import FastEmbedEmbedder

from .test_api import CLIENT, MAYA, OPERATOR, KeywordLLM, _settings, chat

FULL = 24_000  # BK-1042: 120 hours notice, full refund of $240.00


@pytest.fixture
def api_client(seeded: str, embedder: FastEmbedEmbedder) -> Iterator[TestClient]:
    app = create_app(_settings(seeded), llm=KeywordLLM(), embedder=embedder)
    with TestClient(app) as test_client:
        yield test_client


def _request_refund(api_client: TestClient) -> tuple[str, str]:
    first = chat(api_client, "Please refund BK-1042").json()
    assert first["status"] == "pending_approval"
    pending = api_client.get("/v1/approvals", headers=OPERATOR).json()
    return pending[0]["id"], first["conversation_id"]


def _rows(seeded: str) -> dict[str, Any]:
    with psycopg.connect(seeded) as conn:
        booking = conn.execute(
            "SELECT refunded_cents, status FROM bookings WHERE reference = 'BK-1042'"
        ).fetchone()
        actions = conn.execute("SELECT count(*), coalesce(sum(amount_cents), 0) FROM actions"
                               ).fetchone()
        approval = conn.execute(
            "SELECT status, approved_amount_cents FROM approval_requests"
        ).fetchone()
    assert booking and actions and approval
    return {"refunded": booking[0], "booking_status": booking[1], "actions": actions[0],
            "paid": int(actions[1]), "approval_status": approval[0], "approved": approval[1]}


@pytest.mark.parametrize(
    ("decision", "refunded", "actions", "approval_status", "approved", "reply_has"),
    [
        ({"approve": True}, FULL, 1, "approved", None, ["$240.00", "has been approved"]),
        ({"approve": True, "approved_amount_cents": FULL}, FULL, 1, "approved", None,
         ["$240.00"]),  # the full amount is stored as a plain approval
        ({"approve": True, "approved_amount_cents": 10_000}, 10_000, 1, "approved", 10_000,
         ["$100.00", "less than the $240.00 originally requested"]),
        ({"approve": False, "note": "duplicate"}, 0, 0, "rejected", None, ["couldn't approve"]),
    ],
    ids=["approve-full", "approve-explicit-full", "approve-lower", "reject"],
)
def test_every_decision_leaves_money_records_and_message_consistent(
    api_client: TestClient, seeded: str, decision: dict[str, Any], refunded: int, actions: int,
    approval_status: str, approved: int | None, reply_has: list[str],
) -> None:
    approval_id, conversation_id = _request_refund(api_client)
    response = api_client.post(f"/v1/approvals/{approval_id}/decision", json=decision,
                           headers=OPERATOR)
    assert response.status_code == 200

    rows = _rows(seeded)
    assert rows["refunded"] == refunded
    assert rows["actions"] == actions
    assert rows["paid"] == refunded  # what was executed equals what the booking shows refunded
    assert rows["approval_status"] == approval_status
    assert rows["approved"] == approved
    assert rows["booking_status"] == ("cancelled" if refunded else "scheduled")

    # What the customer actually sees in their transcript is the reply the decision produced.
    transcript = api_client.get(f"/v1/conversations/{conversation_id}/messages",
                            params={"customer_email": MAYA}, headers=CLIENT).json()
    seen = transcript[-1]["content"]
    assert seen == response.json()["customer_reply"]
    for fragment in reply_has:
        assert fragment in seen


def test_a_lower_approval_is_exactly_once(api_client: TestClient, seeded: str) -> None:
    approval_id, _ = _request_refund(api_client)
    url = f"/v1/approvals/{approval_id}/decision"
    body = {"approve": True, "approved_amount_cents": 5_000}
    assert api_client.post(url, json=body, headers=OPERATOR).status_code == 200
    assert api_client.post(url, json=body, headers=OPERATOR).status_code == 409
    rows = _rows(seeded)
    assert (rows["refunded"], rows["actions"], rows["paid"]) == (5_000, 1, 5_000)


def test_an_amount_above_the_policy_amount_is_refused_and_nothing_changes(
    api_client: TestClient, seeded: str
) -> None:
    approval_id, _ = _request_refund(api_client)
    response = api_client.post(f"/v1/approvals/{approval_id}/decision",
                           json={"approve": True, "approved_amount_cents": FULL + 1},
                           headers=OPERATOR)
    assert response.status_code == 422
    rows = _rows(seeded)
    assert (rows["refunded"], rows["actions"], rows["approval_status"]) == (0, 0, "pending")


def test_an_amount_cannot_accompany_a_rejection(api_client: TestClient, seeded: str) -> None:
    approval_id, _ = _request_refund(api_client)
    response = api_client.post(f"/v1/approvals/{approval_id}/decision",
                           json={"approve": False, "approved_amount_cents": 1_000},
                           headers=OPERATOR)
    assert response.status_code == 422
    assert _rows(seeded)["approval_status"] == "pending"


@pytest.mark.parametrize("bad", [0, -5])
def test_a_non_positive_amount_is_refused(api_client: TestClient, bad: int) -> None:
    approval_id, _ = _request_refund(api_client)
    response = api_client.post(f"/v1/approvals/{approval_id}/decision",
                           json={"approve": True, "approved_amount_cents": bad},
                           headers=OPERATOR)
    assert response.status_code == 422


def test_the_database_itself_refuses_an_over_policy_amount(
    api_client: TestClient, seeded: str
) -> None:
    """The backstop under the API check: even a direct write cannot authorise more."""
    approval_id, _ = _request_refund(api_client)
    with psycopg.connect(seeded, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE approval_requests SET status = 'approved', approved_amount_cents = %s "
                "WHERE id = %s", (FULL + 1, approval_id))
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "UPDATE approval_requests SET approved_amount_cents = 100 WHERE id = %s",
                (approval_id,))  # an amount on a request that is still pending
