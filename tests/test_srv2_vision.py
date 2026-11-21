"""SRV2 P3 (owner 20-21 Nov, AGENT-MODES, ATP ADR-0029): the 15M SRv2 bot with Trade's Vision / Telegram ✅ (copied AS IS) and the two
agent modes.

The real copied path runs here: `paper.engine_entry.process` -> Trade's `vision.gate.entry_gate` (temporary vision.db) -> the
worker's decision step (`worker.v1_status` + `store.finish`, exactly as `worker.process_row` ends; the chart render and the Anthropic
call are the only parts left out) -> Trade's `telegram_bot.handle_callback` with a signed ✅ button -> the bot's next cycle. Only the
broker / Telegram network edges are fakes. Synthetic data; the callback secret and ids below are test values, not real ones.
"""
import json
import os
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from atp_private.srv2 import host
from atp_private.srv2 import modes as M
from atp_private.srv2 import settings as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "atp_private", "trade_engine")
BOT, SRC = "srv2_momentum_reversal", "srv2_momentum_reversal"
NOW = pd.Timestamp("2026-11-12 10:05")                                     # IST naive
BAR = "2026-11-12 10:00:00"
OWNER = "424242"                                                           # test Telegram id (approver + chat)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    yield from _env(tmp_path, monkeypatch)


def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_DATA_DIR", str(tmp_path / "paper"))
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "engine" / "engine_signals.db"))
    monkeypatch.setenv("VISION_DB_PATH", str(tmp_path / "vision" / "vision.db"))
    monkeypatch.setenv("PAPER_CONFIG", os.path.join(ENGINE, "config.yaml"))
    monkeypatch.setenv("VISION_CALLBACK_SECRET", "test-only-secret")
    monkeypatch.setenv("TELEGRAM_APPROVER_IDS", OWNER)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", OWNER)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-only-token")
    host.reset()
    host.install()
    from atp_private.trade_engine.vision import store as VS
    from atp_private.trade_engine.vision import tg as TG
    tg_calls = []
    monkeypatch.setattr(TG, "_call", lambda method, *a, **k: (tg_calls.append(method) or None))   # the Telegram network edge
    import atp_private.trade_engine.notifications as N
    monkeypatch.setattr(N, "send_telegram_message", lambda *a, **k: (tg_calls.append("sendMessage") or True))
    monkeypatch.setattr(N, "send_telegram_photo", lambda *a, **k: (tg_calls.append("sendPhoto") or True))
    clock = NS(now=NOW)
    monkeypatch.setattr(VS, "now_ist", lambda: clock.now)
    from atp_private.trade_engine.paper import engine_entry as EE
    entered = []
    monkeypatch.setattr(EE, "enter_now", lambda bot, sym, send=None: entered.append((bot, sym)))   # ✅ ⇒ "enter now" (checked below)
    state = NS(stored={}, opened=[], sent=[], open_now=False, live_ok=False, clock=clock, entered=entered,
               vpath=str(tmp_path / "vision" / "vision.db"))
    host.register(
        settings=lambda strategy, symbol: state.stored.get(symbol) if strategy == S.STRATEGY_KEY else None,
        token=lambda: "tok",
        option_chain=lambda tok, sym, idx: (chain(), ""),
        option_expiries=lambda tok, sym: ["2026-11-18", "2026-11-25"],
        send=lambda msg, **kw: (state.sent.append(msg) or True),
        live_confirmed=lambda *a: state.live_ok,
    )
    yield state
    host.reset()
    host.uninstall()


def chain(spot=24010.0):
    rows = []
    for k in range(23500, 24551, 50):
        def leg(kind, k=k):
            itm = (spot - k) if kind == "CE" else (k - spot)
            ltp = max(itm, 0) + 40.0 + abs(k - spot) * 0.02
            return {"instrument_key": f"NSE_FO|{kind}{k}", "market_data": {"ltp": round(ltp, 2)}, "option_greeks": {"pop": 0.5}}
        rows.append({"strike_price": k, "underlying_spot_price": spot, "call_options": leg("CE"), "put_options": leg("PE")})
    return rows


