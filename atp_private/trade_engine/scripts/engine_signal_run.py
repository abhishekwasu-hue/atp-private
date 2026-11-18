#!/usr/bin/env python3
"""🧭 Engine signal service (Abhi, one bot): शेवटच्या **बंद** 15M candle वर method engine ⇒ `engine_signal` store (VPS local SQLite). Bots हा
store adapter ने वाचतात (signal_source own / engine / both; 15M SRv2 = engine). Order / broker call नाही. Code मध्ये तारीख नाही. Holdout rows
कधीच engine input मध्ये नाहीत (data_policy; Daily warm-up फक्त Q33 प्रमाणे).

Engine: `--engine decision3` (default; env ENGINE_SIGNAL_ENGINE) = थर v2.2 (trend → area → pullback → commitment → R:R), symbols = dashboard
setting `signal_symbols` (default NIFTY / BANKNIFTY; `--symbols` दिले तरी त्या यादीबाहेरचे ⇒ ⏭️ skip — SENSEX फक्त data), 09:30–15:00 मध्ये
बंद होणारा प्रत्येक 15M bar. `--engine decision2` = जुना मार्ग (NIFTY 1m ⇒ थर 1–7), तसाच.
Fail-closed: data नाही / exception ⇒ त्या bar ची "error" row (नवा entry नाही) + Telegram ओळ (पहिलं अपयश, अजून अपयशी ⇒ 60 मिनिटांनी पुन्हा,
परत चालू ⇒ "recovered").
Token तपासणी (decision3; env ENGINE_TOKEN_CHECK, default on — Abhi): run सुरू होताना एक GET /v2/user/profile. Upstox ने token नाकारला
(401 / 403 / UDAPI100050) ⇒ प्रत्येक symbol ची error row + "🔴 Upstox token rejected …" (दर 15M bar, throttle नाही); पुन्हा पास ⇒
"✅ Upstox data restored …" एकदा. Network चूक ≠ नाकारला (आजचा मार्ग). Exits (trade_monitor) ना हात नाही. Token कधीच print नाही.

VPS cron (UTC; `scripts/install_engine_schedule.sh` लावतो — हाताने नाही). DECISIONS 37 (trigger_tf 5M): every minute with `--guard` —
the run exits at once unless the symbol's bar (5M, or 15M in the 15M what-if) closed a minute ago is due and not stored; a due run
decides every unstored closed 5M bar of the session (catch-up):
  * 3-10 * * 1-5  cd /root/Trade && set -a && . ./.env && set +a && ENGINE_SIGNAL_LOCK=1 python3 scripts/engine_signal_run.py --engine decision3 --guard   (V6: the lock is taken in Python and a skipped minute is logged)
Dry-run (store / Telegram नाही; बाजार बंद असला तरी): python3 scripts/engine_signal_run.py --dry-run --force
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import atp_private.trade_engine.engine_signal as ES  # noqa: E402



def signal_symbols(symbols_fn=None):
    """Dashboard setting `signal_symbols` (cloud_db; वाचता नाही ⇒ default NIFTY / BANKNIFTY)."""
    if symbols_fn is None:
        import atp_private.trade_engine.cloud_db as cloud_db
        symbols_fn = cloud_db.get_signal_symbols
    return [str(x).upper() for x in symbols_fn()]


def token_check_on():
    """env ENGINE_TOKEN_CHECK (default on; 0 / false / off / no ⇒ run सुरुवातीची token तपासणी नाही = जुना मार्ग)."""
    return (os.environ.get("ENGINE_TOKEN_CHECK") or "1").strip().lower() not in ("0", "false", "off", "no")


def _token_check(tok, check_fn=None):
    try:
        return str((check_fn or ES.token_check)(tok) or "unknown")
    except Exception as exc:                                             # noqa: BLE001 — तपासणी अयशस्वी ⇒ unknown (आजचा मार्ग)
        return f"unknown ({type(exc).__name__})"


def _settings(sym, settings_fn=None):
    """The symbol's engine3 settings. Env ENGINE3_TRIGGER_TF (set only by the `install_engine_schedule.sh --revert` cron line,
    DECISIONS 37 rollback) overrides the dashboard `engine3_trigger_tf` for this run."""
    s = ES.engine3_settings(sym) if settings_fn is None else ES.engine3_settings(sym, settings_fn)
    env = os.environ.get("ENGINE3_TRIGGER_TF", "").strip()
    return {**(s or {}), "engine3_trigger_tf": env} if env else s


def trigger_tf(sym, settings_fn=None):
    """The symbol's dashboard `engine3_trigger_tf` ⇒ "5M" (default, DECISIONS 37) / "15M"; an unreadable / bad value ⇒ "5M" here (the
    run itself then fails closed on a bad setting with its own error row)."""
    import atp_private.trade_engine.engine3_live as L
    try:
        return L.trigger_tf_of(_settings(sym, settings_fn))
    except ValueError:
        return "5M"


def due_symbols(syms, now=None, path=None, settings_fn=None):
    """The every-minute guard (DECISIONS 37, report §5): a symbol is due when the bar closed at least a minute ago on its trigger TF is
    inside the store window (`engine_first_bar_end` … `engine_last_bar_end`) and not stored yet (an error row does not count — the next
    minute retries). The 5M bar is checked first (no settings read when it is stored); 15M mode then needs a new 15M bar."""
    now = ES._naive(now or ES.now_ist())
    out = []
    for sym in syms:
        b5 = ES.due_bar_end(now, "5M")
        if not ES.in_window(ES.window_bar(b5, "5M")) or ES.has_bar(sym, b5, path):
            continue
        tf = trigger_tf(sym, settings_fn)
        b = b5 if tf == "5M" else ES.due_bar_end(now, "15M")
        if tf != "5M" and (not ES.in_window(b) or ES.has_bar(sym, b, path)):
            continue
        out.append(sym)
    if not out:
        print(f"⏭️ guard {now:%H:%M}: no due bar (stored / outside the store window) ⇒ exit")
    return out


LOCK_PATH = "/tmp/engine_signal_run.lock"
_LOCK_FH = None                                                          # kept open for the life of the process


def take_lock(path=LOCK_PATH):
    """V6 (never starve silently): non-blocking flock in Python (same lock file / flock(2) semantics as `flock -n`). True = got it
    (held until the process exits). False = the previous run still holds it => the caller logs the skipped minute."""
    global _LOCK_FH
    import fcntl
    fh = open(path, "a+")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return False
    _LOCK_FH = fh
    return True


def _area_alerts(sym, r, settings_fn=None, area_fn=None):
    """N14: the stored bar's `armed` visits (the engine's own) ⇒ bots_common.area_alert (one message per visit, edits after). The
    settings are the engine bot's dashboard settings (area_alerts / area_alert_daily_cap). Never raises."""
    try:
        from atp_private.trade_engine.bots_common import area_alert as AA
        p = ES.row_payload(r)
        if area_fn is None:
            import atp_private.trade_engine.cloud_db as cloud_db
            st = cloud_db.get_strategy_settings(ES.ENGINE3_SETTINGS_KEY, sym)
            area_fn = lambda s, armed: AA.on_bar(s, armed, settings=st)  # noqa: E731
        area_fn(sym, p.get("armed") or [])
    except Exception as exc:                                             # noqa: BLE001
        print(f"   ⚠️ {sym}: area alert skipped ({type(exc).__name__}: {exc})")


