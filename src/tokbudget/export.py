"""Export raw ledger entries."""

import csv
import json
import sys
from pathlib import Path
from typing import TextIO

from .ledger import Ledger


def export_entries(
    ledger: Ledger,
    days: int | None = None,
    fmt: str = "csv",
    out: str | None = None,
):
    since = None
    if days is not None:
        from .ledger import window_start

        since = window_start(days)

    entries = ledger.entries_all(since)
    fieldnames = [
        "timestamp",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "note",
    ]

    if out is None:
        handle: TextIO = sys.stdout
        close_handle = False
    else:
        path = Path(out)
        # Try to open for writing - will raise if unwritable
        try:
            handle = open(path, "w", encoding="utf-8", newline="")
        except Exception:
            raise ValueError(f"cannot write to {out}")
        close_handle = True

    try:
        if fmt == "csv":
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()
            for row in entries:
                data = dict(row)
                cost = data.get("cost_usd")
                if cost is None:
                    data["cost_usd"] = ""
                else:
                    data["cost_usd"] = cost
                writer.writerow({k: ("" if data.get(k) is None and k != "cost_usd" else data.get(k)) for k in fieldnames})
        elif fmt == "json":
            out_list = []
            for row in entries:
                data = dict(row)
                cost = data.get("cost_usd")
                out_list.append(
                    {
                        "timestamp": data.get("timestamp"),
                        "provider": data.get("provider"),
                        "model": data.get("model"),
                        "input_tokens": int(data.get("input_tokens") or 0),
                        "output_tokens": int(data.get("output_tokens") or 0),
                        "cost_usd": None if cost is None else float(cost),
                        "note": data.get("note"),
                    }
                )
            json.dump(out_list, handle)
        else:
            raise ValueError(f"unknown format {fmt}")
    finally:
        if close_handle:
            handle.close()
