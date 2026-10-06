"""The live cost figures come from the real token ledger, priced per model, aggregates only."""

from collections.abc import Iterator
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from concierge.api.app import create_app
from concierge.retrieval.embeddings import FastEmbedEmbedder

from .test_api import CLIENT, OPERATOR, KeywordLLM, _settings


@pytest.fixture
def stats_client(seeded: str, embedder: FastEmbedEmbedder) -> Iterator[TestClient]:
    with TestClient(create_app(_settings(seeded), llm=KeywordLLM(), embedder=embedder)) as client:
        yield client


def _usage(database_url: str, rows: list[tuple[str, str, int, int, str]]) -> None:
    """Rows are (conversation, model, input, output, age) with age like '1 hour'."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM llm_usage")
        for conversation, model, tokens_in, tokens_out, age in rows:
            conn.execute(
                "INSERT INTO llm_usage (conversation_id, step, model, input_tokens,"
                " output_tokens, created_at) VALUES (%s, 'answer', %s, %s, %s,"
                " now() - %s::interval)",
                (conversation, model, tokens_in, tokens_out, age),
            )


def test_cost_is_priced_per_model_over_the_last_day(
    stats_client: TestClient, seeded: str
) -> None:
    a, b = str(uuid4()), str(uuid4())
    _usage(seeded, [
        (a, "claude-opus-5", 1_000, 200, "1 hour"),     # $0.0100
        (a, "claude-opus-5", 500, 100, "2 hours"),      # $0.0050
        (b, "claude-sonnet-5", 2_000, 400, "3 hours"),  # $0.0080
        (str(uuid4()), "claude-opus-5", 9_000_000, 0, "30 hours"),  # outside the window
    ])
    body = stats_client.get("/v1/stats", headers=CLIENT).json()
    assert body["window_hours"] == 24
    assert body["conversations"] == 2
    assert body["tokens_in_window"] == 1_200 + 600 + 2_400
    assert body["usd_total"] == pytest.approx(0.023)
    assert body["usd_per_conversation"] == pytest.approx(0.0115)
    assert body["unpriced_models"] == []


def test_an_unpriced_model_is_reported_not_hidden(stats_client: TestClient, seeded: str) -> None:
    _usage(seeded, [(str(uuid4()), "mystery-model", 1_000, 200, "1 hour")])
    body = stats_client.get("/v1/stats", headers=CLIENT).json()
    assert body["unpriced_models"] == ["mystery-model"]
    assert body["usd_total"] == pytest.approx(0.01)  # counted at the most expensive tier


def test_an_empty_ledger_has_no_average(stats_client: TestClient, seeded: str) -> None:
    _usage(seeded, [])
    body = stats_client.get("/v1/stats", headers=CLIENT).json()
    assert (body["conversations"], body["usd_total"], body["tokens_in_window"]) == (0, 0, 0)
    assert body["usd_per_conversation"] is None


def test_the_budgets_shown_are_the_ones_enforced(stats_client: TestClient, seeded: str) -> None:
    _usage(seeded, [])
    settings = _settings(seeded)
    body = stats_client.get("/v1/stats", headers=CLIENT).json()
    assert body["daily_token_budget"] == settings.max_tokens_per_day
    assert body["conversation_token_budget"] == settings.max_tokens_per_conversation


def test_stats_need_the_client_key_and_expose_no_customer_data(
    stats_client: TestClient, seeded: str
) -> None:
    _usage(seeded, [(str(uuid4()), "claude-opus-5", 100, 10, "1 hour")])
    assert stats_client.get("/v1/stats").status_code == 401
    assert stats_client.get("/v1/stats", headers=OPERATOR).status_code == 401
    body = stats_client.get("/v1/stats", headers=CLIENT).json()
    assert set(body) == {
        "window_hours", "conversations", "usd_total", "usd_per_conversation",
        "tokens_in_window", "daily_token_budget", "conversation_token_budget", "unpriced_models",
        "demo_mode",
    }
    assert body["demo_mode"] is False  # the test app is not a demo
