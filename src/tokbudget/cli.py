"""Command line interface: argparse only, no third-party dependencies."""

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .ledger import Ledger, default_db_path
from .pricing import catalogue, estimate
from .report import format_money, report, table


def resolve_db_path(explicit: str | None) -> Path:
    candidate = explicit or os.environ.get("TOKBUDGET_DB") or default_db_path()
    return Path(candidate).expanduser()


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer")
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tokbudget",
        description="Local-first ledger of LLM token usage and estimated cost.",
        epilog="The ledger is a plain SQLite file; point --db anywhere you like.",
    )
    parser.add_argument(
        "--version", action="version", version=f"tokbudget {__version__}"
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        help="ledger file (default: $TOKBUDGET_DB, else ~/.tokbudget/ledger.db)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    log = subparsers.add_parser("log", help="record one usage entry")
    log.add_argument("--provider", required=True, help="e.g. openai, anthropic, google")
    log.add_argument("--model", required=True, help="e.g. gpt-4o, claude-sonnet-4")
    log.add_argument("--in", dest="in_tokens", type=int, required=True, metavar="N",
                     help="prompt/input tokens")
    log.add_argument("--out", dest="out_tokens", type=int, required=True, metavar="N",
                     help="completion/output tokens")
    log.add_argument("--cost", type=float, metavar="USD",
                     help="actual cost; omit to estimate from the built-in price table")
    log.add_argument("--note", help="free-form label for the entry")
    log.set_defaults(handler=cmd_log)

    rep = subparsers.add_parser("report", help="spend per day, per model, and totals")
    rep.add_argument("--days", type=positive_int, default=7, metavar="N",
                     help="window in days, counted back from today (default: 7)")
    rep.set_defaults(handler=cmd_report)

    prov = subparsers.add_parser("providers", help="show the built-in price table")
    prov.set_defaults(handler=cmd_providers)

    return parser


def cmd_log(args: argparse.Namespace, ledger: Ledger) -> int:
    provider = args.provider.strip().lower()
    model = args.model.strip().lower()
    note = args.note
    cost = args.cost
    estimated = cost is None

    if estimated:
        cost = estimate(provider, model, args.in_tokens, args.out_tokens)
        if cost is None and note is None:
            note = f"unpriced: {provider}/{model} is not in the price table"

    ledger.add(
        provider=provider,
        model=model,
        input_tokens=args.in_tokens,
        output_tokens=args.out_tokens,
        cost_usd=cost,
        note=note,
    )

    origin = " (estimated)" if estimated and cost is not None else ""
    print(
        f"Logged {args.in_tokens:,} in / {args.out_tokens:,} out for "
        f"{provider}/{model} — {format_money(cost)}{origin}"
    )
    if estimated and cost is None:
        print(
            "No price for this model: stored cost as n/a. "
            "Run `tokbudget providers` to see what is priced.",
            file=sys.stderr,
        )
    return 0


def cmd_report(args: argparse.Namespace, ledger: Ledger) -> int:
    sys.stdout.write(report(ledger, days=args.days))
    return 0


def cmd_providers(_args: argparse.Namespace, _ledger: Ledger | None) -> int:
    rows = [
        [provider, model, f"${price.input_per_million:,.2f}",
         f"${price.output_per_million:,.2f}"]
        for provider, model, price in catalogue()
    ]
    sys.stdout.write(
        "Prices in USD per 1,000,000 tokens\n\n"
        + table(["PROVIDER", "MODEL", "INPUT", "OUTPUT"], rows, align="llrr")
        + "\nA model that is missing here still logs — with cost n/a, "
        "instead of a guess.\n"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "providers":
        return args.handler(args, None)
    with Ledger(resolve_db_path(args.db)) as ledger:
        try:
            return args.handler(args, ledger)
        except ValueError as error:
            print(f"tokbudget: {error}", file=sys.stderr)
            return 2


if __name__ == "__main__":
    sys.exit(main())