def store_row(entries, bar=BAR, symbol="NIFTY"):
    from atp_private.trade_engine import engine_signal as ES
    ES.save({"symbol": symbol, "bar_ts": bar, "computed_at": bar, "decision": "setup", "gate": "pass", "direction": 1,
             "level_lo": 23950.0, "level_hi": 23990.0, "entry": None, "invalidation": None, "target": None, "grade": None,
             "reason": None, "payload": json.dumps({"entries": entries})})


def entry(model="E2", direction=1, visit="v1"):
    return {"model": model, "direction": direction, "visit_id": visit, "trigger_ts": BAR,
            "area": {"lo": 23950.0, "hi": 23990.0, "tf": "15M", "role": "buyer"}}


def cycle(state, now=None):
    """One bot cycle with Trade's REAL Vision gate (gate_fn None) and a recording PAPER open."""
    from atp_private.trade_engine import cloud_db
    from atp_private.trade_engine.paper import engine_entry as EE
    st = cloud_db.get_strategy_settings(S.STRATEGY_KEY, "NIFTY")
    return EE.process(BOT, "tok", "NIFTY", st, 65, SRC, now=now or state.clock.now, gate_fn=None, vpath=state.vpath,
                      has_open=lambda sym, src: state.open_now,
                      open_fn=lambda tok, sym, sr, **kw: (state.opened.append({"symbol": sym, "legs": sr, **kw}) or (True, "opened")))


def worker_decides(state, verdict="agree"):
    """The end of Trade's worker.process_row for each QUEUED row: claim, Trade's `v1_status`, `store.finish` (no chart / API call)."""
    from atp_private.trade_engine.vision import config as VC
    from atp_private.trade_engine.vision import store as VS
    from atp_private.trade_engine.vision import worker as W
    out = []
    for row in VS.claim_queued(path=state.vpath):
        s = VC.load(row["bot"], state.vpath)
        st, extra, _d = W.v1_status(row, verdict, s, {})
        VS.finish(row["signal_id"], st, state.vpath, only_from="RUNNING", verdict=verdict, final_decision=extra.pop("final", None), **extra)
        out.append(VS.get_signal(row["signal_id"], state.vpath))
    return out


def tap(state, row, action="A", who=OWNER):
    """The owner's button on the card, through Trade's own callback handler (signed button data, approver check, deadline)."""
    from atp_private.trade_engine.vision import decide as VD
    from atp_private.trade_engine.vision import telegram_bot as TB
    answers = []
    cq = {"id": "cq1", "from": {"id": int(who)}, "data": VD.callback_data(row["signal_id"], action),
          "message": {"message_id": 7, "chat": {"id": int(OWNER)}}}
    return TB.handle_callback(cq, state.vpath, now=state.clock.now, answer=lambda i, t: answers.append(t),
                              edit=lambda *a, **k: None, send_reply=lambda *a, **k: None, send=lambda *a, **k: None,
                              send_buttons=lambda *a, **k: None)


def signal(state):
    from atp_private.trade_engine.vision import store as VS
    with VS.connect(state.vpath) as c:
        return [dict(r) for r in c.execute("SELECT * FROM vision_signals ORDER BY created_at")]


def legs_of(opened):
    return [(o["legs"], o["lots"], o["trading_mode"], o["entry_reason_tag"], o["entry_level_price"]) for o in opened]


# --- modes ------------------------------------------------------------------------------------------------------------------------------
def test_a_new_deployment_starts_in_human_confirm(env):
    rec = M.ensure_default("abhi", path=env.vpath)
    assert rec["to"] == M.HUMAN_CONFIRM and M.DEFAULT == M.HUMAN_CONFIRM
    assert M.current(env.vpath) == (M.HUMAN_CONFIRM, True)
    from atp_private.trade_engine.vision import config as VC
    s = VC.load(BOT, env.vpath)
    assert s["vision_mode"] == "human_confirm" and s["approval_required"] is True
    assert M.ensure_default("abhi", path=env.vpath) is None                 # a stored mode is never overwritten by "create"


