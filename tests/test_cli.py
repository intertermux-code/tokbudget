import sqlite3

import pytest

from tokbudget.cli import main, resolve_db_path


@pytest.fixture
def db(tmp_path):
    return tmp_path / "ledger.db"


def run(db, *argv):
    return main(["--db", str(db), *argv])


def read_rows(db):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute("SELECT * FROM usage")]
    finally:
        conn.close()


def test_log_with_explicit_cost(db, capsys):
    assert run(db, "log", "--provider", "OpenAI", "--model", "GPT-4o",
               "--in", "1200", "--out", "300", "--cost", "0.012") == 0
    row = read_rows(db)[0]
    assert row["cost_usd"] == 0.012
    assert (row["provider"], row["model"]) == ("openai", "gpt-4o")
    assert "$0.0120" in capsys.readouterr().out


def test_log_estimates_cost_from_the_price_table(db, capsys):
    run(db, "log", "--provider", "openai", "--model", "gpt-4o",
        "--in", "1200", "--out", "300")
    assert read_rows(db)[0]["cost_usd"] == pytest.approx(0.006)
    out = capsys.readouterr().out
    assert "$0.0060" in out and "(estimated)" in out


def test_log_keeps_the_note_verbatim(db):
    run(db, "log", "--provider", "anthropic", "--model", "claude-sonnet-4",
        "--in", "8000", "--out", "1500", "--note", "blog draft")
    assert read_rows(db)[0]["note"] == "blog draft"


def test_log_unknown_model_stores_null_cost_and_a_note(db, capsys):
    run(db, "log", "--provider", "openai", "--model", "gpt-6-max",
        "--in", "10", "--out", "5")
    row = read_rows(db)[0]
    assert row["cost_usd"] is None
    assert "not in the price table" in row["note"]
    captured = capsys.readouterr()
    assert "n/a" in captured.out
    assert "No price for this model" in captured.err


def test_negative_tokens_exit_with_usage_error(db, capsys):
    assert run(db, "log", "--provider", "openai", "--model", "gpt-4o",
               "--in", "-5", "--out", "1") == 2
    assert "must not be negative" in capsys.readouterr().err
    assert not db.exists() or read_rows(db) == []


def test_missing_required_option_exits_two(db):
    with pytest.raises(SystemExit) as excinfo:
        run(db, "log", "--provider", "openai")
    assert excinfo.value.code == 2


def test_zero_days_is_rejected(db):
    with pytest.raises(SystemExit):
        run(db, "report", "--days", "0")


def test_report_command_prints_the_ledger(db, capsys):
    run(db, "log", "--provider", "openai", "--model", "gpt-4o",
        "--in", "4000", "--out", "1000")
    capsys.readouterr()
    assert run(db, "report") == 0
    out = capsys.readouterr().out
    assert "Per day" in out and "openai/gpt-4o" in out
    assert "$0.0200" in out


def test_report_on_a_fresh_database(db, capsys):
    run(db, "report", "--days", "1")
    assert "No usage recorded in the last 1 day" in capsys.readouterr().out


def test_providers_lists_the_price_table(db, capsys):
    assert run(db, "providers") == 0
    out = capsys.readouterr().out
    for provider in ("openai", "anthropic", "google", "qwen", "deepseek"):
        assert provider in out
    assert "$2.50" in out and "$10.00" in out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "tokbudget" in capsys.readouterr().out


def test_db_flag_wins_over_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("TOKBUDGET_DB", str(tmp_path / "from-env.db"))
    assert resolve_db_path(str(tmp_path / "flag.db")) == tmp_path / "flag.db"


def test_environment_variable_selects_the_ledger(tmp_path, monkeypatch, capsys):
    path = tmp_path / "from-env.db"
    monkeypatch.setenv("TOKBUDGET_DB", str(path))
    main(["log", "--provider", "qwen", "--model", "qwen-plus",
          "--in", "500", "--out", "100"])
    assert path.exists()
    assert read_rows(path)[0]["model"] == "qwen-plus"


def test_report_totals_cover_every_entry_in_the_window(db, capsys):
    run(db, "log", "--provider", "openai", "--model", "gpt-4o-mini",
        "--in", "1500", "--out", "400")
    run(db, "log", "--provider", "anthropic", "--model", "claude-3-5-haiku",
        "--in", "2000", "--out", "500")
    run(db, "log", "--provider", "openai", "--model", "mystery-model",
        "--in", "100", "--out", "10")
    capsys.readouterr()
    run(db, "report", "--days", "7")
    out = capsys.readouterr().out
    assert "gpt-4o-mini" in out and "claude-3-5-haiku" in out
    assert out.split("Totals")[1].splitlines()[2].split()[0] == "3"
    assert "1 entry had no price match" in out
