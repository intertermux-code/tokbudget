from datetime import datetime, timedelta, timezone

import pytest

from tokbudget.ledger import Ledger, local_date, to_utc, window_start

NOW = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone.utc)


def column_names(ledger):
    return [row[1] for row in ledger.conn.execute("PRAGMA table_info(usage)")]


def test_creates_database_and_parent_directories(tmp_path):
    path = tmp_path / "nested" / "somewhere" / "ledger.db"
    with Ledger(path):
        pass
    assert path.exists()


def test_schema_matches_the_documented_columns(ledger):
    assert column_names(ledger) == [
        "id", "timestamp", "provider", "model",
        "input_tokens", "output_tokens", "cost_usd", "note",
    ]


def test_cost_usd_is_nullable(ledger):
    assert "cost_usd" in column_names(ledger)
    ledger.add("openai", "gpt-4o", 10, 10, cost_usd=None)
    assert ledger.entries()[0]["cost_usd"] is None


def test_add_returns_row_ids_that_increase(ledger):
    first = ledger.add("openai", "gpt-4o", 10, 5, 0.001)
    second = ledger.add("openai", "gpt-4o", 10, 5, 0.001)
    assert second > first


def test_round_trip_of_every_field(ledger):
    moment = datetime(2026, 3, 4, 8, 30, 15, tzinfo=timezone.utc)
    ledger.add("google", "gemini-2.5-flash", 1234, 567, 0.0018, "notes app",
               timestamp=moment)
    row = ledger.entries()[0]
    assert (row["timestamp"], row["provider"], row["model"]) == (
        "2026-03-04 08:30:15", "google", "gemini-2.5-flash",
    )
    assert (row["input_tokens"], row["output_tokens"], row["cost_usd"], row["note"]) == (
        1234, 567, 0.0018, "notes app",
    )


def test_negative_token_counts_are_rejected(ledger):
    with pytest.raises(ValueError):
        ledger.add("openai", "gpt-4o", -1, 5, 0.0)
    with pytest.raises(ValueError):
        ledger.add("openai", "gpt-4o", 5, -1, 0.0)


def test_reopening_an_existing_ledger_keeps_rows(tmp_path):
    path = tmp_path / "ledger.db"
    with Ledger(path) as first:
        first.add("openai", "gpt-4o", 100, 50, 0.001)
    with Ledger(path) as second:
        assert len(second.entries()) == 1


def test_to_utc_normalises_naive_and_converts():
    assert to_utc(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02 03:04:05"
    eastern = datetime(2026, 1, 1, 19, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert to_utc(eastern) == "2026-01-02 00:00:00"


def test_window_start_rejects_non_positive_days():
    with pytest.raises(ValueError):
        window_start(0, NOW)


def test_window_start_is_local_midnight():
    local_midnight = NOW.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    assert window_start(1, NOW) == to_utc(local_midnight)


def test_window_start_grows_with_the_number_of_days():
    one = datetime.fromisoformat(window_start(1, NOW))
    seven = datetime.fromisoformat(window_start(7, NOW))
    assert (one - seven).days == 6


def test_entries_since_filters_older_rows(ledger):
    ledger.add("openai", "gpt-4o", 10, 10, 0.001, timestamp=NOW)
    ledger.add("openai", "gpt-4o", 10, 10, 0.001,
               timestamp=NOW - timedelta(days=30))
    assert len(ledger.entries(window_start(7, NOW))) == 1


def test_entries_come_back_newest_first(ledger):
    for hours_ago in (0, 3, 6):
        ledger.add("openai", "gpt-4o", 10, 10, 0.001,
                   timestamp=NOW - timedelta(hours=hours_ago))
    assert [row["timestamp"] for row in ledger.entries()] == [
        "2026-10-16 12:00:00", "2026-10-16 09:00:00", "2026-10-16 06:00:00",
    ]


def test_entries_tie_on_the_second_breaks_by_id(ledger):
    first = ledger.add("openai", "gpt-4o", 10, 10, 0.001, timestamp=NOW)
    second = ledger.add("anthropic", "claude-sonnet-4", 10, 10, 0.001,
                        timestamp=NOW)
    assert [row["id"] for row in ledger.entries()] == [second, first]


def test_entries_all_matches_the_entry_order(ledger):
    ledger.add("openai", "gpt-4o", 10, 10, 0.001, timestamp=NOW)
    ledger.add("google", "gemini-2.5-flash", 10, 10, 0.001, timestamp=NOW)
    ledger.add("deepseek", "deepseek-chat", 10, 10, 0.001,
               timestamp=NOW - timedelta(days=1))
    export_keys = [(row["timestamp"], row["provider"])
                   for row in ledger.entries_all()]
    assert export_keys == [
        ("2026-10-16 12:00:00", "google"),
        ("2026-10-16 12:00:00", "openai"),
        ("2026-10-15 12:00:00", "deepseek"),
    ]
    assert export_keys == [(row["timestamp"], row["provider"])
                           for row in ledger.entries()]


def test_entries_all_since_filters_without_losing_the_order(ledger):
    for days_ago in (0, 1, 20):
        ledger.add("openai", "gpt-4o", 10, 10, 0.001,
                   timestamp=NOW - timedelta(days=days_ago))
    rows = ledger.entries_all(window_start(7, NOW))
    assert [row["timestamp"] for row in rows] == [
        "2026-10-16 12:00:00", "2026-10-15 12:00:00",
    ]


def test_daily_groups_by_local_day(ledger):
    ledger.add("openai", "gpt-4o", 1000, 200, 0.005, timestamp=NOW)
    ledger.add("openai", "gpt-4o", 500, 100, 0.002, timestamp=NOW - timedelta(hours=26))
    rows = ledger.daily(window_start(7, NOW))
    assert [row["day"] for row in rows] == [local_date("2026-10-15 10:00:00"),
                                            local_date("2026-10-16 12:00:00")]
    assert rows[1]["input_tokens"] == 1000


def test_by_model_aggregates_and_orders_by_cost(ledger):
    ledger.add("openai", "gpt-4o", 1000, 200, 0.005, timestamp=NOW)
    ledger.add("openai", "gpt-4o", 1000, 200, 0.005, timestamp=NOW)
    ledger.add("anthropic", "claude-sonnet-4", 8000, 1500, 0.0465, timestamp=NOW)
    rows = ledger.by_model(window_start(7, NOW))
    assert [row["model"] for row in rows] == [
        "anthropic/claude-sonnet-4", "openai/gpt-4o",
    ]
    assert rows[1]["entries"] == 2
    assert rows[1]["cost_usd"] == pytest.approx(0.01)


def test_totals_counts_unpriced_entries_separately(ledger):
    ledger.add("openai", "gpt-4o", 100, 10, 0.001, timestamp=NOW)
    ledger.add("openai", "gpt-5-turbo", 100, 10, None, timestamp=NOW)
    totals = ledger.totals(window_start(7, NOW))
    assert totals["entries"] == 2
    assert totals["input_tokens"] == 200
    assert totals["output_tokens"] == 20
    assert totals["unpriced"] == 1
    assert totals["cost_usd"] == pytest.approx(0.001)


def test_totals_on_an_empty_ledger(ledger):
    totals = ledger.totals(window_start(7, NOW))
    assert totals["entries"] == 0
    assert totals["input_tokens"] == 0
    assert totals["cost_usd"] is None
