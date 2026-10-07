"""Bundle the eval results the /evals page shows into one JSON file for the web app.

The web app deploys from web/ and cannot read evals/ at build time, so this copies what it
needs. tests/unit/test_eval_web_data.py fails when the committed file differs from what this
script produces, so the page cannot drift from the real results.

Usage: uv run python evals/export_web_data.py
"""

import json
from pathlib import Path
from typing import Any

EVALS = Path(__file__).resolve().parent
RESULTS = EVALS / "results"
OUT = EVALS.parent / "web" / "lib" / "eval-data.json"

RUNS = (
    ("opus", "Claude Opus 5", "agent.json"),
    ("haiku", "Claude Haiku 4.5", "agent-54cases-haiku-4-5.json"),
)
REPLY_EXCERPT_CHARS = 240


def _read(path: Path) -> Any:
    return json.loads(path.read_text())


def _expectation(expect: dict[str, Any]) -> dict[str, Any]:
    outcome = expect["outcome"]
    return {
        "outcomes": [outcome] if isinstance(outcome, str) else outcome,
        "noApprovalRequest": bool(expect.get("no_approval_request")),
        "replyMustNotContain": expect.get("reply_excludes", []),
        "approvalAmountCents": expect.get("approval_amount_cents"),
    }


def _run_summary(summary: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    safety = [c for c in cases if c["category"] == "safety"]
    return {
        "model": summary["model"],
        "cases": len(cases),
        "passed": sum(1 for c in cases if c["passed"]),
        "safetyCases": len(safety),
        "safetyPassed": sum(1 for c in safety if c["passed"]),
        "refundsWithoutHuman": summary["refunds_executed_without_human"],
        "usdPerConversation": summary["usd_per_conversation"],
        "p50Ms": summary["turn_latency_ms"]["p50"],
        "p95Ms": summary["turn_latency_ms"]["p95"],
    }


def _case_result(case: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "passed": case["passed"],
        "outcome": case["outcome"],
        "failures": case["failures"],
    }
    if not case["passed"] and case.get("reply"):
        result["replyExcerpt"] = case["reply"][:REPLY_EXCERPT_CHARS]
    return result


def build() -> dict[str, Any]:
    dataset = [
        json.loads(line)
        for line in (EVALS / "agent_dataset.jsonl").read_text().splitlines()
        if line.strip()
    ]
    runs: list[dict[str, Any]] = []
    by_run: dict[str, dict[str, dict[str, Any]]] = {}
    for key, label, filename in RUNS:
        data = _read(RESULTS / filename)
        runs.append({"key": key, "label": label, "file": filename,
                     **_run_summary(data["summary"], data["cases"])})
        by_run[key] = {c["id"]: c for c in data["cases"]}

    cases = []
    for row in dataset:
        cases.append({
            "id": row["id"],
            "category": row["category"],
            "turns": row["turns"],
            "expect": _expectation(row["expect"]),
            "results": {key: _case_result(by_run[key][row["id"]]) for key, _, _ in RUNS},
        })

    retrieval = _read(RESULTS / "retrieval.json")
    return {
        "runs": runs,
        "cases": cases,
        "retrieval": {
            "k": retrieval["k"],
            "embeddingModel": retrieval["embedding_model"],
            "shippedMode": retrieval["default_mode"],
            "modes": [
                {
                    "mode": r["mode"],
                    "questions": r["questions"],
                    "recallAtK": r["recall_at_k"],
                    "sectionRecallAtK": r["section_recall_at_k"],
                    "mrr": r["mrr"],
                }
                for r in retrieval["reports"]
            ],
        },
    }


def render(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(build()))
    print(f"wrote {OUT.relative_to(EVALS.parent)}")
