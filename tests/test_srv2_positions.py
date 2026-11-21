# ruff: noqa: F811 - the P1b `bot` fixture is imported and used as a pytest fixture
"""SRV2 P4: the bot's positions for ATP's list, read-only from Trade's own store (`atp_private.srv2.positions.read`).

Positions are opened and closed by the copied Trade PAPER engine (the P1b fixture of tests/test_srv2_engine.py); the module only reads."""
import hashlib
import os
import sqlite3

from atp_private.srv2 import positions as P
from tests.test_srv2_engine import (  # noqa: F401 - the fixture
    S,
    bot,
    chain,
    check_exits,
    enter,
    prices_of,
    store_entry,
    trades,
)


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_open_positions_are_listed_with_their_legs_and_fills(bot):
    store_entry()
    enter(bot)
    rows = P.read(path=bot.db)
    assert len(rows) == 2 and {r["status"] for r in rows} == {"OPEN"} and {r["mode"] for r in rows} == {"PAPER"}
    assert {r["strategy"]: r["direction"] for r in rows} == {"BULL_PUT_SPREAD": "BULLISH", "NAKED_CALL": "BULLISH"}
    spread = next(r for r in rows if r["strategy"] == "BULL_PUT_SPREAD")
    stored = next(t for t in trades(bot, "OPEN") if t["strategy"] == "BULL_PUT_SPREAD")
    assert spread["id"] == stored["trade_id"] and spread["opened_at"] == stored["entry_time"] and spread["closed_at"] is None
    assert {(x["side"], x["option_type"]) for x in spread["legs"]} == {("SELL", "PE"), ("BUY", "PE")}
    assert all(x["entry_price"] is not None and x["exit_price"] is None and x["qty"] == 65 for x in spread["legs"])
    assert spread["pnl"] is None


def test_a_closed_position_shows_its_exit_reason_exit_fills_and_pnl(bot, monkeypatch):
    bot.stored[(S.STRATEGY_KEY, "NIFTY")] = {"naked_enabled": False}
    store_entry()
    enter(bot)
    bot.px = prices_of(chain(23700.0))                                     # Trade's own SL rule closes it
    check_exits(bot, monkeypatch)
    (row,) = P.read(path=bot.db)
    (stored,) = trades(bot, "CLOSED")
    assert row["status"] == "CLOSED" and row["exit_reason"] == "SL" == stored["exit_reason"]
    assert row["pnl"] == stored["realized_pnl"] and row["closed_at"] == stored["exit_time"]
    assert all(x["exit_price"] is not None for x in row["legs"])


def test_reading_never_writes_and_only_the_bots_rows_count(bot):
    store_entry()
    enter(bot)
    with sqlite3.connect(bot.db) as c:                                     # another bot's row in the same store
        c.execute("INSERT INTO live_trades (trade_id, symbol, strategy, status, entry_time, source, mode) VALUES "
                  "('X1','NIFTY','IRON_CONDOR','OPEN','2026-11-12 10:00:00','other_bot','PAPER')")
    before = _sha(bot.db)
    rows = P.read(path=bot.db)
    assert len(rows) == 2 and "X1" not in {r["id"] for r in rows} and _sha(bot.db) == before
    assert len(P.read(limit=1, path=bot.db)) == 1


def test_a_missing_or_unreadable_store_returns_nothing(tmp_path):
    missing = str(tmp_path / "none.db")
    assert P.read(path=missing) == [] and not os.path.exists(missing)      # never created
    bad = tmp_path / "bad.db"
    bad.write_text("not a database")
    assert P.read(path=str(bad)) == []
