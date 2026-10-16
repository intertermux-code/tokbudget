import io
from contextlib import redirect_stdout

from tokbudget import cli


def run(db, *argv):
    return cli.main(["--db", str(db), *argv])


def test_report_week_grouping_rollups_correctly(tmp_path):
    db = tmp_path / "ledger.db"
    run(db, "log", "--provider", "openai", "--model", "gpt-4o", "--in", "100", "--out", "10", "--cost", "0.001")
    run(db, "log", "--provider", "anthropic", "--model", "claude-sonnet-4", "--in", "200", "--out", "20", "--cost", "0.002")
    out = io.StringIO()
    with redirect_stdout(out):
        rc = run(db, "report", "--group-by", "week")
    assert rc == 0
    text = out.getvalue()
    assert "Per week" in text


def test_report_provider_grouping_rollups_correctly(tmp_path):
    db = tmp_path / "ledger.db"
    run(db, "log", "--provider", "openai", "--model", "gpt-4o", "--in", "100", "--out", "10", "--cost", "0.001")
    run(db, "log", "--provider", "anthropic", "--model", "claude-sonnet-4", "--in", "200", "--out", "20", "--cost", "0.002")
    out = io.StringIO()
    with redirect_stdout(out):
        rc = run(db, "report", "--group-by", "provider")
    assert rc == 0
    text = out.getvalue()
    assert "Per provider" in text
