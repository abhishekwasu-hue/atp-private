"""atp_private.srv2.runner - the 15M SRv2 bot's schedule inside ATP's worker (owner order SRV2, 18 Nov).

Trade runs the bot with cron lines (Trade scripts/install_engine_schedule.sh, deploy/README.md):
- the engine resident: each 5M close + the final grace, symbols in parallel, retried until the bar is stored (scripts/engine_resident.py,
  08:30-15:25 IST spawns; the resident's own window / market checks decide);
- the bot: every minute at :30, 09:15-16:29 IST Mon-Fri (srv2_momentum_reversal_strategy.py --symbols NIFTY,BANKNIFTY,SENSEX);
- the exit monitor: every minute 09:15-16:29 IST Mon-Fri, looping inside the minute every 15 s, every 5 s while a trade is open
  (trade_monitor.py, run_monitor_loop).
ATP's worker calls `tick(now)` every few seconds (in a thread: the copied code is synchronous) and this module runs what is due with the
same timing. Every rule is the copied Trade code; this module only decides WHEN, as cron did.

The bot's cycle is the engine part of srv2_momentum_reversal_strategy.process_symbol (Trade L235-245: settings, symbol_enabled,
paper.bot_hooks.pre_cycle -> the engine entry). Its legacy own-level path after that is not ported: with signal_source = engine its
entries are refused by own_signal_ok anyway, and it reads Trade's market_zones (levels of the legacy level bots), which ATP does not keep.

SRV2 P3: Trade runs Vision and the Telegram ✅ as two systemd services (docs/SRV2_PORT_AUDIT.md section 1):
- `vision_worker.service`: `python3 -m vision.worker --loop-seconds 3600 --poll 2` (lock, stale rows expired, orphans re-queued, then
  `run_once` every 2 s: chart, Vision, the card, deadlines / expiry via `v1_housekeeping`);
- `vision_telegram.service`: `python3 -m vision.telegram_bot` (needs VISION_CALLBACK_SECRET and TELEGRAM_APPROVER_IDS; open cards
  EXPIRED on start, then `poll_once` long-poll every 0.5 s: ✅ / ❌ callbacks, commands).
`start_services()` runs the same two loop bodies in two daemon threads of ATP's worker (never inside `tick`, so a slow Vision call or a
Telegram long-poll never delays the exit monitor - ADR-0004).
"""
from __future__ import annotations

import os
import sys
import threading

import pandas as pd

from . import host

BOT = "srv2_momentum_reversal"
SYMBOLS = ("NIFTY", "BANKNIFTY", "SENSEX")                                # Trade's cron --symbols
BOT_WINDOW = ("09:15", "16:29")                                           # cron 45-59 3 + * 4-10 UTC, Mon-Fri
BOT_AT_SECOND = 30                                                        # `sleep 30`
MONITOR_WINDOW = ("09:15", "16:29")
ENGINE_WINDOW = ("08:30", "15:29")                                        # resident spawns */5 3-9 UTC (it exits after its store window)

_state = {"bot_minute": None, "monitor_last": None, "engine": {}}
_install_lock = threading.Lock()
_installed = False


def _private():
    """The copied modules (imported once; Trade's scripts add their folder to sys.path - restored, so ATP's own imports never see it)."""
    global _installed
    with _install_lock:
        if not _installed:
            host.install()
            before = list(sys.path)
            from atp_private.trade_engine import config as C
            from atp_private.trade_engine import database as DB
            from atp_private.trade_engine import engine_service as SVC
            from atp_private.trade_engine.scripts import (
                engine_resident as ER,
            )
            from atp_private.trade_engine.scripts import (
                engine_signal_run as ESR,
            )
            sys.path[:] = before
            SVC.SETTINGS_PATH = os.path.join(C.DATA_DIR, "engine_settings.json")   # Trade: data/engine_settings.json next to the code
            DB.init_sqlite_db()
            _installed = True
    from atp_private.trade_engine import trade_monitor as TM
    from atp_private.trade_engine.scripts import engine_resident as ER
    from atp_private.trade_engine.scripts import engine_signal_run as ESR
    return ER, ESR, TM


