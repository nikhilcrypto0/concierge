"""The HTTP API end to end: real Postgres, real checkpointer, real retrieval, scripted model."""

import re
from collections.abc import Iterator, Sequence
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from httpx import Response
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from concierge.api.app import create_app
from concierge.config import Settings
from concierge.guardrails import extract_booking_reference
from concierge.llm import Classification, GroundedAnswer, LLMResult
from concierge.retrieval.embeddings import FastEmbedEmbedder

CLIENT_KEY = "client-key-" + "x" * 24
OPERATOR_KEY = "operator-key-" + "y" * 24
CLIENT = {"X-API-Key": CLIENT_KEY}
OPERATOR = {"X-API-Key": OPERATOR_KEY}
MAYA = "maya@example.com"


class KeywordLLM:
    """Deterministic stand-in for Claude so API tests are free and repeatable."""

    async def classify(
        self, history: Sequence[BaseMessage], config: RunnableConfig | None = None
    ) -> LLMResult[Classification]:
        text = str(history[-1].content).lower()
        reference = extract_booking_reference(text)
        # Like the real classifier prompt: a refund *request* names a booking; "how do refunds
        # work?" is a question.
        intent = "refund_request" if "refund" in text and reference else (
            "booking_status" if "status" in text else "question")
        value = Classification(intent=intent, booking_reference=reference,
                               confidence=0.9, search_query=text)
        return LLMResult(value, "keyword-fake", 10, 5)

    async def answer(
        self, question: str, documents: str, history: Sequence[BaseMessage],
        config: RunnableConfig | None = None,
    ) -> LLMResult[GroundedAnswer]:
        match = re.search(r'id="([^"]+)"', documents)
        assert match is not None
        value = GroundedAnswer(answerable=True, answer="Here is what our policy says.",
                               cited_chunk_ids=[match.group(1)])
        return LLMResult(value, "keyword-fake", 10, 5)


def _settings(database_url: str, rate_limit: int = 1_000) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=database_url,
        rate_limit_per_minute=rate_limit,
        CLIENT_API_KEYS=f"webapp:{CLIENT_KEY}",
        OPERATOR_API_KEYS=f"support-lead:{OPERATOR_KEY}",
    )


@pytest.fixture
def client(seeded: str, embedder: FastEmbedEmbedder) -> Iterator[TestClient]:
    app = create_app(_settings(seeded), llm=KeywordLLM(), embedder=embedder)
    with TestClient(app) as test_client:
        yield test_client


