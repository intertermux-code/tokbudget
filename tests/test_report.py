from datetime import datetime, timedelta, timezone

from tokbudget.report import format_money, format_tokens, report, table

NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)


def test_format_money_none_is_not_applicable():
    assert format_money(None) == "n/a"


def test_format_money_shows_four_places():
    assert format_money(0.006) == "$0.0060"
    assert format_money(12.5) == "$12.5000"


def test_format_tokens_uses_thousands_separators():
    assert format_tokens(1234567) == "1,234,567"
    assert format_tokens(None) == "0"


def test_table_pads_columns_and_honours_alignment():
    rendered = table(
        ["NAME", "COST"],
        [["openai/gpt-4o", "$0.0060"], ["x", "$1.00"]],
        align="lr",
    )
    lines = rendered.rstrip("\n").split("\n")
    assert lines[0].split() == ["NAME", "COST"]
    assert lines[1].startswith("openai/gpt-4o")
    assert lines[1].index("$0.0060") + len("$0.0060") == (
        lines[2].index("$1.00") + len("$1.00")
    )


def test_report_says_so_when_the_window_is_empty(ledger):
    text = report(ledger, days=7, now=NOW)
    assert "No usage recorded in the last 7 days" in text
    assert "tokbudget log" in text


def test_report_sections_and_totals(ledger):
    ledger.add("openai", "gpt-4o", 1200, 300, 0.006, timestamp=NOW)
    text = report(ledger, days=7, now=NOW)
    assert "Per day" in text
    assert "Per model" in text
    assert "Totals" in text
    assert "openai/gpt-4o" in text
    assert "1,200" in text and "300" in text
    assert "$0.0060" in text


def test_report_flags_unpriced_entries(ledger):
    ledger.add("openai", "gpt-4o", 1000, 200, 0.005, timestamp=NOW)
    ledger.add("openai", "gpt-5-turbo", 400, 80, None, timestamp=NOW)
    text = report(ledger, days=7, now=NOW)
    assert "1 entry had no price match" in text
    assert "openai/gpt-5-turbo" in text


def test_report_cost_is_na_when_no_entry_is_priced(ledger):
    ledger.add("mistral", "mistral-large", 400, 80, None, timestamp=NOW)
    text = report(ledger, days=7, now=NOW)
    assert "n/a" in text


def test_report_honours_the_days_window(ledger):
    ledger.add("openai", "gpt-4o", 1000, 200, 0.005, timestamp=NOW)
    ledger.add("openai", "gpt-4o", 7000, 900, 0.03,
               timestamp=NOW - timedelta(days=20))
    short = report(ledger, days=7, now=NOW)
    assert "$0.0050" in short
    assert "0.0350" not in short
    long = report(ledger, days=30, now=NOW)
    assert "$0.0350" in long


def test_report_uses_singular_day_wording(ledger):
    ledger.add("openai", "gpt-4o", 10, 1, 0.0001, timestamp=NOW)
    assert "last 1 day" in report(ledger, days=1, now=NOW)


def test_report_lists_every_day_in_the_window(ledger):
    for offset in (0, 1, 2):
        ledger.add("openai", "gpt-4o", 100, 10, 0.001,
                   timestamp=NOW - timedelta(days=offset))
    text = report(ledger, days=7, now=NOW)
    assert text.split("Per day")[1].split("Per model")[0].count("2026") == 3
