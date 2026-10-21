import csv
import io
import json
from contextlib import redirect_stdout
from datetime import datetime, timezone

from tokbudget import cli
from tokbudget.ledger import Ledger


def run(db, *argv):
    return cli.main(["--db", str(db), *argv])


def test_export_csv_has_expected_columns(tmp_path):
    db = tmp_path / "ledger.db"
    run(db, "log", "--provider", "openai", "--model", "gpt-4o", "--in", "100", "--out", "10", "--cost", "0.001")
    out = io.StringIO()
    with redirect_stdout(out):
        rc = run(db, "export", "--format", "csv")
    assert rc == 0
    rows = list(csv.DictReader(io.StringIO(out.getvalue())))
    assert set(rows[0].keys()) == {"timestamp", "provider", "model", "input_tokens", "output_tokens", "cost_usd", "note"}


def test_export_json_parses_as_list_of_objects(tmp_path):
    db = tmp_path / "ledger.db"
    run(db, "log", "--provider", "openai", "--model", "gpt-4o", "--in", "100", "--out", "10", "--cost", "0.001")
    out = io.StringIO()
    with redirect_stdout(out):
        rc = run(db, "export", "--format", "json")
    assert rc == 0
    data = json.loads(out.getvalue())
    assert isinstance(data, list)
    assert isinstance(data[0], dict)


def test_export_stdout_default_is_csv(tmp_path):
    db = tmp_path / "ledger.db"
    run(db, "log", "--provider", "openai", "--model", "gpt-4o", "--in", "100", "--out", "10", "--cost", "0.001")
    out = io.StringIO()
    with redirect_stdout(out):
        rc = run(db, "export")
    assert rc == 0
    assert out.getvalue().startswith("timestamp,provider,model")


def test_export_empty_ledger_behaves_friendly(tmp_path):
    db = tmp_path / "ledger.db"
    out = io.StringIO()
    with redirect_stdout(out):
        rc = run(db, "export")
    assert rc == 0
    assert "timestamp" in out.getvalue()


def seed_three_days(db):
    """Oldest to newest, so an ascending read order is visibly wrong."""
    with Ledger(db) as ledger:
        for hour, model in ((8, "gpt-4o"), (9, "gpt-4o-mini"), (10, "claude-sonnet-4")):
            ledger.add("openai", model, 100, 10, 0.001,
                       timestamp=datetime(2026, 10, 16, hour, tzinfo=timezone.utc))


def test_export_lists_rows_newest_first(tmp_path):
    db = tmp_path / "ledger.db"
    seed_three_days(db)
    out = io.StringIO()
    with redirect_stdout(out):
        assert run(db, "export", "--format", "csv") == 0
    rows = list(csv.DictReader(io.StringIO(out.getvalue())))
    assert [row["model"] for row in rows] == [
        "claude-sonnet-4", "gpt-4o-mini", "gpt-4o",
    ]
    assert [row["timestamp"] for row in rows] == [
        "2026-10-16 10:00:00", "2026-10-16 09:00:00", "2026-10-16 08:00:00",
    ]


def test_export_json_lists_rows_newest_first(tmp_path):
    db = tmp_path / "ledger.db"
    seed_three_days(db)
    out = io.StringIO()
    with redirect_stdout(out):
        assert run(db, "export", "--format", "json") == 0
    assert [entry["model"] for entry in json.loads(out.getvalue())] == [
        "claude-sonnet-4", "gpt-4o-mini", "gpt-4o",
    ]