def _within(now, window):
    t = now.time()
    return now.weekday() < 5 and pd.Timestamp(window[0]).time() <= t <= pd.Timestamp(window[1]).time().replace(second=59)


# --- the bot (every minute at :30) ---------------------------------------------------------------------------------------------------
def process_symbol(access_token, symbol, lot_size=None):
    """srv2_momentum_reversal_strategy.process_symbol, the engine part (Trade L235-245) verbatim apart from the imports."""
    from atp_private.trade_engine import cloud_db
    settings = cloud_db.get_strategy_settings("15m_dynamic_sr", symbol)
    if not settings.get("symbol_enabled", symbol == "NIFTY"):
        return f"{symbol}: बंद आहे (symbol_enabled=False, Bot Dynamic SR Algo सेटिंग्जमधून सक्रिय करा)"
    from atp_private.trade_engine.paper import bot_hooks as _PBH
    _pre = _PBH.pre_cycle("srv2_momentum_reversal", access_token, symbol, settings, lot_size, source="srv2_momentum_reversal")
    if _pre.stop:
        return _pre.msg
    return _pre.msg


def bot_cycle(symbols=SYMBOLS):
    """srv2_momentum_reversal_strategy `__main__` + run_all_symbols (Trade L734-783): one pass under the bot's ProcessLock."""
    _private()
    from atp_private.trade_engine import cloud_db
    from atp_private.trade_engine.database import init_sqlite_db, run_auto_backup_if_due
    from atp_private.trade_engine.notifications import notify_error, write_heartbeat
    from atp_private.trade_engine.process_lock import ProcessLock, ProcessLockHeld
    out = []
    try:
        with ProcessLock("srv2_momentum_reversal_strategy"):
            init_sqlite_db()
            token = cloud_db.get_effective_upstox_token(None)
            if not token:
                try:
                    from atp_private.trade_engine.paper.bot_hooks import token_error
                    token_error("NIFTY", "15M Dynamic SR")
                except Exception as exc:                                # noqa: BLE001 - Trade: the alert never stops the run
                    print(f"srv2 token alert: {type(exc).__name__}: {exc}")
                return ["no Upstox token"]
            ok = False
            for symbol in symbols:
                try:
                    out.append(process_symbol(token, symbol.strip()))
                    ok = True
                except Exception as e:                                  # noqa: BLE001 - Trade: one symbol never stops the others
                    notify_error("srv2_momentum_reversal", f"{symbol.strip()}: {e}")
                    out.append(f"{symbol.strip()}: error {e}")
            if ok:
                write_heartbeat("srv2_momentum_reversal")
            run_auto_backup_if_due(interval_minutes=60)
    except ProcessLockHeld as e:
        out.append(f"previous run still going ({e})")
    return out


# --- the exit monitor (every 15 s; every 5 s while a trade is open) --------------------------------------------------------------------
def monitor_interval():
    """trade_monitor.run_monitor_loop's cadence: 5 s with a TSL-locked or any open trade, else 15 s (Trade's defaults)."""
    from atp_private.trade_engine import database
    from atp_private.trade_engine.engine_service import MONITORED_SYMBOLS
    try:
        if database.has_active_tsl_trades(MONITORED_SYMBOLS):
            return 5.0
        if database.get_open_trade_modes_by_symbol(MONITORED_SYMBOLS):
            return 5.0
    except Exception as exc:                                            # noqa: BLE001 - Trade: a DB error keeps the usual interval
        print(f"srv2 monitor interval: {type(exc).__name__}: {exc}")
    return 15.0


def exit_cycle():
    """trade_monitor `__main__` one cycle: the token, then run_monitor_cycle (every open trade of the bot, Trade's own exits)."""
    _ER, _ESR, TM = _private()
    from atp_private.trade_engine import cloud_db
    token = cloud_db.get_effective_upstox_token(None)
    if not token:
        return "no Upstox token - exits wait for the login"
    return TM.run_monitor_cycle(token, "D")


