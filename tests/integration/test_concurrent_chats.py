"""Many customers chatting at once must not starve each other of database connections."""

import asyncio
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi.testclient import TestClient
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from concierge.api.app import create_app
from concierge.llm import Classification, GroundedAnswer, LLMResult
from concierge.retrieval.embeddings import FastEmbedEmbedder
from tests.integration.test_api import CLIENT, KeywordLLM, _settings

MODEL_DELAY_SECONDS = 0.4
POOL_MAX = 4
VISITORS = 12


class SlowLLM(KeywordLLM):
    """The keyword stand-in, but each model call takes a moment, like the real thing."""

    async def classify(
        self, history: Sequence[BaseMessage], config: RunnableConfig | None = None
    ) -> LLMResult[Classification]:
        await asyncio.sleep(MODEL_DELAY_SECONDS)
        return await super().classify(history, config)

    async def answer(
        self, question: str, documents: str, history: Sequence[BaseMessage],
        config: RunnableConfig | None = None,
    ) -> LLMResult[GroundedAnswer]:
        await asyncio.sleep(MODEL_DELAY_SECONDS)
        return await super().answer(question, documents, history, config)


def _chat(client: TestClient, number: int) -> Any:
    body = {"customer_email": "maya@example.com", "message": f"How do refunds work? ({number})"}
    return client.post("/v1/chat", json=body, headers=CLIENT)


def test_more_simultaneous_chats_than_pool_connections_all_finish(
    seeded: str, embedder: FastEmbedEmbedder
) -> None:
    settings = _settings(seeded).model_copy(update={"db_pool_max": POOL_MAX})
    app = create_app(settings, llm=SlowLLM(), embedder=embedder)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=VISITORS) as executor:
        futures = [executor.submit(_chat, client, n) for n in range(VISITORS)]
        statuses = sorted(future.result().status_code for future in futures)
    assert statuses == [200] * VISITORS


def test_when_the_lock_pool_is_full_extra_chats_get_a_fast_busy_answer(
    seeded: str, embedder: FastEmbedEmbedder
) -> None:
    settings = _settings(seeded).model_copy(
        update={"db_lock_pool_max": 2, "db_lock_wait_seconds": 0.1}
    )
    app = create_app(settings, llm=SlowLLM(), embedder=embedder)
    started = time.monotonic()
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=VISITORS) as executor:
        futures = [executor.submit(_chat, client, n) for n in range(VISITORS)]
        statuses = [future.result().status_code for future in futures]
    elapsed = time.monotonic() - started

    # Two chats fit; the rest are told to retry. Nobody hangs and nobody gets a server error.
    assert set(statuses) <= {200, 409}
    assert statuses.count(200) >= 2 and statuses.count(409) >= 1
    assert elapsed < 10
