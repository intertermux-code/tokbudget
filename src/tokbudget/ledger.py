"""SQLite ledger: schema, writes, and the aggregates the report renders."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS usage_timestamp ON usage(timestamp);
CREATE INDEX IF NOT EXISTS usage_model ON usage(provider, model);
"""

UTC_FORMAT = "%Y-%m-%d %H:%M:%S"


def default_db_path() -> Path:
    return Path.home() / ".tokbudget" / "ledger.db"


def to_utc(value: datetime) -> str:
    """Render a datetime the way the ledger stores it: UTC, second resolution."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime(UTC_FORMAT)


def window_start(days: int, now: datetime | None = None) -> str:
    """Inclusive lower bound for "last N days", aligned to local midnight."""
    if days < 1:
        raise ValueError("days must be at least 1")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    anchor = current.astimezone() - timedelta(days=days - 1)
    return to_utc(anchor.replace(hour=0, minute=0, second=0, microsecond=0))


def local_date(stored: str) -> str:
    """Local calendar day for a stored UTC timestamp."""
    moment = datetime.strptime(stored, UTC_FORMAT).replace(tzinfo=timezone.utc)
    return moment.astimezone().date().isoformat()


def week_label(stored: str) -> str:
    """ISO week label like 2026-W41 for a stored UTC timestamp."""
    moment = datetime.strptime(stored, UTC_FORMAT).replace(tzinfo=timezone.utc)
    local = moment.astimezone()
    isocal = local.isocalendar()
    return f"{isocal[0]:04d}-W{isocal[1]:02d}"


class Ledger:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def add(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float | None = None,
        note: str | None = None,
        timestamp: datetime | None = None,
    ) -> int:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must not be negative")
        cursor = self.conn.execute(
            """
            INSERT INTO usage (timestamp, provider, model, input_tokens,
                               output_tokens, cost_usd, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                to_utc(timestamp or datetime.now(timezone.utc)),
                provider,
                model,
                input_tokens,
                output_tokens,
                cost_usd,
                note,
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def entries(self, since: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM usage"
        args: tuple = ()
        if since:
            sql += " WHERE timestamp >= ?"
            args = (since,)
        return self.conn.execute(sql + " ORDER BY timestamp, id", args).fetchall()

    def entries_all(self, since: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT timestamp, provider, model, input_tokens, output_tokens, cost_usd, note FROM usage"
        args: tuple = ()
        if since:
            sql += " WHERE timestamp >= ?"
            args = (since,)
        return self.conn.execute(sql + " ORDER BY timestamp, id", args).fetchall()

    def daily(self, since: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT date(timestamp, 'localtime') AS day,
                   COUNT(*) AS entries,
                   SUM(input_tokens) AS input_tokens,
                   SUM(output_tokens) AS output_tokens,
                   SUM(cost_usd) AS cost_usd,
                   SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) AS unpriced
            FROM usage
            WHERE timestamp >= ?
            GROUP BY day
            ORDER BY day
            """,
            (since,),
        ).fetchall()

    def weekly(self, since: str) -> list[sqlite3.Row]:
        rows = self.conn.execute(
            """
            SELECT timestamp, input_tokens, output_tokens, cost_usd
            FROM usage
            WHERE timestamp >= ?
            """,
            (since,),
        ).fetchall()
        buckets: dict[str, dict] = {}
        for r in rows:
            key = week_label(r["timestamp"])
            b = buckets.setdefault(
                key,
                {
                    "entries": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_sum": 0.0,
                    "priced_count": 0,
                    "unpriced": 0,
                },
            )
            b["entries"] += 1
            b["input_tokens"] += int(r["input_tokens"] or 0)
            b["output_tokens"] += int(r["output_tokens"] or 0)
            if r["cost_usd"] is None:
                b["unpriced"] += 1
            else:
                b["cost_sum"] += float(r["cost_usd"] or 0.0)
                b["priced_count"] += 1
        result = []
        for k, v in sorted(buckets.items(), key=lambda x: x[0]):
            cost_usd = v["cost_sum"] if v["priced_count"] > 0 else None
            result.append(
                {
                    "week": k,
                    "entries": v["entries"],
                    "input_tokens": v["input_tokens"],
                    "output_tokens": v["output_tokens"],
                    "cost_usd": cost_usd,
                }
            )
        return result

    def by_provider(self, since: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT provider,
                   COUNT(*) AS entries,
                   SUM(input_tokens) AS input_tokens,
                   SUM(output_tokens) AS output_tokens,
                   SUM(cost_usd) AS cost_usd,
                   SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) AS unpriced
            FROM usage
            WHERE timestamp >= ?
            GROUP BY provider
            ORDER BY provider
            """,
            (since,),
        ).fetchall()

    def by_model(self, since: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT provider || '/' || model AS model,
                   COUNT(*) AS entries,
                   SUM(input_tokens) AS input_tokens,
                   SUM(output_tokens) AS output_tokens,
                   SUM(cost_usd) AS cost_usd,
                   SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) AS unpriced
            FROM usage
            WHERE timestamp >= ?
            GROUP BY provider, model
            ORDER BY cost_usd DESC, model
            """,
            (since,),
        ).fetchall()

    def totals(self, since: str) -> sqlite3.Row:
        return self.conn.execute(
            """
            SELECT COUNT(*) AS entries,
                   COALESCE(SUM(input_tokens), 0) AS input_tokens,
                   COALESCE(SUM(output_tokens), 0) AS output_tokens,
                   SUM(cost_usd) AS cost_usd,
                   SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) AS unpriced
            FROM usage
            WHERE timestamp >= ?
            """,
            (since,),
        ).fetchone()
