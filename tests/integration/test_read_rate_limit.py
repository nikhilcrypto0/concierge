"""Page loads and polling must not starve the calls that cost money, and guessing stays limited."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from concierge.api.app import READ_RATE_MULTIPLIER, create_app
from concierge.retrieval.embeddings import FastEmbedEmbedder

from .test_api import CLIENT, MAYA, KeywordLLM, _settings, chat

CHAT_BUDGET = 2  # requests a minute for the costly calls in these tests


@pytest.fixture
def tight_client(seeded: str, embedder: FastEmbedEmbedder) -> Iterator[TestClient]:
    app = create_app(_settings(seeded, rate_limit=CHAT_BUDGET), llm=KeywordLLM(), embedder=embedder)
    with TestClient(app) as client:
        yield client


def _bookings(client: TestClient, headers: dict[str, str] | None = None) -> int:
    return client.get("/v1/bookings", params={"customer_email": MAYA},
                      headers=headers or CLIENT).status_code


def test_reads_do_not_use_up_the_chat_budget(tight_client: TestClient) -> None:
    for _ in range(CHAT_BUDGET * READ_RATE_MULTIPLIER - 1):
        assert _bookings(tight_client) == 200
    # The reads above would have exhausted a shared budget many times over.
    assert chat(tight_client, "How long do refunds take?").status_code == 200
    assert chat(tight_client, "Are your plumbers licensed?").status_code == 200
    assert chat(tight_client, "One chat too many").status_code == 429


def test_reads_are_still_limited(tight_client: TestClient) -> None:
    results = [_bookings(tight_client) for _ in range(CHAT_BUDGET * READ_RATE_MULTIPLIER + 1)]
    assert results[:-1] == [200] * (CHAT_BUDGET * READ_RATE_MULTIPLIER)
    assert results[-1] == 429


def test_guessing_a_key_is_limited_on_the_read_endpoints_too(tight_client: TestClient) -> None:
    wrong = {"X-API-Key": "definitely-not-a-valid-key-" + "z" * 12}
    codes = [_bookings(tight_client, wrong) for _ in range(CHAT_BUDGET + 1)]
    assert codes == [401] * CHAT_BUDGET + [429]
