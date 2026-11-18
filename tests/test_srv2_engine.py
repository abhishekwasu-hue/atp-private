"""SRV2 P1b (owner 18 Nov, OPEN_QUESTIONS SRV2-Q1 default A): the 15M SRv2 bot end to end inside atp-private - an engine entry row ->
Trade's engine-entry glue -> Trade's own PAPER engine (open_multi_leg_trade: legs filled at their LTP, a live_trades row) -> Trade's
own exits (manage_open_trades, srv2 branch: settings re-read at exit time). ATP gives only the IO (fake adapters here); every rule is
the copied Trade code. Synthetic prices; the clock of the exit check is fixed (10:30 IST) so the EOD rules never interfere.
"""
import datetime as _dt
import json
import sqlite3
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from atp_private.srv2 import host
from atp_private.srv2 import settings as S

BOT = SRC = "srv2_momentum_reversal"
SPOT_KEY = "NSE_INDEX|Nifty 50"
BAR = "2026-11-12 10:00:00"
NOW = pd.Timestamp("2026-11-12 10:05")


def chain(spot):
    rows = []
    for k in range(23500, 24551, 50):
        def leg(kind, k=k):
            itm = (spot - k) if kind == "CE" else (k - spot)
            return {"instrument_key": f"NSE_FO|{kind}{k}", "market_data": {"ltp": round(max(itm, 0) + 40.0 + abs(k - spot) * 0.02, 2)},
                    "option_greeks": {"pop": 0.5}}
        rows.append({"strike_price": k, "underlying_spot_price": spot, "call_options": leg("CE"), "put_options": leg("PE")})
    return rows


def prices_of(rows):
    out = {}
    for r in rows:
        for side in ("call_options", "put_options"):
            out[r[side]["instrument_key"]] = r[side]["market_data"]["ltp"]
    out[SPOT_KEY] = rows[0]["underlying_spot_price"]
    return out


class _FrozenDT(_dt.datetime):
    at = _dt.datetime(2026, 11, 12, 5, 0)                                  # 10:30 IST in UTC  # noqa: DTZ001 - naive UTC, as Trade reads utcnow()

    @classmethod
    def utcnow(cls):
        return cls.at

    @classmethod
    def now(cls, tz=None):
        return cls.at + _dt.timedelta(hours=5, minutes=30) if tz is None else cls.at.replace(tzinfo=_dt.UTC).astimezone(tz)


@pytest.fixture()
def bot(tmp_path, monkeypatch):
    data = tmp_path / "srv2"
    data.mkdir()
    monkeypatch.setenv("PAPER_DATA_DIR", str(data / "paper"))
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(data / "engine_signals.db"))
    host.reset()
    host.install()
    from atp_private.trade_engine import config as C
    db = str(data / "historical_data.db")
    monkeypatch.setattr(C, "DB_PATH", db)                                  # before the first import of database (it opens DB_PATH)
    monkeypatch.setattr(C, "DATA_DIR", str(data))
    from atp_private.trade_engine import database as DB
    from atp_private.trade_engine import monitor_timing as MT
    from atp_private.trade_engine import trading_engine as TE
    for mod in (C, DB, TE):
        monkeypatch.setattr(mod, "DB_PATH", db, raising=False)
    for mod in (C, DB, MT):
        monkeypatch.setattr(mod, "DATA_DIR", str(data), raising=False)
    monkeypatch.setattr(MT, "_PATH", str(data / "monitor_timing.json"))
    DB.init_sqlite_db()
    st = NS(stored={}, rows=chain(24010.0), sent=[], db=db)
    st.px = prices_of(st.rows)
    host.register(
        settings=lambda strategy, symbol: st.stored.get((strategy, symbol)),
        token=lambda: "tok",
        option_chain=lambda tok, sym, idx: (st.rows, ""),
        option_expiries=lambda tok, sym: ["2026-11-18", "2026-11-25"],
        ltp=lambda tok, keys: ({k: st.px[k] for k in keys if k in st.px}, None),
        send=lambda msg, silent, kind: (st.sent.append(msg) or True),
        funds=lambda tok: {"available_margin": 1_000_000.0, "used_margin": 0.0},   # Trade's kill switch needs the capital (PAPER too)
    )
    yield st
    host.reset()
    host.uninstall()


