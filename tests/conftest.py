import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tokbudget.ledger import Ledger  # noqa: E402

NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def ledger(tmp_path):
    with Ledger(tmp_path / "ledger.db") as instance:
        yield instance


@pytest.fixture
def seeded(ledger):
    """Three days of usage: a priced model, a second call, and an unknown model."""
    ledger.add("openai", "gpt-4o", 1200, 300, 0.006, "blog draft",
               timestamp=NOW.replace(hour=9))
    ledger.add("anthropic", "claude-sonnet-4", 8000, 1500, 0.0465, None,
               timestamp=NOW.replace(hour=10))
    ledger.add("openai", "gpt-5-turbo", 500, 100, None,
               "unpriced: openai/gpt-5-turbo is not in the price table",
               timestamp=NOW.replace(hour=11))
    return ledger
