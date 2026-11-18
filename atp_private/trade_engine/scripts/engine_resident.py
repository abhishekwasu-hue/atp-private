"""N15 (owner order 30 Oct "Telegram timing") — the engine at the close: one resident process for the session (started by one cron
line, `scripts/install_engine_schedule.sh`) instead of the every-minute cron with its one-minute offset. At each 5M close + a few
seconds it runs `scripts/engine_signal_run.py --symbols SYM` for every signal symbol IN PARALLEL, each with its own lock
(ENGINE_SIGNAL_LOCK_PATH), and retries every few seconds until that bar is stored (Upstox may need a few seconds for the bar). Every
skipped / late run logs one line. Decisions are the same code on the same bars (byte-identical stored rows); only the start time moves.

  python3 scripts/engine_resident.py            # until the store window ends (engine_last_bar_end) / the market closes
M56 O6 (D10): `signal_symbols` is read again at every close (a dashboard change needs no restart); the store window is judged with the
run's own settings (engine_signal_run._settings — a dashboard engine_first/last_bar_end, else the default); a start after the window
exits at once (the cron line ends at 15:25 IST — no re-spawn churn after the close).
The timing constants below are operational (when to start the run), not reading rules."""
import os
import subprocess
import sys
import threading
import time

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

START_AFTER_CLOSE_S = 3        # first try this many seconds after the 5M close
RETRY_EVERY_S = 5              # then every this many seconds …
GIVE_UP_AFTER_S = 120          # … until this long after the close (the next close takes over; catch-up stores the missed bar)


def start_after_s():
    """M56 E3 (A3): the first try waits for the bar to be final — max(START_AFTER_CLOSE_S, engine3_live `engine3_bar_final_grace_s`
    default); an earlier try would only hit the engine's silent "not final yet" retry."""
    try:
        import atp_private.trade_engine.engine3_live as L
        return max(float(START_AFTER_CLOSE_S), L.final_grace().total_seconds())
    except Exception:                                                    # noqa: BLE001
        return float(START_AFTER_CLOSE_S)


def log(msg, now=None):
    import atp_private.trade_engine.engine_signal as ES
    print(f"[{(now or ES.now_ist()):%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def tf_of(sym):
    try:
        from atp_private.trade_engine.scripts import engine_signal_run as ESR
        return ESR.trigger_tf(sym)
    except Exception:                                                    # noqa: BLE001
        return "5M"


_LAST_SETTINGS = {}                                                       # sym ⇒ the last settings read without an error


def settings_of(sym):
    """M56 O6 (D10): the symbol's store-window / engine3_* settings from its stored dashboard row (cloud_db.get_strategy_settings_raw —
    it raises on an outage instead of returning code defaults), so the resident judges the window with the value the run stores by. A
    read error ⇒ the last good settings of this symbol (never a silent switch to the defaults); none yet ⇒ {} (= the code defaults)."""
    import atp_private.trade_engine.engine_signal as ES
    try:
        import atp_private.trade_engine.cloud_db as cloud_db
        raw = cloud_db.get_strategy_settings_raw(ES.ENGINE3_SETTINGS_KEY, str(sym).upper()) or {}
        got = {k: v for k, v in dict(raw).items() if str(k).startswith("engine3_") or k in ES.WINDOW_KEYS}
    except Exception as exc:                                             # noqa: BLE001
        log(f"⚠️ {sym} settings unreadable ({type(exc).__name__}) ⇒ last good settings")
        return dict(_LAST_SETTINGS.get(sym, {}))
    _LAST_SETTINGS[sym] = got
    return dict(got)


def due(sym, close, path=None, s=None):
    """This symbol decides the bar that closed at `close`: inside the store window, not stored yet, and on its trigger TF."""
    import atp_private.trade_engine.engine_signal as ES
    if tf_of(sym) != "5M" and close.minute % 15:
        return False
    return ES.in_window(ES.window_bar(close, "5M"), s) and not ES.has_bar(sym, close, path)


def window_over(close, syms, settings=None):
    """Every symbol's store window (its own `engine_last_bar_end`, dashboard or default) has ended by this close."""
    import atp_private.trade_engine.engine_signal as ES
    settings = settings or {}
    for sym in syms or [None]:
        s = {**ES.DEFAULTS, **(settings.get(sym) or {})}
        if ES.in_window(ES.window_bar(close, "5M"), s) or close.time() <= pd.Timestamp(s["engine_last_bar_end"]).time():
            return False
    return True


def read_symbols(prev=None):
    """M56 O6 (D10): the dashboard `signal_symbols`, read again at every close (a change needs no restart). Read through
    cloud_db.get_strategy_settings_raw (it raises on an outage; get_signal_symbols would silently return the default list and drop e.g.
    SENSEX) ⇒ an error keeps the last list; no last list yet (first read) ⇒ the dashboard getter (default list)."""
    try:
        import atp_private.trade_engine.cloud_db as cloud_db
        raw = (cloud_db.get_strategy_settings_raw(cloud_db.SIGNAL_SYMBOLS_STRATEGY_KEY, cloud_db.SIGNAL_SYMBOLS_SYMBOL_KEY) or {}) \
            .get("signal_symbols")
        return cloud_db.clean_signal_symbols(raw) if raw else list(cloud_db.SIGNAL_SYMBOLS_DEFAULT)
    except Exception as exc:                                             # noqa: BLE001
        if prev:
            log(f"⚠️ signal_symbols unreadable ({type(exc).__name__}) ⇒ last list {', '.join(prev)}")
            return list(prev)
        from atp_private.trade_engine.scripts import engine_signal_run as ESR
        return ESR.signal_symbols(None)


def run_symbol(sym, close, runner=None, sleep=time.sleep, clock=None, path=None):
    """Run → stored? done : retry every RETRY_EVERY_S until GIVE_UP_AFTER_S. Returns (stored, tries)."""
    import atp_private.trade_engine.engine_signal as ES
    clock = clock or ES.now_ist
    runner = runner or _subprocess_run
    tries = 0
    while True:
        tries += 1
        runner(sym)
        if ES.has_bar(sym, close, path):
            took = (pd.Timestamp(clock()) - close).total_seconds()
            if tries > 1 or took > 60:
                log(f"⏱ {sym} {close:%H:%M} stored after {took:.0f} s ({tries} tries)")
            return True, tries
        if (pd.Timestamp(clock()) - close).total_seconds() >= GIVE_UP_AFTER_S:
            log(f"⚠️ {sym} {close:%H:%M} not stored {GIVE_UP_AFTER_S} s after the close ({tries} tries) ⇒ the next close catches it up")
            return False, tries
        sleep(RETRY_EVERY_S)


def _subprocess_run(sym):
    env = {**os.environ, "ENGINE_SIGNAL_LOCK": "1", "ENGINE_SIGNAL_LOCK_PATH": f"/tmp/engine_signal_run_{sym}.lock"}
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "engine_signal_run.py"), "--engine", "decision3", "--symbols", sym],
                   cwd=ROOT, env=env, timeout=GIVE_UP_AFTER_S + 60)


