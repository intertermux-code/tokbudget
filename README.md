# tokbudget

A local-first ledger for what your LLM calls actually cost. One SQLite file,
one command per call, no account, no network, no third-party runtime dependency.

If you script against several providers — OpenAI, Anthropic, Google, Qwen,
DeepSeek — you usually learn your spend weeks later from a billing page you
have to log into. `tokbudget` keeps the numbers next to your code instead:
log each call as you make it, then ask what the week looked like.

```
Token spend — last 7 days (2026-10-10 to 2026-10-16)

Per day
DAY         ENTRIES  INPUT   OUTPUT  COST(USD)
2026-10-16        5  56,900   4,020    $0.0708

Per model
MODEL                      ENTRIES  INPUT   OUTPUT  COST(USD)
anthropic/claude-sonnet-4        1   8,000   1,500    $0.0465
google/gemini-2.5-flash          1  44,000   1,200    $0.0162
openai/gpt-4o                    1   1,200     300    $0.0060
deepseek/deepseek-chat           1   3,200     900    $0.0021
openai/gpt-6-max                 1     500     120        n/a

Totals
ENTRIES  INPUT   OUTPUT  COST(USD)
      5  56,900   4,020    $0.0708
1 entry had no price match and is excluded from the cost figures above.
```

## Install

Python 3.10 or newer. From a checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

That gives you a `tokbudget` command on your PATH. Nothing else is required at
runtime — the package uses only the standard library and `sqlite3`.

## Storage

The ledger is created on first use at `~/.tokbudget/ledger.db`. Choose another
place with the `--db` flag or the `TOKBUDGET_DB` environment variable:

```bash
tokbudget --db /Volumes/work/ledger.db report
export TOKBUDGET_DB=~/projects/agent/ledger.db
```

`--db` wins over the environment variable. Because it is one SQLite file, you
can keep a separate ledger per project, or point every project at a shared one.

Schema:

| column         | type    | notes                                        |
| -------------- | ------- | -------------------------------------------- |
| `id`           | INTEGER | primary key, assigned by SQLite              |
| `timestamp`    | TEXT    | UTC, `YYYY-MM-DD HH:MM:SS`                   |
| `provider`     | TEXT    | lower-cased on write                         |
| `model`        | TEXT    | lower-cased on write                         |
| `input_tokens` | INTEGER | prompt tokens                                |
| `output_tokens`| INTEGER | completion tokens                            |
| `cost_usd`     | REAL    | nullable — NULL means "no price was known"   |
| `note`         | TEXT    | free-form                                    |

Indexes cover `timestamp` and `(provider, model)`, which are the two axes the
report groups by. Days in a report are *your* local days: the stored timestamps
are UTC, and grouping converts them on read.

## Usage

### Log a call

```bash
tokbudget log --provider openai --model gpt-4o --in 1200 --out 300 --note "blog draft"
```

```
Logged 1,200 in / 300 out for openai/gpt-4o — $0.0060 (estimated)
```

Omit `--cost` and the price table decides. Pass it when you know the real
figure — a discounted rate, a batch job billed by your employer, a provider
that is not in the table:

```bash
tokbudget log --provider deepseek --model deepseek-chat --in 3200 --out 900 --cost 0.0021
```

```
Logged 3,200 in / 900 out for deepseek/deepseek-chat — $0.0021
```

An unknown model is not an error. The entry is stored with a NULL cost and a
note explaining itself, and the report shows `n/a` for it rather than inventing
a number:

```bash
tokbudget log --provider openai --model gpt-6-max --in 500 --out 120
```

```
Logged 500 in / 120 out for openai/gpt-6-max — n/a
No price for this model: stored cost as n/a. Run `tokbudget providers` to see what is priced.
```

### Report

```bash
tokbudget report            # last 7 days
tokbudget report --days 30  # last 30 days
```

The window counts whole local days backwards from today, so `--days 1` means
"since midnight", not "since this minute". Cost columns skip entries that have
no price, and the footer tells you how many were skipped.

### Prices

```bash
tokbudget providers
```

```
Prices in USD per 1,000,000 tokens

PROVIDER   MODEL              INPUT   OUTPUT
anthropic  claude-3-5-haiku    $0.80   $4.00
anthropic  claude-3-7-sonnet   $3.00  $15.00
anthropic  claude-opus-4      $15.00  $75.00
anthropic  claude-sonnet-4     $3.00  $15.00
deepseek   deepseek-chat       $0.27   $1.10
...
```

The table is a snapshot of published 2025 list prices for a handful of
representative models. Treat estimates as estimates — for billing-grade numbers
pass `--cost`.

### From a script

Pipe usage through the CLI, or import the package:

```python
from tokbudget.ledger import Ledger
from tokbudget.pricing import estimate

prompt_tokens, completion_tokens = response.usage.input_tokens, response.usage.output_tokens
cost = estimate("openai", "gpt-4o", prompt_tokens, completion_tokens)
with Ledger() as ledger:
    ledger.add("openai", "gpt-4o", prompt_tokens, completion_tokens, cost)
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

54 tests cover the ledger (insert, query, windowing, aggregation), the cost
math including the unknown-model path, the report renderer, and every CLI
command.

## Roadmap

- `tokbudget import` readers for provider usage APIs, so logging is not manual.
- A user-editable price file (`~/.tokbudget/pricing.json`) that overrides or
  extends the built-in table, plus `--cost` for one-offs.
- Monthly rollups and a `--group-by provider` option on `report`.
- CSV/JSON export of the raw ledger.
- Currency other than USD.

## License

MIT, see [LICENSE](LICENSE).
