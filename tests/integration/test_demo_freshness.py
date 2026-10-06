"""Demo bookings are reseeded once stale, but never under a visitor who is mid-demo."""

from collections.abc import Iterator
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from concierge.api.app import DEMO_MAX_AGE, DEMO_QUIET_FOR, create_app
from concierge.bookings.repository import SupportRepository
from concierge.db import DictPool
from concierge.retrieval.embeddings import FastEmbedEmbedder

from .test_api import CLIENT, MAYA, KeywordLLM, _settings


@pytest.fixture(autouse=True)
def quiet_ledger(seeded: str) -> None:
    """Earlier tests leave token-usage rows behind; for these tests nobody has chatted lately."""
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM llm_usage")


def _age_the_demo(database_url: str, by: timedelta) -> None:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("UPDATE bookings SET scheduled_for = scheduled_for - %s", (by,))


async def _stale(pool: DictPool) -> bool:
    return await SupportRepository(pool).demo_data_is_stale(DEMO_MAX_AGE, DEMO_QUIET_FOR)


async def test_freshly_seeded_data_is_not_stale(pool: DictPool) -> None:
    assert not await _stale(pool)


async def test_data_older_than_the_limit_is_stale(pool: DictPool, seeded: str) -> None:
    _age_the_demo(seeded, DEMO_MAX_AGE + timedelta(minutes=1))
    assert await _stale(pool)


async def test_data_just_under_the_limit_is_not_stale(pool: DictPool, seeded: str) -> None:
    _age_the_demo(seeded, DEMO_MAX_AGE - timedelta(minutes=5))
    assert not await _stale(pool)


async def test_a_refund_waiting_for_a_person_blocks_the_refresh(
    pool: DictPool, seeded: str
) -> None:
    repo = SupportRepository(pool)
    conversation_id = uuid4()
    assert await repo.claim_conversation(conversation_id, MAYA)
    await repo.open_approval_request(conversation_id, "BK-1042", 24_000, "full_notice")
    _age_the_demo(seeded, DEMO_MAX_AGE + timedelta(hours=1))
    assert not await _stale(pool)


async def test_a_recent_chat_blocks_the_refresh(pool: DictPool, seeded: str) -> None:
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO llm_usage (conversation_id, step, model, input_tokens, output_tokens) "
            "VALUES (%s, 'classify', 'fake', 1, 1)", (uuid4(),))
    _age_the_demo(seeded, DEMO_MAX_AGE + timedelta(hours=1))
    assert not await _stale(pool)


async def test_a_database_with_no_demo_data_is_left_alone(pool: DictPool, seeded: str) -> None:
    with psycopg.connect(seeded, autocommit=True) as conn:
        conn.execute("DELETE FROM bookings")
    assert not await _stale(pool)


@pytest.fixture
def demo_client(seeded: str, embedder: FastEmbedEmbedder) -> Iterator[TestClient]:
    settings = _settings(seeded).model_copy(update={"demo_mode": True})
    with TestClient(create_app(settings, llm=KeywordLLM(), embedder=embedder)) as client:
        yield client


def _hours_until(database_url: str, reference: str) -> float:
    with psycopg.connect(database_url) as conn:
        row = conn.execute(
            "SELECT extract(epoch FROM scheduled_for - now()) / 3600 FROM bookings "
            "WHERE reference = %s", (reference,)).fetchone()
    assert row is not None
    return float(row[0])


def test_loading_bookings_refreshes_stale_demo_data(
    demo_client: TestClient, seeded: str
) -> None:
    _age_the_demo(seeded, timedelta(hours=5))
    assert _hours_until(seeded, "BK-1043") < 26  # it has drifted

    response = demo_client.get("/v1/bookings", params={"customer_email": MAYA}, headers=CLIENT)
    assert response.status_code == 200
    assert _hours_until(seeded, "BK-1043") > 29.5  # reseeded relative to now


@pytest.fixture
def plain_client(seeded: str, embedder: FastEmbedEmbedder) -> Iterator[TestClient]:
    with TestClient(create_app(_settings(seeded), llm=KeywordLLM(), embedder=embedder)) as client:
        yield client


def test_without_demo_mode_nothing_is_reseeded(plain_client: TestClient, seeded: str) -> None:
    _age_the_demo(seeded, timedelta(hours=5))
    plain_client.get("/v1/bookings", params={"customer_email": MAYA}, headers=CLIENT)
    assert _hours_until(seeded, "BK-1043") < 26
