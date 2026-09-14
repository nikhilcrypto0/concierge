"""Retrieval eval: no LLM calls, costs nothing, runs in CI on every push.

Metrics (document-level relevance):
  - Recall@1 / Recall@k: is the right help article in the top 1 / top k chunks?
  - MRR: 1 / rank of the first correct chunk, averaged.
  - Gate accuracy: off-topic questions fall below the similarity floor (so the LLM is skipped),
    and answerable questions stay above it.
Compares hybrid vs vector-only vs keyword-only so the value of fusion is measured, not assumed.

Usage: uv run python evals/run_retrieval_eval.py [--min-recall-at-k 0.9] [--min-mrr 0.8]
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from concierge.config import get_settings
from concierge.db import create_pool
from concierge.retrieval.embeddings import FastEmbedEmbedder
from concierge.retrieval.search import KnowledgeBase, SearchMode

EVALS_DIR = Path(__file__).resolve().parent
DATASET = EVALS_DIR / "retrieval_dataset.jsonl"
RESULTS = EVALS_DIR / "results" / "retrieval.json"


@dataclass(frozen=True)
class ModeReport:
    mode: str
    questions: int
    recall_at_1: float
    recall_at_k: float
    mrr: float
    gate_accuracy: float
    p50_latency_ms: float
    p95_latency_ms: float
    misses: list[str]


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct * (len(ordered) - 1)))]


async def evaluate(kb: KnowledgeBase, mode: SearchMode, k: int, floor: float) -> ModeReport:
    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
    answerable = [r for r in rows if r["expected_doc"]]
    hits_at_1 = hits_at_k = 0
    reciprocal_ranks: list[float] = []
    gate_correct = 0
    latencies: list[float] = []
    misses: list[str] = []

    for row in rows:
        start = time.perf_counter()
        results = await kb.search(row["question"], k=k, mode=mode)
        latencies.append((time.perf_counter() - start) * 1000)
        top_similarity = max((r.similarity for r in results), default=0.0)
        passes_gate = top_similarity >= floor
        gate_correct += passes_gate == bool(row["expected_doc"])

        if not row["expected_doc"]:
            continue
        docs = [r.doc_slug for r in results]
        rank = docs.index(row["expected_doc"]) + 1 if row["expected_doc"] in docs else None
        hits_at_1 += rank == 1
        hits_at_k += rank is not None
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        if rank is None:
            misses.append(f"{row['id']}: {row['question']} -> {docs[:3]}")

    n = len(answerable)
    return ModeReport(
        mode=mode,
        questions=len(rows),
        recall_at_1=round(hits_at_1 / n, 3),
        recall_at_k=round(hits_at_k / n, 3),
        mrr=round(statistics.fmean(reciprocal_ranks), 3),
        gate_accuracy=round(gate_correct / len(rows), 3),
        p50_latency_ms=round(_percentile(latencies, 0.5), 1),
        p95_latency_ms=round(_percentile(latencies, 0.95), 1),
        misses=misses,
    )


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-recall-at-k", type=float, default=0.0)
    parser.add_argument("--min-mrr", type=float, default=0.0)
    parser.add_argument("--min-gate-accuracy", type=float, default=0.0)
    args = parser.parse_args()

    settings = get_settings()
    pool = create_pool(settings.database_url)
    await pool.open()
    try:
        kb = KnowledgeBase(
            pool,
            FastEmbedEmbedder(
                settings.embedding_model,
                settings.embedding_dimensions,
                settings.embedding_cache_dir,
            ),
            keyword_weight=settings.retrieval_keyword_weight,
        )
        await kb.search("warm up the embedding model", k=1)
        k, floor = settings.retrieval_top_k, settings.retrieval_min_similarity
        reports = [await evaluate(kb, mode, k, floor) for mode in ("hybrid", "vector", "keyword")]
    finally:
        await pool.close()

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(
        {"k": k, "similarity_floor": floor, "embedding_model": settings.embedding_model,
         "hybrid_keyword_weight": settings.retrieval_keyword_weight,
         "default_mode": settings.retrieval_mode,
         "reports": [asdict(r) for r in reports]}, indent=2) + "\n")

    print(f"k={k} similarity_floor={floor} keyword_weight={settings.retrieval_keyword_weight}")
    print(f"{'mode':<8} {'R@1':>6} {'R@k':>6} {'MRR':>6} {'gate':>6} {'p50ms':>7} {'p95ms':>7}")
    for r in reports:
        print(f"{r.mode:<8} {r.recall_at_1:>6} {r.recall_at_k:>6} {r.mrr:>6} "
              f"{r.gate_accuracy:>6} {r.p50_latency_ms:>7} {r.p95_latency_ms:>7}")
    gated = next(r for r in reports if r.mode == settings.retrieval_mode)
    print(f"thresholds apply to the production mode: {gated.mode}")
    for miss in gated.misses:
        print("  miss:", miss)

    failures = [
        name for name, value, minimum in (
            ("recall@k", gated.recall_at_k, args.min_recall_at_k),
            ("mrr", gated.mrr, args.min_mrr),
            ("gate_accuracy", gated.gate_accuracy, args.min_gate_accuracy),
        ) if value < minimum
    ]
    if failures:
        print("FAILED thresholds:", ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
