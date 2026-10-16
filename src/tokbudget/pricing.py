"""Hard-coded USD price table, used to estimate cost when --cost is omitted.

Prices are dollars per one million tokens as published by the providers during
2025. The table is deliberately small: it covers representative models only,
and anything missing is logged with a NULL cost rather than a guessed one.
"""

from dataclasses import dataclass

PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "openai": {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4.1": (2.00, 8.00),
        "gpt-4.1-mini": (0.40, 1.60),
        "o4-mini": (1.10, 4.40),
    },
    "anthropic": {
        "claude-opus-4": (15.00, 75.00),
        "claude-sonnet-4": (3.00, 15.00),
        "claude-3-7-sonnet": (3.00, 15.00),
        "claude-3-5-haiku": (0.80, 4.00),
    },
    "google": {
        "gemini-2.5-pro": (1.25, 10.00),
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-2.0-flash": (0.10, 0.40),
    },
    "qwen": {
        "qwen-max": (1.60, 6.40),
        "qwen-plus": (0.40, 1.20),
        "qwen-turbo": (0.05, 0.20),
    },
    "deepseek": {
        "deepseek-chat": (0.27, 1.10),
        "deepseek-reasoner": (0.55, 2.19),
    },
}

TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class Price:
    input_per_million: float
    output_per_million: float

    @property
    def total_per_million(self) -> float:
        return self.input_per_million + self.output_per_million


def lookup(provider: str, model: str) -> Price | None:
    """Return the price pair for (provider, model), or None when unpriced."""
    models = PRICING.get(provider.strip().lower())
    if models is None:
        return None
    quoted = models.get(model.strip().lower())
    if quoted is None:
        return None
    return Price(*quoted)


def estimate(provider: str, model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Cost in USD for a single call, or None if the model has no price."""
    price = lookup(provider, model)
    if price is None:
        return None
    cost = (
        input_tokens / TOKENS_PER_MILLION * price.input_per_million
        + output_tokens / TOKENS_PER_MILLION * price.output_per_million
    )
    return round(cost, 6)


def catalogue() -> list[tuple[str, str, Price]]:
    """All known models, sorted by provider then model, for `tokbudget providers`."""
    return [
        (provider, model, Price(*quoted))
        for provider in sorted(PRICING)
        for model, quoted in sorted(PRICING[provider].items())
    ]