def test_a_mode_switch_is_audited_by_who_and_from_to(env):
    M.ensure_default("abhi", path=env.vpath)
    rec = M.apply(M.AUTO, "abhi", owner_deployment=True, vision_on=True, path=env.vpath, now="2026-11-12T04:35:00+00:00")
    assert rec == {"bot": BOT, "by": "abhi", "at": "2026-11-12T04:35:00+00:00", "from": M.HUMAN_CONFIRM, "from_vision_on": True,
                   "to": M.AUTO, "vision_on": True,
                   "settings": {"vision_mode": "auto_veto", "approval_required": False, "vision_fail_action": "skip"}}
    from atp_private.trade_engine.vision import config as VC
    h = VC.history(BOT, env.vpath)                                          # Trade's own change history keeps both switches
    assert [x["by"] for x in h] == ["atp:abhi", "atp:abhi"]
    assert json.loads(h[-1]["new_json"])["vision_mode"] == "auto_veto" and json.loads(h[-1]["old_json"])["vision_mode"] == "human_confirm"
    back = M.apply(M.HUMAN_CONFIRM, "abhi", owner_deployment=True, path=env.vpath)
    assert back["from"] == M.AUTO and back["settings"]["vision_fail_action"] == "ignore" and len(VC.history(BOT, env.vpath)) == 3


def test_auto_is_refused_outside_the_owners_deployment_and_without_an_actor(env):
    with pytest.raises(M.ModeRefused):
        M.apply(M.AUTO, "someone", owner_deployment=False, path=env.vpath)
    with pytest.raises(M.ModeRefused):
        M.apply(M.AUTO, "", owner_deployment=True, path=env.vpath)
    with pytest.raises(M.ModeRefused):
        M.apply("yolo", "abhi", owner_deployment=True, path=env.vpath)
    assert M.current(env.vpath) == (M.HUMAN_CONFIRM, True)                   # nothing was written
    assert M.apply(M.HUMAN_CONFIRM, "someone", owner_deployment=False, path=env.vpath)["to"] == M.HUMAN_CONFIRM


def test_a_hand_edited_or_unknown_row_reads_as_human_confirm(env):
    from atp_private.trade_engine.vision import store as VS
    with VS.connect(env.vpath) as c:
        c.execute("INSERT INTO vision_settings (bot, json, updated_at, updated_by) VALUES (?,?,?,?)",
                  (BOT, json.dumps({"vision_mode": "notify", "approval_required": False}), "x", "hand"))
    assert M.current(env.vpath) == (M.HUMAN_CONFIRM, True)


# --- human_confirm ----------------------------------------------------------------------------------------------------------------------
def test_human_confirm_holds_until_the_owners_tick_then_enters(env):
    M.ensure_default("abhi", path=env.vpath)
    env.stored["NIFTY"] = {"lots": 2, "naked_lots": 1}
    store_row([entry("E2")])
    assert "waiting for Vision" in cycle(env) and not env.opened            # QUEUED: the card is not even out yet
    [row] = worker_decides(env)
    assert row["status"] == "PENDING_HUMAN" and row["deadline"]
    assert "waiting for Vision" in cycle(env) and not env.opened            # the card is out, no ✅ yet ⇒ nothing
    ok, _ = tap(env, row, "A")
    assert ok and env.entered == [(BOT, "NIFTY")]                           # Trade: ✅ runs the bot's cycle at once
    from atp_private.trade_engine.vision import store as VS
    assert VS.get_signal(row["signal_id"], env.vpath)["decided_by"] == f"telegram:{OWNER}"
    cycle(env)
    assert len(env.opened) == 2 and {o["trading_mode"] for o in env.opened} == {"PAPER"}
    assert [o["lots"] for o in env.opened] == [2, 1]                        # the dashboard lots, never a Vision size
    assert VS.get_signal(row["signal_id"], env.vpath)["status"] == "EXECUTED"


def test_an_expired_card_places_nothing(env):
    M.ensure_default("abhi", path=env.vpath)
    store_row([entry("E2")])
    cycle(env)
    [row] = worker_decides(env)
    env.clock.now = pd.Timestamp(row["deadline"]) + pd.Timedelta(seconds=1)  # no ✅ before the deadline
    ok, why = tap(env, row, "A")                                            # a late tap is refused by Trade's handler
    assert not ok and why == "expired" and not env.entered
    msg = cycle(env, now=env.clock.now)
    assert not env.opened, msg
    from atp_private.trade_engine.vision import store as VS
    assert VS.get_signal(row["signal_id"], env.vpath)["status"] in ("REJECTED", "SHADOWED", "EXPIRED")
    cycle(env, now=env.clock.now + pd.Timedelta(minutes=1))
    assert not env.opened                                                   # and never later either