def one_close(close, syms, runner=None, sleep=time.sleep, clock=None, path=None, settings=None):
    """Every due symbol of this close in parallel (one thread each)."""
    todo = [s for s in syms if due(s, close, path, (settings or {}).get(s))]
    th = [threading.Thread(target=run_symbol, args=(s, close, runner, sleep, clock, path), daemon=True) for s in todo]
    for t in th:
        t.start()
    for t in th:
        t.join()
    return todo


def main(argv=None, clock=None, sleep=time.sleep, market_fn=None, symbols_fn=None, settings_fn=None, close_fn=None):
    import atp_private.trade_engine.engine_signal as ES
    if market_fn is None:
        from atp_private.trade_engine.config import is_market_open as market_fn
    clock = clock or ES.now_ist
    symbols_fn = symbols_fn or read_symbols
    settings_fn = settings_fn or settings_of
    close_fn = close_fn or one_close
    syms = symbols_fn(None)
    now = pd.Timestamp(clock())
    if window_over(now.floor("5min"), syms, {x: settings_fn(x) for x in syms}):   # M56 O6: started after the window ⇒ exit at once (no churn)
        log(f"store window over ({now:%H:%M}) ⇒ exit (cron starts the resident next session)", now)
        return 0
    log(f"engine resident start · symbols {', '.join(syms)}")
    while True:
        now = pd.Timestamp(clock())
        close = now.floor("5min") + pd.Timedelta(minutes=5)              # the close is fixed first: a slow read never skips it
        new = symbols_fn(syms)                                           # M56 O6 (D10): the dashboard list for every close — read
        if new != syms:                                                  # before the wait, so the reads never delay the run at the close
            log(f"signal_symbols changed: {', '.join(syms)} ⇒ {', '.join(new)}")
            syms = new
        settings = {x: settings_fn(x) for x in syms}                     # the run's own settings (store window = dashboard or default)
        wait = (close + pd.Timedelta(seconds=start_after_s()) - pd.Timestamp(clock())).total_seconds()   # M56 E3: the final grace
        if wait > 0:
            sleep(wait)
        if window_over(close, syms, settings):
            log("store window over ⇒ exit")
            return 0
        if not market_fn():
            continue
        try:
            close_fn(close, syms, settings=settings)
        except Exception as exc:                                         # noqa: BLE001 — the next close tries again
            log(f"❌ close {close:%H:%M}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    sys.exit(main())
