"""Retrieval over the help center: pgvector cosine search, Postgres full-text search, or both fused.

Vector search catches paraphrases ("get my money back" -> refunds); keyword search catches
exact terms an embedding model can blur. Weighted Reciprocal Rank Fusion combines the two
rankings without needing their scores on the same scale. Which mode wins is an empirical
question: evals/run_retrieval_eval.py measures all three and the default follows the data.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from concierge.db import DictPool
from concierge.retrieval.embeddings import Embedder, to_pgvector

SearchMode = Literal["hybrid", "vector", "keyword"]
RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    doc_slug: str
    doc_title: str
    heading: str
    content: str
    similarity: float  # cosine similarity to the query, used for the relevance gate
    score: float  # fused rank score, used for ordering


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]],
    k: int = RRF_K,
    weights: Sequence[float] | None = None,
) -> list[tuple[str, float]]:
    weights = weights if weights is not None else [1.0] * len(rankings)
    scores: dict[str, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights, strict=True):
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] += weight / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


_VECTOR_SQL = """
SELECT id, 1 - (embedding <=> %(qvec)s::vector) AS similarity
FROM kb_chunks
ORDER BY embedding <=> %(qvec)s::vector
LIMIT %(limit)s
"""

# OR together the query's stemmed lexemes: natural questions rarely contain every keyword.
_KEYWORD_SQL = """
WITH q AS (
    SELECT to_tsquery('english', array_to_string(
        tsvector_to_array(to_tsvector('english', %(qtext)s)), ' | ')) AS query
)
SELECT id
FROM kb_chunks, q
WHERE tsv @@ q.query
ORDER BY ts_rank_cd(tsv, q.query) DESC, id
LIMIT %(limit)s
"""

_FETCH_SQL = """
SELECT id, doc_slug, doc_title, heading, content,
       1 - (embedding <=> %(qvec)s::vector) AS similarity
FROM kb_chunks
WHERE id = ANY(%(ids)s)
"""


class KnowledgeBase:
    def __init__(
        self,
        pool: DictPool,
        embedder: Embedder,
        default_mode: SearchMode = "hybrid",
        keyword_weight: float = 1.0,
        candidates: int = 20,
    ) -> None:
        self._pool = pool
        self._embedder = embedder
        self._default_mode = default_mode
        self._keyword_weight = keyword_weight
        self._candidates = candidates

    async def search(
        self, query: str, k: int, mode: SearchMode | None = None
    ) -> list[RetrievedChunk]:
        mode = mode or self._default_mode
        qvec = to_pgvector(await self._embedder.embed_query(query))
        params = {"qvec": qvec, "qtext": query, "limit": self._candidates}
        async with self._pool.connection() as conn:
            rankings: list[list[str]] = []
            weights: list[float] = []
            if mode in ("hybrid", "vector"):
                cur = await conn.execute(_VECTOR_SQL, params)
                rankings.append([row["id"] for row in await cur.fetchall()])
                weights.append(1.0)
            if mode in ("hybrid", "keyword"):
                cur = await conn.execute(_KEYWORD_SQL, params)
                rankings.append([row["id"] for row in await cur.fetchall()])
                weights.append(self._keyword_weight if mode == "hybrid" else 1.0)

            fused = reciprocal_rank_fusion(rankings, weights=weights)[:k]
            if not fused:
                return []
            cur = await conn.execute(_FETCH_SQL, {"qvec": qvec, "ids": [i for i, _ in fused]})
            rows = {row["id"]: row for row in await cur.fetchall()}

        return [
            RetrievedChunk(
                id=chunk_id,
                doc_slug=rows[chunk_id]["doc_slug"],
                doc_title=rows[chunk_id]["doc_title"],
                heading=rows[chunk_id]["heading"],
                content=rows[chunk_id]["content"],
                similarity=float(rows[chunk_id]["similarity"]),
                score=score,
            )
            for chunk_id, score in fused
            if chunk_id in rows
        ]
