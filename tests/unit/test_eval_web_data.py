"""The /evals page shows web/lib/eval-data.json, which must be exactly what the results say."""

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _exporter() -> ModuleType:
    path = ROOT / "evals" / "export_web_data.py"
    spec = importlib.util.spec_from_file_location("export_web_data", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_web_data_matches_the_eval_results() -> None:
    exporter = _exporter()
    committed = (ROOT / "web" / "lib" / "eval-data.json").read_text()
    assert committed == exporter.render(exporter.build()), (
        "web/lib/eval-data.json is stale: run `uv run python evals/export_web_data.py`"
    )


def test_every_case_has_a_result_for_every_model() -> None:
    data = _exporter().build()
    models = {run["key"] for run in data["runs"]}
    assert len(data["cases"]) == data["runs"][0]["cases"]
    for case in data["cases"]:
        assert set(case["results"]) == models, case["id"]