def gate_enter(*a, **k):
    return NS(action="ENTER", lots=99, naked_lots=99, note="ok", signal_id="sig", final=True)


def store_entry(model="E2", direction=1, visit="v1"):
    from atp_private.trade_engine import engine_signal as ES
    ES.save({"symbol": "NIFTY", "bar_ts": BAR, "computed_at": BAR, "decision": "setup", "gate": "pass", "direction": direction,
             "level_lo": 23950.0, "level_hi": 23990.0, "entry": None, "invalidation": None, "target": None, "grade": None, "reason": None,
             "payload": json.dumps({"entries": [{"model": model, "direction": direction, "visit_id": visit, "trigger_ts": BAR,
                                                 "area": {"lo": 23950.0, "hi": 23990.0, "tf": "15M", "role": "buyer"}}]})})


def enter(st):
    from atp_private.trade_engine import cloud_db
    from atp_private.trade_engine.paper import engine_entry as EE
    s = cloud_db.get_strategy_settings(S.STRATEGY_KEY, "NIFTY")
    return EE.process(BOT, "tok", "NIFTY", s, 65, SRC, now=NOW, gate_fn=gate_enter)


def trades(st, status=None):
    with sqlite3.connect(st.db) as c:
        c.row_factory = sqlite3.Row
        q = "SELECT * FROM live_trades" + (" WHERE status=?" if status else "")
        return [dict(r) for r in c.execute(q, (status,) if status else ())]


def check_exits(st, monkeypatch):
    from atp_private.trade_engine import trading_engine as TE
    monkeypatch.setattr(TE.datetime, "datetime", _FrozenDT)
    return TE.manage_open_trades("tok", "NIFTY", "D", broker_positions=None)


def test_an_approved_entry_opens_paper_positions_in_trades_own_store(bot):
    store_entry()
    msg = enter(bot)
    open_ = trades(bot, "OPEN")
    assert len(open_) == 2, msg                                            # credit spread + naked (the default settings)
    assert {t["strategy"] for t in open_} == {"BULL_PUT_SPREAD", "NAKED_CALL"}
    assert all(t["source"] == SRC and t["mode"] == "PAPER" and t["entry_timeframe"] == "ENGINE" for t in open_)
    assert {t["entry_reason_tag"] for t in open_} == {"ENGINE_E2"}
    assert all(t["trade_id"].startswith("PAPER") for t in open_)


def test_the_spread_closes_at_its_premium_target_with_trades_own_exit_rule(bot, monkeypatch):
    bot.stored[(S.STRATEGY_KEY, "NIFTY")] = {"naked_enabled": False}
    store_entry()
    enter(bot)
    (spread,) = trades(bot, "OPEN")
    legs = spread.get("legs_json")
    for k in list(bot.px):                                                 # every option nearly worthless => the spread's credit is kept
        if k != SPOT_KEY:
            bot.px[k] = 0.05
    check_exits(bot, monkeypatch)
    closed = trades(bot, "CLOSED")
    assert len(closed) == 1 and closed[0]["exit_reason"] == "PREMIUM_TARGET", (closed, legs)


def test_the_spread_stops_out_on_the_spot_and_premium_rule(bot, monkeypatch):
    bot.stored[(S.STRATEGY_KEY, "NIFTY")] = {"naked_enabled": False}
    store_entry()
    enter(bot)
    down = chain(23700.0)                                                  # spot falls through the bull put spread
    bot.px = prices_of(down)
    check_exits(bot, monkeypatch)
    closed = trades(bot, "CLOSED")
    assert len(closed) == 1 and closed[0]["exit_reason"] == "SL", closed


def test_no_exit_while_nothing_has_moved(bot, monkeypatch):
    store_entry()
    enter(bot)
    check_exits(bot, monkeypatch)
    assert len(trades(bot, "OPEN")) == 2 and not trades(bot, "CLOSED")


def test_a_live_order_is_refused_by_the_atp_adapter():
    from atp_private.srv2.io import upstox_api as U
    code, resp = U.execute_order_leg_set("tok", [{"instrument_token": "X"}], "LIVE")
    assert code is None and resp["status"] == "error"
