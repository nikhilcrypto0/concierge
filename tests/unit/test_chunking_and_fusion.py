from pathlib import Path

import pytest

from concierge.retrieval.chunking import chunk_markdown, load_directory
from concierge.retrieval.search import reciprocal_rank_fusion

KB_DIR = Path(__file__).resolve().parents[2] / "data" / "kb"


def test_chunks_follow_sections_with_overview() -> None:
    md = "# Title\n\nIntro text.\n\n## First\n\nAlpha.\n\n## Second\n\nBeta."
    chunks = chunk_markdown("doc", md)
    assert [(c.id, c.heading, c.content) for c in chunks] == [
        ("doc#0", "Overview", "Intro text."),
        ("doc#1", "First", "Alpha."),
        ("doc#2", "Second", "Beta."),
    ]
    assert all(c.doc_title == "Title" for c in chunks)


def test_long_sections_split_on_paragraphs() -> None:
    body = "\n\n".join(f"Paragraph {i} " + "x" * 80 for i in range(10))
    chunks = chunk_markdown("doc", f"# T\n\n## Long\n\n{body}", max_chars=300)
    assert len(chunks) > 1
    assert all(len(c.content) <= 300 for c in chunks)
    assert all(c.heading == "Long" for c in chunks)


def test_missing_title_is_rejected() -> None:
    with pytest.raises(ValueError, match="Title"):
        chunk_markdown("doc", "## Section only\n\ntext")


def test_content_hash_changes_with_content() -> None:
    a = chunk_markdown("doc", "# T\n\n## S\n\none")[0]
    b = chunk_markdown("doc", "# T\n\n## S\n\ntwo")[0]
    assert a.content_hash != b.content_hash


def test_real_knowledge_base_chunks_cleanly() -> None:
    chunks = load_directory(KB_DIR)
    ids = [c.id for c in chunks]
    assert len(ids) == len(set(ids))
    assert {c.doc_slug for c in chunks} == {p.stem for p in KB_DIR.glob("*.md")}


def test_rrf_rewards_agreement_between_rankers() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "d"]])
    assert fused[0][0] == "b"  # ranked by both lists
    assert {item for item, _ in fused} == {"a", "b", "c", "d"}


def test_rrf_is_deterministic_on_ties() -> None:
    assert reciprocal_rank_fusion([["x"], ["y"]]) == reciprocal_rank_fusion([["y"], ["x"]])


def test_weighted_rrf_lets_the_stronger_ranker_win_disagreements() -> None:
    vector, keyword = ["relevant", "other"], ["noisy", "relevant"]
    assert reciprocal_rank_fusion([vector, keyword])[0][0] == "relevant"
    assert reciprocal_rank_fusion([vector, keyword], weights=[1.0, 0.1])[0][0] == "relevant"
    assert reciprocal_rank_fusion([["a"], ["b"]], weights=[0.2, 1.0])[0][0] == "b"


def test_rrf_rejects_mismatched_weights() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"], ["b"]], weights=[1.0])