def _queue_now(sym, enter_fn=None):
    """N16 (30 Oct): right after the engine stored a setup bar, run each engine PAPER bot's own cycle for that symbol at once
    (`paper.engine_entry.enter_now`: same entry lock as srv2's minute poll ⇒ never twice; the gate queues the Vision row, ✅ still
    decides). srv2's poll stays as the fallback. Never raises (the poll picks it up)."""
    try:
        from atp_private.trade_engine.paper import engine_entry as EE
        fn = enter_fn or EE.enter_now
        for bot in EE.BOT_SETTINGS_KEY:
            msg = fn(bot, sym, send=None)
            print(f"   ⚡ {sym} {bot}: queued now — {str(msg or '')[:160]}")
    except Exception as exc:                                             # noqa: BLE001
        print(f"   ⚠️ {sym}: queue now failed ({type(exc).__name__}: {exc}) ⇒ srv2's next minute")


def main(argv=None, token_fn=None, run_fn=None, market_fn=None, send=None, alert_path=None, now=None, symbols_fn=None, check_fn=None,
         settings_fn=None, lock_path=None, enter_fn=None, area_fn=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None, help="default: decision3 ⇒ dashboard signal_symbols; decision2 ⇒ NIFTY. signal_symbols "
                                                    "बाहेरचे symbols ⇒ skip")
    ap.add_argument("--engine", default=None, help="decision3 (default) / decision2")
    ap.add_argument("--force", action="store_true", help="बाजार बंद असला तरी (dry-run / तपासणी)")
    ap.add_argument("--dry-run", action="store_true", help="store मध्ये लिहीत नाही, Telegram नाही — फक्त print")
    ap.add_argument("--guard", action="store_true", help="every-minute cron (DECISIONS 37): exit at once unless a closed bar of the "
                                                        "symbol's trigger TF (5M / 15M) inside the store window is not stored yet")
    ap.add_argument("--lock", action="store_true", help="take the engine lock here (non-blocking) and log a line when the previous "
                                                       "run still holds it (also env ENGINE_SIGNAL_LOCK=1, used by the cron line instead of an outer `flock -n`)")
    a = ap.parse_args(argv)
    lock_path = lock_path or os.environ.get("ENGINE_SIGNAL_LOCK_PATH") or LOCK_PATH   # N15: one lock per symbol (engine_resident)
    if (a.lock or os.environ.get("ENGINE_SIGNAL_LOCK") == "1") and not take_lock(lock_path):
        print(f"⏳ engine run still going (lock held) — this minute skipped [{(now or ES.now_ist()):%Y-%m-%d %H:%M}]")
        return 0
    engine = ES.engine_name(a.engine)
    if market_fn is None:
        from atp_private.trade_engine.config import is_market_open as market_fn
    if not a.force and not market_fn():
        print("बाजार बंद ⇒ engine signal नाही")
        return 0
    allowed = signal_symbols(symbols_fn)
    want = [x.strip().upper() for x in a.symbols.split(",") if x.strip()] if a.symbols else (allowed if engine == "decision3" else ["NIFTY"])
    syms = [x for x in dict.fromkeys(want) if x in allowed]
    for x in dict.fromkeys(want):
        if x not in allowed:
            print(f"⏭️ {x}: signal_symbols ({' / '.join(allowed)}) मध्ये नाही ⇒ engine signal नाही (dashboard setting)")
    if not syms:
        print("⏭️ एकही signal symbol नाही ⇒ engine signal नाही")
        return 0
    if a.guard and engine == "decision3":                                # DECISIONS 37: the every-minute cron runs only when a bar is due
        syms = due_symbols(syms, now, settings_fn=settings_fn)
        if not syms:
            return 0
    if token_fn is None:
        import atp_private.trade_engine.cloud_db as cloud_db
        token_fn = lambda: cloud_db.get_effective_upstox_token(None)  # noqa: E731
    tok = token_fn()
    _bars = {}

    def bar_for(sym):                                                    # the error row's bar: the symbol's own trigger TF (5M / 15M)
        if sym not in _bars:
            _bars[sym] = ES.expected_bar_end(now or ES.now_ist(), trigger_tf(sym, settings_fn) if engine == "decision3" else "15M")
        return _bars[sym]
    if not tok:
        msg = "Upstox token नाही — engine signal मोजता येत नाही (आधी daily login)"
        print(f"❌ {msg}")
        if not a.dry_run:
            for sym in syms:
                ES.save_error(sym, bar_for(sym), msg, engine=engine)
                ES.alert_error(sym, "Upstox token missing", send=send, state_path=alert_path, now=now)
        return 2
    if engine == "decision3" and token_check_on():                       # Abhi: नाकारलेला token प्रत्येक 15M bar ला दिसावा
        chk = _token_check(tok, check_fn)
        if chk.startswith("rejected"):
            msg = f"Upstox token {chk} — no engine reading, no entries (log in again)"
            print(f"❌ {msg}")
            if not a.dry_run:
                for sym in syms:
                    try:
                        ES.save_error(sym, bar_for(sym), msg, engine=engine)
                    except Exception as exc2:                            # noqa: BLE001
                        print(f"⚠️ {sym}: error row लिहिता आली नाही: {exc2}")
                try:
                    ES.alert_token_rejected(send=send, state_path=alert_path, now=now, detail=chk)
                except Exception as exc2:                                # noqa: BLE001
                    print(f"⚠️ token alert पाठवता आला नाही: {type(exc2).__name__}: {exc2}")
            return 2
        if chk.startswith("unknown"):
            print(f"⚠️ Upstox token check {chk} ⇒ engine तसाच चालतो (network चूक ≠ token नाकारला)")
        if chk == "ok" and not a.dry_run:
            try:
                ES.alert_token_restored(send=send, state_path=alert_path, now=now)
            except Exception as exc2:                                    # noqa: BLE001 — alert मुळे run कधीच थांबत नाही
                print(f"⚠️ token restored alert पाठवता आला नाही: {type(exc2).__name__}: {exc2}")
    if run_fn is None:
        if engine == "decision3":
            run_fn = lambda sym, t: ES.run3(sym, t, now=now, dry_run=a.dry_run, s=_settings(sym, settings_fn))  # noqa: E731
        else:
            run_fn = ES.run
    rc = 0
    for sym in syms:
        try:
            t0, g0 = time.perf_counter(), _gets()
            try:
                r = run_fn(sym, tok)
            finally:                                                     # V6: per-symbol cycle time + peak RSS (log only)
                print(_timing_line(sym, engine, time.perf_counter() - t0))
                if _gets() > g0:                                         # M56 O1 (D3): Upstox GETs of this symbol's cycle (log only)
                    print(f"🌐 {sym} [{engine}] Upstox GETs {_gets() - g0}")
            if not a.dry_run:
                ES.alert_recovered(sym, send=send, state_path=alert_path, now=now)
                if r.get("bar_ts") and not r.get("skipped"):            # V6 delay guard: decided late after the bar close => one notice a day
                    ES.alert_engine_delay(sym, r["bar_ts"], r.get("computed_at"), None, send=send, state_path=alert_path, now=now,
                                          tf=trigger_tf(sym, settings_fn) if engine == "decision3" else "15M")
                dp = _data_problem(r, sym)
                if dp:                                                   # Abhi Z-1c: volume NA at the decision ⇒ data problem (entry नाही)
                    ES.alert_data_problem(sym, dp, send=send, state_path=alert_path, now=now)
                if r.get("watch_alerts_new"):                            # EN1 WATCH (DECISIONS 118 / 119): M53 INFO tier, once per visit
                    ES.alert_watch(sym, r["watch_alerts_new"], send=send, state_path=alert_path, now=now)
            if r.get("skipped"):
                print(f"⏭️ {sym} [{engine}] {r['bar_ts']}: {r['decision']} — {r['skipped']}")
                continue
            tag = " (dry-run, store नाही)" if a.dry_run else ""
            print(f"✅ {sym} [{engine}] {r['bar_ts']}: {r['decision']} gate {r.get('gate') or '—'} dir {r.get('direction')} "
                  f"grade {r.get('grade') or '—'} · {r.get('reason') or ''}{tag}{_m1_tag(r)}"
                  + (f" · catch-up {len(r['caught_up'])} earlier 5M bar(s)" if r.get("caught_up") else ""))
            if not a.dry_run:
                print(f"   {ES.opinion(sym, r['bar_ts'])}")
                if r.get("decision") == "setup":                         # N16: the card's row is queued now, not at srv2's next minute
                    _queue_now(sym, enter_fn)
                _area_alerts(sym, r, settings_fn, area_fn)               # N14: one message per area visit (edits after)
        except Exception as exc:                                         # noqa: BLE001 — fail-closed
            msg = f"{type(exc).__name__}: {exc}"
            print(f"❌ {sym} [{engine}]: {msg} ⇒ entry नाही (fail-closed)")
            rc = 1
            if not a.dry_run:
                try:
                    ES.save_error(sym, bar_for(sym), msg, engine=engine)
                except Exception as exc2:                                # noqa: BLE001
                    print(f"⚠️ {sym}: error row लिहिता आली नाही: {exc2}")
                if getattr(exc, "bar_late", False) and getattr(exc, "one_bar", False):   # DECISIONS 37: one 5M close late ⇒ retry next minute
                    print(f"   ⏳ {sym}: the 5M bar is late at Upstox ⇒ silent retry next minute (no Telegram)")
                elif getattr(exc, "token_rejected", False):               # engine3_live.TokenRejected ⇒ तीच 🔴 ओळ (दर bar, एकदाच)
                    try:
                        ES.alert_token_rejected(send=send, state_path=alert_path, now=now, detail=str(exc))
                    except Exception as exc2:                            # noqa: BLE001
                        print(f"⚠️ token alert पाठवता आला नाही: {type(exc2).__name__}: {exc2}")
                elif getattr(exc, "data_problem", False) and _fut_required(sym):   # Abhi Z-1c: FUT volume missing ⇒ एकच ओळ, दिवसातून एकदा
                    ES.alert_data_problem(sym, str(exc), send=send, state_path=alert_path, now=now)
                else:
                    ES.alert_error(sym, msg, send=send, state_path=alert_path, now=now,
                                   setting=bool(getattr(exc, "setting_error", False)))   # dashboard engine3_* setting ⇒ "fix it on the dashboard"
    if rc == 0 and not a.dry_run and syms:                               # M53 MS-6: the day's quiet "bot alive" line (once a day)
        try:
            ES.alert_heartbeat(syms, send=send, state_path=alert_path, now=now)
        except Exception as exc:                                         # noqa: BLE001 — alerts never stop the run
            print(f"⚠️ heartbeat पाठवता आला नाही: {type(exc).__name__}: {exc}")
    return rc


