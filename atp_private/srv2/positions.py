"""atp_private.srv2.positions - the 15M SRv2 bot's positions for ATP's list (SRV2 P4, read-only).

The bot's positions live in Trade's own store (`live_trades` + `order_log` in `<SRV2_DATA_DIR>/historical_data.db`, the copied PAPER
engine, P1b). This module only READS them, through Trade's own helpers (copied AS IS):
- `database.get_trade_legs_with_prices`: every leg's strike / type / side / qty and its entry and exit fill (order_log);
- `database.position_direction`: the direction from the stored strategy (BULL_PUT_SPREAD / NAKED_CALL = BULLISH, ...).
Only the bot's own rows (`source = srv2_momentum_reversal`). The rows are read with SQLite `mode=ro` and the legs with Trade's SELECT-only helper: no writes, ever. A
missing or unreadable store returns []. Times are as the store writes them (IST, naive). `pnl` is the stored realized P&L; an OPEN
position has none yet (its live MTM needs the broker and stays on ATP's own positions view).
"""
from __future__ import annotations

import os
import sqlite3

SOURCE = "srv2_momentum_reversal"
_COLS = ("trade_id", "symbol", "strategy", "status", "entry_time", "exit_time", "realized_pnl", "exit_reason", "mode")


def _db_path():
    from atp_private.trade_engine.config import DB_PATH
    return DB_PATH


def read(limit=50, path=None):
    """The bot's positions, newest first: [{id, symbol, direction, status, opened_at, closed_at, legs, pnl, exit_reason, mode}]."""
    p = path or _db_path()
    if not os.path.isfile(p):
        return []
    try:
        n = max(1, min(int(limit), 500))
        conn = sqlite3.connect(f"file:{os.path.abspath(p)}?mode=ro", uri=True)
        try:
            rows = conn.execute(f"SELECT {', '.join(_COLS)} FROM live_trades WHERE source=? ORDER BY entry_time DESC LIMIT ?",
                                (SOURCE, n)).fetchall()
        finally:
            conn.close()
        if not rows:
            return []
        from atp_private.trade_engine import database as DB
        legs = _legs(DB, p, [r[0] for r in rows])
        out = []
        for tid, sym, strategy, status, opened, closed, pnl, why, mode in rows:
            out.append({"id": tid, "symbol": sym, "direction": DB.position_direction(strategy), "strategy": strategy,
                        "status": "OPEN" if str(status).upper() == "OPEN" else "CLOSED", "opened_at": opened, "closed_at": closed,
                        "legs": [{"strike": x.get("strike"), "option_type": x.get("option_type"), "side": x.get("transaction_type"),
                                  "qty": x.get("qty"), "entry_price": x.get("entry_price"), "exit_price": x.get("exit_price")}
                                 for x in legs.get(tid, [])],
                        "pnl": pnl, "exit_reason": why, "mode": "LIVE" if str(mode or "").upper() == "LIVE" else "PAPER"})
        return out
    except Exception:                                                    # noqa: BLE001 - display only, never blocks
        return []


def _legs(DB, path, ids):
    """Trade's get_trade_legs_with_prices (SELECTs only). Its store is Trade's DB_PATH; another `path` (tests) is pointed at for this one
    call only."""
    if os.path.abspath(path) == os.path.abspath(DB.DB_PATH):
        return DB.get_trade_legs_with_prices(ids)
    old = DB.DB_PATH
    DB.DB_PATH = path
    try:
        return DB.get_trade_legs_with_prices(ids)
    finally:
        DB.DB_PATH = old