def test_a_tick_from_someone_else_or_a_rejection_places_nothing(env):
    M.ensure_default("abhi", path=env.vpath)
    store_row([entry("E1", visit="a")])
    cycle(env)
    [row] = worker_decides(env)
    assert tap(env, row, "A", who="999") == (False, "unauthorized")
    assert tap(env, row, "R")[0]
    cycle(env)
    assert not env.opened and not env.entered


def test_a_vision_approval_without_the_owners_tick_never_enters_in_human_confirm(env):
    M.ensure_default("abhi", path=env.vpath)
    store_row([entry("E2")])
    cycle(env)
    from atp_private.trade_engine.vision import store as VS
    [row] = VS.claim_queued(path=env.vpath)
    VS.finish(row["signal_id"], "APPROVED", env.vpath, only_from="RUNNING", decided_by="vision", decided_at=VS._iso(env.clock.now))
    cycle(env)
    assert not env.opened                                                   # Trade: approval_required ⇒ only telegram:<id> counts


# --- auto -------------------------------------------------------------------------------------------------------------------------------
def test_auto_without_vision_enters_on_the_bots_own_rules(env):
    M.apply(M.AUTO, "abhi", owner_deployment=True, vision_on=False, path=env.vpath)
    env.stored["NIFTY"] = {"lots": 2, "naked_lots": 1}
    store_row([entry("E2")])
    cycle(env)
    assert len(env.opened) == 2 and not signal(env)                         # no card, no ✅ asked


def test_auto_with_vision_enters_when_vision_agrees_and_skips_when_it_disagrees_or_is_unavailable(env):
    M.apply(M.AUTO, "abhi", owner_deployment=True, vision_on=True, path=env.vpath)
    store_row([entry("E1", visit="a")])
    assert "waiting for Vision" in cycle(env) and not env.opened
    [row] = worker_decides(env, "disagree")
    assert row["status"] == "REJECTED"
    cycle(env)
    assert not env.opened
    store_row([entry("E2", visit="b")])
    cycle(env)
    [row] = worker_decides(env, "unavailable")
    assert row["status"] == "REJECTED"                                      # SRV2-Q5 default: no Vision answer = no agreement
    cycle(env)
    assert not env.opened
    store_row([entry("E3", visit="c")])
    cycle(env)
    [row] = worker_decides(env, "agree")
    assert row["status"] == "APPROVED" and row["decided_by"] == "vision"
    cycle(env)
    assert len(env.opened) == 2 and not env.entered


@pytest.mark.parametrize("vision_on", [False, True])
def test_auto_places_exactly_what_human_confirm_would_have_proposed_for_the_same_bars(tmp_path, monkeypatch, vision_on):
    """Parity: the same engine bars and the same dashboard settings in both modes ⇒ the same positions (legs, strikes, lots, mode,
    model tag, level). human_confirm reaches them after the owner's ✅; auto reaches them by itself."""
    results = {}
    for mode in (M.HUMAN_CONFIRM, M.AUTO):
        sub = tmp_path / mode
        with monkeypatch.context() as mp:
            gen = _env(sub, mp)
            state = next(gen)
            state.stored["NIFTY"] = {"lots": 3, "naked_lots": 2}
            if mode == M.AUTO:
                M.apply(M.AUTO, "abhi", owner_deployment=True, vision_on=vision_on, path=state.vpath)
            else:
                M.ensure_default("abhi", path=state.vpath)
            store_row([entry("E2", visit="p")])
            cycle(state)
            rows = worker_decides(state) if (mode == M.HUMAN_CONFIRM or vision_on) else []
            if mode == M.HUMAN_CONFIRM:
                assert not state.opened and rows[0]["status"] == "PENDING_HUMAN"
                assert tap(state, rows[0], "A")[0]
            cycle(state)
            results[mode] = legs_of(state.opened)
            next(gen, None)
    assert results[M.AUTO] and results[M.AUTO] == results[M.HUMAN_CONFIRM]


