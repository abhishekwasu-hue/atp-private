#!/usr/bin/env python3
"""Trade side of the shadow run (owner order M79 W10): one day's rows of Trade's `engine_signals` table as JSON lines.

Read-only (the database is opened `mode=ro`), standard library only, so it runs on the Trade host as it is:

    python3 trade_export.py --db <Trade data/engine_signals.db> --day YYYY-MM-DD > trade-YYYY-MM-DD.jsonl

Columns written: symbol, bar_ts, computed_at, decision, payload (the payload text as stored). Nothing is changed.
"""
import argparse
import json
import sqlite3
import sys


def rows(db, day):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
    try:
        cur = con.execute("SELECT symbol, bar_ts, computed_at, decision, payload FROM engine_signals "
                          "WHERE substr(bar_ts, 1, 10) = ? ORDER BY symbol, bar_ts", (day,))
        for symbol, bar_ts, computed_at, decision, payload in cur:
            yield {"symbol": symbol, "bar_ts": bar_ts, "computed_at": computed_at, "decision": decision, "payload": payload}
    finally:
        con.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", required=True)
    p.add_argument("--day", required=True)
    a = p.parse_args(argv)
    n = 0
    for r in rows(a.db, a.day):
        sys.stdout.write(json.dumps(r) + "\n")
        n += 1
    print(f"{n} row(s) of {a.day}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
