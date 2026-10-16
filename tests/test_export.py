import csv
import io
import json
from contextlib import redirect_stdout

from tokbudget import cli


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