# --- in both modes ----------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode", [M.HUMAN_CONFIRM, M.AUTO])
def test_live_is_refused_unless_the_owners_switch_is_on(env, mode):
    if mode == M.AUTO:
        M.apply(M.AUTO, "abhi", owner_deployment=True, vision_on=False, path=env.vpath)
    else:
        M.ensure_default("abhi", path=env.vpath)
    env.stored["NIFTY"] = {"trading_mode": "LIVE"}
    from atp_private.trade_engine import cloud_db
    assert cloud_db.get_strategy_settings(S.STRATEGY_KEY, "NIFTY")["trading_mode"] == "PAPER"   # switch off ⇒ reads as PAPER
    env.live_ok = True
    store_row([entry("E1")])
    msg = cycle(env)
    assert "PAPER only" in msg and not env.opened                           # switch on ⇒ still no engine LIVE order from here
    from atp_private.trade_engine import upstox_api
    code, resp = upstox_api.execute_order_leg_set("tok", [{"instrument_token": "NSE_FO|PE23950"}], "LIVE")
    assert code is None and resp["status"] == "error"                       # and the order edge refuses LIVE in both modes


def test_the_vision_and_telegram_services_run_trades_loops_in_their_own_threads(env, monkeypatch, tmp_path):
    import threading

    from atp_private.srv2 import runner as R
    from atp_private.trade_engine import process_lock as PL
    monkeypatch.setattr(PL, "DATA_DIR", str(tmp_path / "locks"))            # Trade's lock files, kept out of the repo
    monkeypatch.setattr(R, "_private", lambda: None)                        # the engine's DB init is P1's (tested there)
    from atp_private.trade_engine.vision import telegram_bot as TB
    from atp_private.trade_engine.vision import worker as W
    seen = []
    monkeypatch.setattr(W, "run_once", lambda *a, **k: (seen.append("vision") or []))
    monkeypatch.setattr(TB, "poll_once", lambda offset, path=None, timeout=50: (seen.append(("tg", timeout)) or offset))
    stop = threading.Event()
    R.vision_service(stop, once=True)
    assert R.telegram_service(stop, once=True, poll_timeout=1) == 0
    assert seen == ["vision", ("tg", 1)]
    started = R.start_services()
    try:
        assert started == ["vision", "telegram"] and R.start_services() == []   # idempotent: never two loops
        assert {t.name for t in threading.enumerate()} >= {"srv2-vision", "srv2-telegram"}
    finally:
        R.stop_services()
    assert not any(t.name.startswith("srv2-") for t in threading.enumerate())
    monkeypatch.delenv("VISION_CALLBACK_SECRET")
    assert R.telegram_service(stop, once=True) == 1                         # Trade: no secret ⇒ the service does not start


def test_cards_lists_the_bots_cards_newest_first_read_only(env):
    M.ensure_default("abhi", path=env.vpath)
    store_row([entry("E1", visit="a"), entry("E2", visit="b")])
    cycle(env)                                                              # two cards, both QUEUED
    from atp_private.trade_engine.vision import store as VS
    first = sorted(VS.claim_queued(path=env.vpath), key=lambda r: r["created_at"])
    for r in first[1:]:                                                     # only the first one is decided by the worker
        VS.transition(r["signal_id"], "RUNNING", "QUEUED", env.vpath)
    from atp_private.trade_engine.vision import config as VC
    from atp_private.trade_engine.vision import worker as W
    st, extra, _d = W.v1_status(first[0], "agree", VC.load(BOT, env.vpath), {})
    VS.finish(first[0]["signal_id"], st, env.vpath, only_from="RUNNING", final_decision=extra.pop("final", None), **extra)
    out = M.cards(path=env.vpath)
    assert sorted(c["status"] for c in out) == ["PENDING_HUMAN", "QUEUED"] and all(set(c) == set(M.CARD_FIELDS) for c in out)
    assert [c["created_at"] for c in out] == sorted((c["created_at"] for c in out), reverse=True)
    assert len(M.cards(limit=1, path=env.vpath)) == 1
    assert M.cards(path=os.path.join(env.vpath, "not-a-dir", "vision.db")) == []   # unreadable store ⇒ [] (never raises)
