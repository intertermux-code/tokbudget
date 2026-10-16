import pytest

from tokbudget import pricing


def test_lookup_returns_published_pair():
    price = pricing.lookup("openai", "gpt-4o")
    assert price == pricing.Price(2.50, 10.00)


def test_lookup_normalises_case_and_whitespace():
    assert pricing.lookup("  OpenAI ", " GPT-4o ") == pricing.lookup("openai", "gpt-4o")


def test_lookup_unknown_model_is_none():
    assert pricing.lookup("openai", "gpt-4.5-ultra") is None


def test_lookup_unknown_provider_is_none():
    assert pricing.lookup("mistral", "mistral-large") is None


def test_estimate_for_gpt4o():
    assert pricing.estimate("openai", "gpt-4o", 1200, 300) == 0.006


def test_estimate_for_claude_sonnet():
    cost = pricing.estimate("anthropic", "claude-sonnet-4", 8000, 1500)
    assert cost == pytest.approx(0.0465, abs=1e-9)


def test_estimate_unknown_model_is_none():
    assert pricing.estimate("google", "gemini-3-pro", 1000, 1000) is None


def test_estimate_zero_tokens_is_zero():
    assert pricing.estimate("deepseek", "deepseek-chat", 0, 0) == 0.0


def test_estimate_rounds_to_six_decimals():
    assert pricing.estimate("openai", "gpt-4o-mini", 1, 1) == 0.000001


def test_price_total_per_million():
    assert pricing.Price(2.5, 10.0).total_per_million == 12.5


def test_catalogue_covers_every_provider():
    providers = {row[0] for row in pricing.catalogue()}
    assert providers == set(pricing.PRICING)


def test_catalogue_is_sorted():
    rows = pricing.catalogue()
    assert rows == sorted(rows, key=lambda row: (row[0], row[1]))


def test_catalogue_entry_count_matches_table():
    assert len(pricing.catalogue()) == sum(len(m) for m in pricing.PRICING.values())