# --- the engine (each 5M close) ---------------------------------------------------------------------------------------------------------
def engine_close(close, symbols, calendar=None):
    """One try of engine_resident.one_close for this close: every due symbol (engine_resident.due) in parallel, one thread each, run
    in-process (engine_signal_run.main --engine decision3 --symbols S) instead of Trade's subprocess. The resident's retry loop is the
    next tick (engine_due). Under the engine shim's lock with ATP's market calendar (the engine and is_market_open read it)."""
    ER, ESR, _TM = _private()
    from atp_private.adapters import trade_config
    from atp_private.trade_engine import provider

    def runner(sym):
        try:
            ESR.main(["--engine", "decision3", "--symbols", sym])
        except Exception as exc:                                        # noqa: BLE001 - one symbol never stops the others
            print(f"srv2 engine {sym}: {type(exc).__name__}: {exc}")

    with provider._LOCK, trade_config.use_calendar(calendar):
        settings = {x: ER.settings_of(x) for x in symbols}
        if ER.window_over(close, symbols, settings):
            return []
        todo = [x for x in symbols if ER.due(x, close, None, settings.get(x))]
        th = [threading.Thread(target=runner, args=(x,), daemon=True) for x in todo]
        for t in th:
            t.start()
        for t in th:
            t.join()
        return todo


# --- Vision worker + Telegram ✅ (Trade's two services, P3) ---------------------------------------------------------------------------
VISION_POLL_S = 2                                                         # vision_worker.service --poll 2
TELEGRAM_PAUSE_S = 0.5                                                    # telegram_bot.main: time.sleep(0.5) between polls
_services = {"stop": threading.Event(), "threads": {}}


def vision_service(stop, poll=VISION_POLL_S, once=False):
    """vision.worker.main's loop (Trade L1311-1325) under the same lock, until `stop` is set (Trade: until --loop-seconds)."""
    _private()
    from atp_private.trade_engine.process_lock import ProcessLock, ProcessLockHeld
    from atp_private.trade_engine.vision import store as VS
    from atp_private.trade_engine.vision import worker as W
    try:
        with ProcessLock("vision_worker"):
            VS.expire_stale(W.STALE_MIN)
            for sid in VS.requeue_orphans():
                print(f"♻️ {sid}: RUNNING from a stopped worker ⇒ queued again")
            while not stop.is_set():
                try:
                    for sid, res in W.run_once():
                        print(f"{VS.now_ist():%H:%M:%S} {sid} → {res.get('verdict')} {res.get('error') or ''}")
                except Exception as exc:                                # noqa: BLE001 - systemd restarts Trade's worker; here the loop goes on
                    print(f"srv2 vision worker: {type(exc).__name__}: {exc}")
                if once:
                    break
                stop.wait(poll)
    except ProcessLockHeld:
        print("⏭️ vision worker आधीच चालू आहे")


def telegram_service(stop, once=False, poll_timeout=50):
    """vision.telegram_bot.main (Trade L300-324) under the same lock, until `stop` is set. Returns 1 (not started) without the callback
    secret / approver ids, as Trade: then no card gets buttons and Trade's no-reply rule applies (no entry in human_confirm)."""
    _private()
    from atp_private.trade_engine.process_lock import ProcessLock, ProcessLockHeld
    from atp_private.trade_engine.vision import decide as VD
    from atp_private.trade_engine.vision import notify as VN
    from atp_private.trade_engine.vision import store as VS
    from atp_private.trade_engine.vision import telegram_bot as TB
    from atp_private.trade_engine.vision import tg as TG
    if not VD.secret() or not VD.approver_ids():
        print("❌ VISION_CALLBACK_SECRET आणि TELEGRAM_APPROVER_IDS env हवेत — service सुरू नाही")
        return 1
    try:
        with ProcessLock("vision_telegram"):
            n = TB.expire_on_restart()
            print(f"vision telegram service सुरू — restart मुळे {n} pending रद्द")
            ok, why = TG.can_ask()
            if not ok:
                print(f"⚠️ {why}")
                VN.can_ask_alert(why)
            offset = int(VS.kv_get("tg_offset") or 0)
            while not stop.is_set():
                try:
                    offset = TB.poll_once(offset, timeout=poll_timeout)
                except Exception as exc:                                # noqa: BLE001 - systemd restarts Trade's service; here the loop goes on
                    print(f"srv2 telegram: {type(exc).__name__}: {exc}")
                    stop.wait(5)
                if once:
                    break
                stop.wait(TELEGRAM_PAUSE_S)
    except ProcessLockHeld:
        print("⏭️ vision telegram service आधीच चालू आहे")
    return 0


