"""Prices are applied per million tokens, and an unknown model can only look more expensive."""

import pytest

from concierge.pricing import PRICES, cost_usd, is_priced


def test_a_million_tokens_each_way_costs_the_listed_price() -> None:
    assert cost_usd("claude-opus-5", 1_000_000, 1_000_000) == pytest.approx(30.0)
    assert cost_usd("claude-sonnet-5", 1_000_000, 1_000_000) == pytest.approx(12.0)


def test_input_and_output_are_priced_separately() -> None:
    assert cost_usd("claude-opus-5", 1_000, 200) == pytest.approx(0.01)  # 5 + 5 thousandths


def test_an_unknown_model_is_charged_at_the_most_expensive_tier_and_flagged() -> None:
    assert not is_priced("some-new-model")
    assert cost_usd("some-new-model", 1_000, 200) == cost_usd("claude-opus-5", 1_000, 200)
    assert cost_usd("some-new-model", 1_000, 200) >= max(
        cost_usd(model, 1_000, 200) for model in PRICES
    )
