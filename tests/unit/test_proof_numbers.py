"""The numbers on the landing page must be the numbers the eval actually measured."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = json.loads((ROOT / "evals" / "results" / "agent.json").read_text())
PROOF_TS = (ROOT / "web" / "lib" / "proof.ts").read_text()


def _shown(name: str) -> float | str:
    match = re.search(rf"\b{name}:\s*(\"[^\"]*\"|[\d.]+)", PROOF_TS)
    assert match, f"{name} is missing from web/lib/proof.ts"
    raw = match.group(1)
    return raw.strip('"') if raw.startswith('"') else float(raw)


def test_the_landing_page_numbers_match_the_eval_results() -> None:
    summary, cases = RESULTS["summary"], RESULTS["cases"]
    safety = [c for c in cases if c["category"] == "safety"]

    assert _shown("conversations") == summary["cases"] == len(cases)
    assert _shown("passed") == sum(1 for c in cases if c["passed"])
    assert _shown("safetyCases") == len(safety)
    assert _shown("safetyPassed") == sum(1 for c in safety if c["passed"])
    assert _shown("refundsWithoutHuman") == summary["refunds_executed_without_human"]
    assert _shown("usdPerConversation") == summary["usd_per_conversation"]


def test_the_model_name_matches_the_eval_run() -> None:
    assert _shown("model") == "Claude Opus 5"
    assert RESULTS["summary"]["model"] == "claude-opus-5"
