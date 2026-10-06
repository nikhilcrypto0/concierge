"""Model prices, in one place, so the eval report and the live cost figures cannot disagree."""

# USD per million tokens (input, output). Source: Anthropic pricing, Sept 2026.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),
}
# A model we have no price for is charged at the most expensive tier, so an unknown model can
# only make the reported cost look worse, never better. Callers also get told it was unpriced.
FALLBACK_MODEL = "claude-opus-5"


def is_priced(model: str) -> bool:
    return model in PRICES


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, PRICES[FALLBACK_MODEL])
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000
