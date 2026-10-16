"""Text rendering for `tokbudget report`."""

from datetime import datetime, timezone

from .ledger import Ledger, local_date, to_utc, window_start

NA = "n/a"
MONEY_PLACES = 4


def format_tokens(value: int | None) -> str:
    return f"{int(value or 0):,}"


def format_money(value: float | None) -> str:
    """A NULL total means no entry in the group had a price, so show n/a."""
    if value is None:
        return NA
    return f"${value:.{MONEY_PLACES}f}"


def table(headers: list[str], rows: list[list[str]], align: str) -> str:
    """Align is one 'l' or 'r' per column; the result is newline terminated."""
    widths = [
        max(len(header), *(len(row[i]) for row in rows)) if rows else len(header)
        for i, header in enumerate(headers)
    ]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths))]
    lines.extend(
        "  ".join(
            cell.ljust(w) if align[i] == "l" else cell.rjust(w)
            for i, (cell, w) in enumerate(zip(row, widths))
        )
        for row in rows
    )
    return "\n".join(line.rstrip() for line in lines) + "\n"


def report(ledger: Ledger, days: int = 7, group_by: str = "day", now: datetime | None = None) -> str:
    since = window_start(days, now)
    totals = ledger.totals(since)

    current = now or datetime.now(timezone.utc)
    first_day, last_day = local_date(since), local_date(to_utc(current))

    window = f"last {days} day{'s' if days != 1 else ''} ({first_day} to {last_day})"

    if totals["entries"] == 0:
        return (
            f"No usage recorded in the {window}.\n"
            "Log an entry with: tokbudget log --provider openai --model gpt-4o "
            "--in 1200 --out 300\n"
        )

    lines = [f"Token spend — {window}", ""]

    group_by = (group_by or "day").lower()

    if group_by == "day":
        grouped = ledger.daily(since)
        lines.append("Per day")
        lines.append(
            table(
                ["DAY", "ENTRIES", "INPUT", "OUTPUT", "COST(USD)"],
                [
                    [
                        row["day"],
                        format_tokens(row["entries"]),
                        format_tokens(row["input_tokens"]),
                        format_tokens(row["output_tokens"]),
                        format_money(row["cost_usd"]),
                    ]
                    for row in grouped
                ],
                align="lrrrr",
            ).rstrip("\n")
        )
        lines.append("")
    elif group_by == "week":
        grouped = ledger.weekly(since)
        lines.append("Per week")
        lines.append(
            table(
                ["WEEK", "ENTRIES", "INPUT", "OUTPUT", "COST(USD)"],
                [
                    [
                        row["week"],
                        format_tokens(row["entries"]),
                        format_tokens(row["input_tokens"]),
                        format_tokens(row["output_tokens"]),
                        format_money(row["cost_usd"]),
                    ]
                    for row in grouped
                ],
                align="lrrrr",
            ).rstrip("\n")
        )
        lines.append("")
    elif group_by == "provider":
        grouped = ledger.by_provider(since)
        lines.append("Per provider")
        lines.append(
            table(
                ["PROVIDER", "ENTRIES", "INPUT", "OUTPUT", "COST(USD)"],
                [
                    [
                        row["provider"],
                        format_tokens(row["entries"]),
                        format_tokens(row["input_tokens"]),
                        format_tokens(row["output_tokens"]),
                        format_money(row["cost_usd"]),
                    ]
                    for row in grouped
                ],
                align="lrrrr",
            ).rstrip("\n")
        )
        lines.append("")
    elif group_by == "model":
        grouped = ledger.by_model(since)
        lines.append("Per model")
        lines.append(
            table(
                ["MODEL", "ENTRIES", "INPUT", "OUTPUT", "COST(USD)"],
                [
                    [
                        row["model"],
                        format_tokens(row["entries"]),
                        format_tokens(row["input_tokens"]),
                        format_tokens(row["output_tokens"]),
                        format_money(row["cost_usd"]),
                    ]
                    for row in grouped
                ],
                align="lrrrr",
            ).rstrip("\n")
        )
        lines.append("")
    else:
        grouped = ledger.daily(since)
        lines.append("Per day")
        lines.append(
            table(
                ["DAY", "ENTRIES", "INPUT", "OUTPUT", "COST(USD)"],
                [
                    [
                        row["day"],
                        format_tokens(row["entries"]),
                        format_tokens(row["input_tokens"]),
                        format_tokens(row["output_tokens"]),
                        format_money(row["cost_usd"]),
                    ]
                    for row in grouped
                ],
                align="lrrrr",
            ).rstrip("\n")
        )
        lines.append("")

    models = ledger.by_model(since)
    lines.append("Per model")
    lines.append(
        table(
            ["MODEL", "ENTRIES", "INPUT", "OUTPUT", "COST(USD)"],
            [
                [
                    row["model"],
                    format_tokens(row["entries"]),
                    format_tokens(row["input_tokens"]),
                    format_tokens(row["output_tokens"]),
                    format_money(row["cost_usd"]),
                ]
                for row in models
            ],
            align="lrrrr",
        ).rstrip("\n")
    )
    lines.append("")

    lines.append("Totals")
    lines.append(
        table(
            ["ENTRIES", "INPUT", "OUTPUT", "COST(USD)"],
            [
                [
                    format_tokens(totals["entries"]),
                    format_tokens(totals["input_tokens"]),
                    format_tokens(totals["output_tokens"]),
                    format_money(totals["cost_usd"]),
                ]
            ],
            align="rrrr",
        ).rstrip("\n")
    )

    unpriced = totals["unpriced"] or 0
    if unpriced:
        subject = "1 entry had" if unpriced == 1 else f"{unpriced} entries had"
        verb = "is" if unpriced == 1 else "are"
        lines.append(
            f"{subject} no price match and {verb} excluded "
            "from the cost figures above."
        )
    return "\n".join(lines) + "\n"