def _gets():
    try:
        import atp_private.trade_engine.engine3_live as L
        return int(L.GETS["n"])
    except Exception:                                                    # noqa: BLE001
        return 0


def _timing_line(sym, engine, secs):
    """V6 (DECISIONS 106): one timing line per symbol per cycle — the engine's own compute time and the process peak RSS so far
    (Linux ru_maxrss = KB). Log only; never raises."""
    try:
        import resource
        rss = f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MB"
    except Exception:                                                    # noqa: BLE001 — no resource module (Windows) ⇒ RSS NA
        rss = "NA"
    return f"⏱️ {sym} [{engine}] cycle {secs:.1f} s · peak RSS {rss}"


def _m1_tag(r):
    """Z-1o: payload `m1` ⇒ " · 1m ✓ (complete n/m)" / " · 1m off" / " · 1m fallback: …" (decision3 फक्त; नसेल ⇒ ""). n = swings2
    m1_status "complete" 15M bars (1m चे high / low जुळतात); जुनी row (m15_complete नाही) ⇒ 1m rows असलेले bars."""
    try:
        import json
        m = (json.loads(r.get("payload") or "{}") or {}).get("m1")
    except (TypeError, ValueError):
        return ""
    if not m:
        return ""
    if m.get("used"):
        n = f"complete {m['m15_complete']}" if m.get("m15_complete") is not None else m.get("m15_covered")
        return f" · 1m ✓ ({n}/{m.get('m15_bars')})" + (f" {m['note']}" if m.get("note") else "")
    return " · 1m off" if not m.get("setting") else f" · 1m fallback: {m.get('note')}"


def _fut_required(sym):
    """Abhi Z-1c: the data-problem Telegram line only for the FUT-required symbols (NIFTY / BANKNIFTY) — never SENSEX."""
    import atp_private.trade_engine.engine3_live as L
    return str(sym).upper() in L.FUT_REQUIRED


def _data_problem(r, sym=None):
    """engine row (payload JSON) मधली data-problem नोंद (V22 ⑥ c0 volume NA) — नाही / FUT_REQUIRED बाहेरचा symbol ⇒ None. Payload
    engine3_live.fit_payload ने लहान केलेला असतो (कधीच मधेच कापलेला नाही) ⇒ flag हरवत नाही."""
    if sym is not None and not _fut_required(sym):
        return None
    try:
        import json
        return (json.loads(r.get("payload") or "{}") or {}).get("data_problem")
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    sys.exit(main())
