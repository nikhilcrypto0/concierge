"""Haiku 4.5 rejects the effort setting with a 400 (found running the eval on it)."""

import pytest

from concierge.llm import effort_options


@pytest.mark.parametrize("model", ["claude-opus-5", "claude-sonnet-5"])
def test_models_that_support_effort_get_it(model: str) -> None:
    assert effort_options(model, "low") == {"output_config": {"effort": "low"}}


@pytest.mark.parametrize("model", ["claude-haiku-4-5-20251001", "claude-haiku-4-5"])
def test_haiku_gets_no_effort_option(model: str) -> None:
    assert effort_options(model, "low") == {}