def chat(
    client: TestClient, message: str, email: str = MAYA, conversation_id: str | None = None
) -> Response:
    body: dict[str, Any] = {"customer_email": email, "message": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return client.post("/v1/chat", json=body, headers=CLIENT)


def test_health_and_readiness(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.headers["X-Request-ID"]


def test_each_role_can_only_use_its_own_endpoints(client: TestClient) -> None:
    body = {"customer_email": MAYA, "message": "hi"}
    assert client.post("/v1/chat", json=body).status_code == 401
    assert client.post("/v1/chat", json=body, headers=OPERATOR).status_code == 401
    assert client.get("/v1/approvals", headers=CLIENT).status_code == 401


def test_questions_are_answered_with_sources(client: TestClient) -> None:
    body = chat(client, "How long do refunds take to show up on my card?").json()
    assert body["status"] == "completed"
    assert body["outcome"] == "answered"
    assert body["sources"] and body["request_id"]


def test_refund_waits_for_a_human_and_is_applied_exactly_once(
    client: TestClient, seeded: str
) -> None:
    first = chat(client, "Please refund BK-1042").json()
    assert first["status"] == "pending_approval"
    assert "$240.00" in first["reply"]
    conversation_id = first["conversation_id"]

    follow_up = chat(client, "any update?", conversation_id=conversation_id).json()
    assert follow_up["status"] == "pending_approval"

    pending = client.get("/v1/approvals", headers=OPERATOR).json()
    assert len(pending) == 1
    assert (pending[0]["booking_reference"], pending[0]["amount"]) == ("BK-1042", "$240.00")

    url = f"/v1/approvals/{pending[0]['id']}/decision"
    decision = client.post(url, json={"approve": True, "note": "ok"}, headers=OPERATOR)
    assert decision.status_code == 200
    assert decision.json()["outcome"] == "refund_completed"
    assert decision.json()["approval"]["reviewer"] == "support-lead"
    assert client.post(url, json={"approve": True}, headers=OPERATOR).status_code == 409

    with psycopg.connect(seeded) as conn:
        booking = conn.execute(
            "SELECT refunded_cents, status FROM bookings WHERE reference = 'BK-1042'"
        ).fetchone()
        actions = conn.execute("SELECT count(*) FROM actions").fetchone()
    assert booking == (24_000, "cancelled")
    assert actions == (1,)

    transcript = client.get(f"/v1/conversations/{conversation_id}/messages",
                            params={"customer_email": MAYA}, headers=CLIENT).json()
    assert [m["role"] for m in transcript] == ["customer", "assistant", "assistant"]
    assert "sent a refund request" in transcript[1]["content"]
    assert "approved" in transcript[-1]["content"]


def test_rejected_refund_leaves_the_booking_untouched(client: TestClient, seeded: str) -> None:
    chat(client, "refund BK-1043 please")
    pending = client.get("/v1/approvals", headers=OPERATOR).json()
    assert pending[0]["amount"] == "$67.50", "30 hours notice -> 50% of $135.00"
    decision = client.post(f"/v1/approvals/{pending[0]['id']}/decision",
                           json={"approve": False, "note": "duplicate"}, headers=OPERATOR)
    assert decision.json()["outcome"] == "refund_rejected"
    with psycopg.connect(seeded) as conn:
        row = conn.execute(
            "SELECT refunded_cents FROM bookings WHERE reference = 'BK-1043'"
        ).fetchone()
    assert row == (0,)


def test_conversations_cannot_be_read_or_continued_by_another_customer(
    client: TestClient,
) -> None:
    conversation_id = chat(client, "What is your refund policy?").json()["conversation_id"]
    hijack = chat(client, "hi", email="jordan@example.com", conversation_id=conversation_id)
    assert hijack.status_code == 404
    peek = client.get(f"/v1/conversations/{conversation_id}/messages",
                      params={"customer_email": "jordan@example.com"}, headers=CLIENT)
    assert peek.status_code == 404


def test_unknown_fields_and_oversized_messages_are_rejected(client: TestClient) -> None:
    extra = {"customer_email": MAYA, "message": "hi", "is_admin": True}
    assert client.post("/v1/chat", json=extra, headers=CLIENT).status_code == 422
    huge = {"customer_email": MAYA, "message": "x" * 4_001}
    assert client.post("/v1/chat", json=huge, headers=CLIENT).status_code == 422


def test_unknown_approval_is_404(client: TestClient) -> None:
    url = "/v1/approvals/00000000-0000-4000-8000-000000000000/decision"
    assert client.post(url, json={"approve": True}, headers=OPERATOR).status_code == 404


def test_rate_limit_returns_429_with_retry_after(seeded: str, embedder: FastEmbedEmbedder) -> None:
    app = create_app(_settings(seeded, rate_limit=2), llm=KeywordLLM(), embedder=embedder)
    with TestClient(app) as limited:
        codes = [chat(limited, "What is your refund policy?").status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        blocked = chat(limited, "What is your refund policy?")
        assert int(blocked.headers["Retry-After"]) >= 1


def test_oversized_request_body_is_rejected_before_parsing(client: TestClient) -> None:
    huge = '{"customer_email": "maya@example.com", "message": "' + "x" * 100_000 + '"}'
    headers = {**CLIENT, "content-type": "application/json"}
    assert client.post("/v1/chat", content=huge, headers=headers).status_code == 413


def test_failed_authentication_is_rate_limited(seeded: str, embedder: FastEmbedEmbedder) -> None:
    app = create_app(_settings(seeded, rate_limit=2), llm=KeywordLLM(), embedder=embedder)
    wrong = {"X-API-Key": "wrong-key-" + "z" * 24}
    body = {"customer_email": MAYA, "message": "hi"}
    with TestClient(app) as limited:
        codes = [limited.post("/v1/chat", json=body, headers=wrong).status_code for _ in range(3)]
    assert codes == [401, 401, 429]


def test_api_docs_are_hidden_in_production(seeded: str, embedder: FastEmbedEmbedder) -> None:
    settings = _settings(seeded).model_copy(update={"environment": "prod"})
    app = create_app(settings, llm=KeywordLLM(), embedder=embedder)
    with TestClient(app) as prod:
        assert prod.get("/docs").status_code == 404
        assert prod.get("/openapi.json").status_code == 404


def test_a_conversation_already_being_processed_returns_409(
    client: TestClient, seeded: str
) -> None:
    conversation_id = chat(client, "What is your refund policy?").json()["conversation_id"]
    with psycopg.connect(seeded, autocommit=True) as other_replica:
        other_replica.execute(
            "SELECT pg_advisory_lock(hashtextextended(%s, 0))",
            (f"conversation:{conversation_id}",),
        )
        busy = chat(client, "and the fee?", conversation_id=conversation_id)
    assert busy.status_code == 409
    released = chat(client, "and the fee?", conversation_id=conversation_id)
    assert released.status_code == 200
