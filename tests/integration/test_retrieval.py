from pathlib import Path

from concierge.db import DictPool
from concierge.retrieval.embeddings import FastEmbedEmbedder
from concierge.retrieval.ingest import ingest
from concierge.retrieval.search import KnowledgeBase

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "kb"
FLOOR = 0.55


async def test_paraphrased_question_finds_the_refund_article(
    pool: DictPool, embedder: FastEmbedEmbedder
) -> None:
    kb = KnowledgeBase(pool, embedder, default_mode="vector")
    results = await kb.search("how do I get my money back if I cancel a few days early", k=3)
    assert results[0].doc_slug == "refund-policy"
    assert results[0].similarity >= FLOOR


async def test_every_search_mode_returns_ranked_results(
    pool: DictPool, embedder: FastEmbedEmbedder
) -> None:
    kb = KnowledgeBase(pool, embedder, keyword_weight=0.5)
    for mode in ("hybrid", "vector", "keyword"):
        results = await kb.search("reschedule fee", k=4, mode=mode)
        assert results, mode
        assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)


async def test_off_topic_questions_fall_below_the_relevance_floor(
    pool: DictPool, embedder: FastEmbedEmbedder
) -> None:
    kb = KnowledgeBase(pool, embedder, default_mode="vector")
    results = await kb.search("what is the capital of France", k=4)
    assert max(r.similarity for r in results) < FLOOR


async def test_reingesting_unchanged_documents_is_a_no_op(
    pool: DictPool, embedder: FastEmbedEmbedder
) -> None:
    report = await ingest(pool, embedder, KB_DIR)
    assert (report.upserted, report.deleted) == (0, 0)
    assert report.unchanged > 0
