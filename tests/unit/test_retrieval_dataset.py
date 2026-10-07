"""The retrieval eval's section labels must point at sections that really exist."""

import json
from pathlib import Path

from concierge.retrieval.chunking import load_directory

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals" / "retrieval_dataset.jsonl"


def _rows() -> list[dict[str, object]]:
    return [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]


def test_every_answerable_question_names_a_real_section_of_its_article() -> None:
    headings: dict[str, set[str]] = {}
    for chunk in load_directory(ROOT / "data" / "kb"):
        headings.setdefault(chunk.doc_slug, set()).add(chunk.heading)

    for row in _rows():
        if row["expected_doc"] is None:
            assert "expected_heading" not in row, row["id"]
            continue
        wanted = row["expected_heading"]
        names = [wanted] if isinstance(wanted, str) else wanted
        assert isinstance(names, list) and names, row["id"]
        for name in names:
            assert name in headings[str(row["expected_doc"])], (row["id"], name)