def start_services(vision=True, telegram=True):
    """Start the two P3 services in daemon threads (idempotent: a live thread is not started twice). Returns the names started."""
    stop = _services["stop"]
    stop.clear()
    started = []
    for name, on, fn in (("vision", vision, vision_service), ("telegram", telegram, telegram_service)):
        th = _services["threads"].get(name)
        if not on or (th is not None and th.is_alive()):
            continue
        th = threading.Thread(target=fn, args=(stop,), name=f"srv2-{name}", daemon=True)
        _services["threads"][name] = th
        th.start()
        started.append(name)
    return started


def stop_services(timeout=5):
    """Stop the P3 service threads (ATP's worker shutdown / tests)."""
    _services["stop"].set()
    for th in list(_services["threads"].values()):
        th.join(timeout)
    _services["threads"].clear()


# --- ATP's worker calls this ------------------------------------------------------------------------------------------------------------
def tick(now=None, calendar=None, run=None):
    """Run what is due at `now` (IST naive; default the IST clock). Returns the names that ran. Never raises: a failing part is logged
    by the copied code (notify_error) and the others still run. `run` (tests) replaces the three parts."""
    from atp_private.adapters.trade_config import get_ist_now
    now = pd.Timestamp(now or get_ist_now()).floor("s")
    run = run or {"engine": engine_due, "bot": bot_cycle, "exits": exit_cycle}
    ran = []
    if _within(now, ENGINE_WINDOW):
        try:
            if run["engine"](now, calendar):
                ran.append("engine")
        except Exception as exc:                                        # noqa: BLE001
            print(f"srv2 engine tick: {type(exc).__name__}: {exc}")
    minute = now.floor("min")
    if _within(now, BOT_WINDOW) and now.second >= BOT_AT_SECOND and _state["bot_minute"] != minute:
        _state["bot_minute"] = minute
        try:
            run["bot"]()
            ran.append("bot")
        except Exception as exc:                                        # noqa: BLE001
            print(f"srv2 bot tick: {type(exc).__name__}: {exc}")
    if _within(now, MONITOR_WINDOW):
        last = _state["monitor_last"]
        try:
            every = monitor_interval() if run.get("exits") is exit_cycle else 5.0
        except Exception:                                               # noqa: BLE001
            every = 15.0
        if last is None or (now - last).total_seconds() >= every:
            _state["monitor_last"] = now
            try:
                run["exits"]()
                ran.append("exits")
            except Exception as exc:                                    # noqa: BLE001
                print(f"srv2 exit tick: {type(exc).__name__}: {exc}")
    return ran


def engine_due(now, calendar=None):
    """The resident's loop, one step: the last 5M close, once its final grace has passed and until GIVE_UP_AFTER_S, retried every
    RETRY_EVERY_S while a due symbol's bar is not stored (engine_resident.run_symbol's timing). True when a run was made."""
    ER, _ESR, _TM = _private()
    close = now.floor("5min")
    since = (now - close).total_seconds()
    if since < ER.start_after_s() or since >= ER.GIVE_UP_AFTER_S:
        return False
    last = _state["engine"].get(close)
    if last is not None and (now - last).total_seconds() < ER.RETRY_EVERY_S:
        return False
    syms = ER.read_symbols(_state.get("engine_syms"))
    _state["engine_syms"] = syms
    _state["engine"] = {close: now}                                       # one close at a time (older closes: the catch-up of the next)
    engine_close(close, syms, calendar)
    return True
