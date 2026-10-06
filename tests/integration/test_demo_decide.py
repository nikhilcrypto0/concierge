"""A demo visitor can play the support lead for their OWN request, and nothing else."""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from concierge.api.app import DEMO_REVIEWER, create_app
from concierge.retrieval.embeddings import FastEmbedEmbedder

from .test_api import CLIENT, MAYA, OPERATOR, KeywordLLM, _settings, chat

JORDAN = "jordan@example.com"
FULL = 24_000  # BK-1042, 120 hours of notice


@pytest.fixture
def demo_client(seeded: str, embedder: FastEmbedEmbedder) -> Iterator[TestClient]:
    settings = _settings(seeded).model_copy(update={"demo_mode": True})
    with TestClient(create_app(settings, llm=KeywordLLM(), embedder=embedder)) as client:
        yield client


@pytest.fixture
def plain_client(seeded: str, embedder: FastEmbedEmbedder) -> Iterator[TestClient]:
    with TestClient(create_app(_settings(seeded), llm=KeywordLLM(), embedder=embedder)) as client:
        yield client


def _pending_refund(client: TestClient) -> str:
    first = chat(client, "Please refund BK-1042").json()
    assert first["status"] == "pending_approval"
    return str(first["conversation_id"])


def _decide(client: TestClient, conversation_id: str, headers: dict[str, str] | None = None,
            email: str = MAYA, **decision: Any) -> Any:
    body = {"conversation_id": conversation_id, "customer_email": email, **decision}
    return client.post("/v1/demo/decide", json=body, headers=headers or CLIENT)


def _rows(database_url: str) -> dict[str, Any]:
    with psycopg.connect(database_url) as conn:
        booking = conn.execute(
            "SELECT refunded_cents FROM bookings WHERE reference = 'BK-1042'").fetchone()
        approval = conn.execute(
            "SELECT status, reviewer, approved_amount_cents FROM approval_requests").fetchone()
        actions = conn.execute("SELECT count(*) FROM actions").fetchone()
    assert booking and approval and actions
    return {"refunded": booking[0], "status": approval[0], "reviewer": approval[1],
            "approved": approval[2], "actions": actions[0]}


def test_the_api_says_whether_visitors_may_play_the_support_lead(
    demo_client: TestClient, plain_client: TestClient
) -> None:
    """The web app reads this flag, so it only offers the buttons where the route exists."""
    assert demo_client.get("/v1/stats", headers=CLIENT).json()["demo_mode"] is True
    assert plain_client.get("/v1/stats", headers=CLIENT).json()["demo_mode"] is False


def test_a_visitor_can_approve_their_own_request(demo_client: TestClient, seeded: str) -> None:
    conversation_id = _pending_refund(demo_client)
    response = _decide(demo_client, conversation_id, approve=True)
    assert response.status_code == 200
    assert "has been approved" in response.json()["customer_reply"]
    rows = _rows(seeded)
    assert (rows["refunded"], rows["status"], rows["actions"]) == (FULL, "approved", 1)
    assert rows["reviewer"] == DEMO_REVIEWER  # never mistaken for a real operator


def test_a_visitor_can_approve_a_lower_amount(demo_client: TestClient, seeded: str) -> None:
    conversation_id = _pending_refund(demo_client)
    response = _decide(demo_client, conversation_id, approve=True, approved_amount_cents=10_000)
    assert response.status_code == 200
    assert "less than the $240.00 originally requested" in response.json()["customer_reply"]
    rows = _rows(seeded)
    assert (rows["refunded"], rows["approved"]) == (10_000, 10_000)


def test_a_visitor_can_reject_their_own_request(demo_client: TestClient, seeded: str) -> None:
    conversation_id = _pending_refund(demo_client)
    assert _decide(demo_client, conversation_id, approve=False).status_code == 200
    rows = _rows(seeded)
    assert (rows["refunded"], rows["status"], rows["actions"]) == (0, "rejected", 0)


def test_someone_elses_conversation_cannot_be_decided(
    demo_client: TestClient, seeded: str
) -> None:
    conversation_id = _pending_refund(demo_client)  # Maya's
    response = _decide(demo_client, conversation_id, email=JORDAN, approve=True)
    assert response.status_code == 404
    rows = _rows(seeded)
    assert (rows["refunded"], rows["status"]) == (0, "pending")


def test_an_unknown_conversation_looks_the_same_as_someone_elses(demo_client: TestClient) -> None:
    assert _decide(demo_client, str(uuid4()), approve=True).status_code == 404


def test_the_route_does_not_exist_outside_demo_mode(
    plain_client: TestClient, seeded: str
) -> None:
    conversation_id = _pending_refund(plain_client)
    assert _decide(plain_client, conversation_id, approve=True).status_code == 404
    assert _rows(seeded)["status"] == "pending"


def test_it_needs_the_client_key_not_the_operator_key(
    demo_client: TestClient, seeded: str
) -> None:
    conversation_id = _pending_refund(demo_client)
    body = {"conversation_id": conversation_id, "customer_email": MAYA, "approve": True}
    assert demo_client.post("/v1/demo/decide", json=body).status_code == 401
    assert demo_client.post("/v1/demo/decide", json=body, headers=OPERATOR).status_code == 401
    assert _rows(seeded)["status"] == "pending"


def test_an_amount_above_the_policy_amount_is_refused(
    demo_client: TestClient, seeded: str
) -> None:
    conversation_id = _pending_refund(demo_client)
    response = _decide(demo_client, conversation_id, approve=True, approved_amount_cents=FULL + 1)
    assert response.status_code == 422
    assert _rows(seeded)["status"] == "pending"


def test_an_amount_cannot_accompany_a_rejection(demo_client: TestClient, seeded: str) -> None:
    conversation_id = _pending_refund(demo_client)
    response = _decide(demo_client, conversation_id, approve=False, approved_amount_cents=500)
    assert response.status_code == 422
    assert _rows(seeded)["status"] == "pending"


def test_a_second_decision_does_not_pay_twice(demo_client: TestClient, seeded: str) -> None:
    conversation_id = _pending_refund(demo_client)
    assert _decide(demo_client, conversation_id, approve=True).status_code == 200
    assert _decide(demo_client, conversation_id, approve=True).status_code == 404  # nothing pending
    rows = _rows(seeded)
    assert (rows["refunded"], rows["actions"]) == (FULL, 1)
