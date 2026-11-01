"""engine_signal.py — common analysis engine चा signal bots ना एकाच interface ने (Abhi, Monday PAPER). **Order कधीच नाही.**

Engine (`engine_name`, default decision3 — Abhi, one bot): decision3 = थर v2.2 method engine (trend → area → pullback → commitment + c1; R:R नाही — Abhi 13 Oct;
live feed `engine3_live.py`, NIFTY / BANKNIFTY / SENSEX); decision2 = जुना मार्ग (NIFTY 1m ⇒ थर 1–7) तसाच उपलब्ध (`--engine decision2`).

रचना:
  • Service (`scripts/engine_signal_run.py`, cron, प्रत्येक बंद 15M candle नंतर): NIFTY 1m (Upstox, holdout वगळून) ⇒ थर 1–7 ⇒ शेवटच्या बंद
    15M candle चा decision2 निर्णय ⇒ इथल्या store मध्ये (VPS local SQLite, `ENGINE_SIGNAL_DB`, default data/engine_signals.db).
  • Adapter (bots, vision caption): `latest`, `opinion`, `own_allowed`, `pending_entry`, `mark_consumed`.
  • Bot setting `signal_source` (dashboard): own / engine (default since M56 O4, owner default M56-Q5) / both.
      own    ⇒ bot चा स्वतःचा signal; engine फक्त shadow मत (caption).
      engine ⇒ फक्त engine चा setup (bot चे spread selection / strikes / execution / settings तसेच) — `engine_entry.py`.
      both   ⇒ bot चा signal फक्त engine च्या ताज्या setup शी दिशा जुळली तरच.
  Engine चं मत निर्णयात फक्त `engine` / `both` निवडल्यावर; ते सुद्धा Vision + Abhi ✅ नंतरच entry (vision/gate.py).
"""
import json
import os
import sqlite3

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES = ("own", "engine", "both")
# Abhi (addition D, 23 Oct): for signal_source = engine the bot's UI / card / trade-message label is the engine's own name; the old bot
# name ("15M Dynamic SR …") is shown only when the signal comes from the bot itself (signal_source = own). Display only.
ENGINE_LABEL = "Engine (PAPER)"


def display_label(own_label, source=None):
    """The label to show: ENGINE_LABEL for an engine signal / an engine-sourced bot (source "engine" or True), else the bot's own label."""
    return ENGINE_LABEL if source is True or str(source or "").lower() == "engine" else own_label
DEFAULTS = {"signal_source": "engine",                                   # M56 O4: engine-only unless the dashboard says own / both
            "engine_max_age_min": 30, "engine_lookback_days": 100, "engine_name": "decision3",
            "engine_first_bar_end": "09:30", "engine_last_bar_end": "15:00",
            "engine_delay_alert_min": 5}       # decision3: फक्त या वेळांत बंद होणारे 15M bars
WINDOW_KEYS = ("engine_first_bar_end", "engine_last_bar_end")              # M56 O6 (D10): a dashboard row value wins over the default
ENGINES = ("decision3", "decision2")
ERROR = "error"                                                                     # fail-closed row (data / exception) ⇒ entry नाही
DIR_TXT = {1: "BULLISH", -1: "BEARISH"}
SIDE_TXT = {1: "bull put", -1: "bear call"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS engine_signals (
  symbol TEXT NOT NULL, bar_ts TEXT NOT NULL, computed_at TEXT, decision TEXT, gate TEXT, direction INTEGER,
  level_lo REAL, level_hi REAL, entry REAL, invalidation REAL, target REAL, grade TEXT, reason TEXT, payload TEXT,
  PRIMARY KEY (symbol, bar_ts));
CREATE TABLE IF NOT EXISTS engine_consumed (
  bot TEXT NOT NULL, symbol TEXT NOT NULL, bar_ts TEXT NOT NULL, status TEXT, at TEXT, PRIMARY KEY (bot, symbol, bar_ts));
CREATE TABLE IF NOT EXISTS engine_entry_consumed (
  bot TEXT NOT NULL, symbol TEXT NOT NULL, visit_id TEXT NOT NULL, model TEXT NOT NULL, status TEXT, bar_ts TEXT, at TEXT,
  direction INTEGER, lo REAL, hi REAL,
  PRIMARY KEY (bot, symbol, visit_id, model));
CREATE TABLE IF NOT EXISTS engine_entry_seen (
  bot TEXT NOT NULL, symbol TEXT NOT NULL, visit_id TEXT NOT NULL, model TEXT NOT NULL, at TEXT,
  PRIMARY KEY (bot, symbol, visit_id, model));
"""
# columns added after the first entry-models store (an older engine_entry_consumed table gets them on connect, empty for old rows)
ENTRY_ZONE_COLS = (("direction", "INTEGER"), ("lo", "REAL"), ("hi", "REAL"))


def db_path(path=None):
    return path or os.environ.get("ENGINE_SIGNAL_DB") or os.path.join(ROOT, "data", "engine_signals.db")


def connect(path=None, timeout=5):
    p = db_path(path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    c = sqlite3.connect(p, timeout=timeout)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    have = {r[1] for r in c.execute("PRAGMA table_info(engine_entry_consumed)")}
    for col, typ in ENTRY_ZONE_COLS:                                     # additive migration only (never drops / rewrites)
        if col not in have:
            c.execute(f"ALTER TABLE engine_entry_consumed ADD COLUMN {col} {typ}")
    return c


def now_ist():
    from atp_private.trade_engine.config import get_ist_now                                      # M56 O3 (D5): the one IST clock helper
    return pd.Timestamp(get_ist_now()).floor("s")


def _naive(t):
    """IST naive Timestamp (tz-aware ⇒ IST मध्ये नेऊन tz काढा)."""
    t = pd.Timestamp(t)
    return t.tz_convert("Asia/Kolkata").tz_localize(None) if t.tzinfo is not None else t


def source_of(settings, key="signal_source"):
    """M56 O4 (D7, owner default M56-Q5): unset / empty / unknown ⇒ "engine" (engine-only; the bot's own signals only on an explicit
    own / both). LIVE is untouched: own_signal_ok passes every non-PAPER row and engine entries are PAPER only."""
    v = str((settings or {}).get(key) or DEFAULTS["signal_source"]).lower()
    return v if v in SOURCES else DEFAULTS["signal_source"]


# ---------------------------------------------------------------------------------------------------------------- service
def row_from_decision(symbol, dec, bar_end):
    """decision2 चा dict ⇒ store row. दिशा: risk point (entry vs invalidation) नाहीतर I दिशा."""
    p = dec.get("points") or {}
    risk = p.get("10_risk") or {}
    area = p.get("7_area") or {}
    band = area.get("band") or [None, None]
    d = None
    if risk.get("entry") is not None and risk.get("invalidation") is not None:
        d = 1 if risk["entry"] > risk["invalidation"] else -1
    elif ((p.get("2_parent") or {}).get("I") or {}).get("dir") in (1, -1):
        d = int(p["2_parent"]["I"]["dir"])
    return {"symbol": str(symbol).upper(), "bar_ts": str(pd.Timestamp(bar_end)), "computed_at": str(now_ist()), "decision": dec.get("decision"),
            "gate": dec.get("gate"), "direction": d, "level_lo": band[0], "level_hi": band[1], "entry": risk.get("entry"),
            "invalidation": risk.get("invalidation"), "target": risk.get("target"), "grade": dec.get("grade"),
            "reason": dec.get("where_wrong"), "payload": json.dumps(dec, ensure_ascii=False, default=str)[:20000]}


def save(row, path=None):
    with connect(path) as c:
        cols = list(row)
        c.execute(f"INSERT OR REPLACE INTO engine_signals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [row[k] for k in cols])


def compute(m1, fut=None):
    """1m frame (holdout आधीच वगळलेला) ⇒ शेवटच्या **बंद** 15M candle चा (decision, bar_end). सगळं ≤ त्या candle."""
    from atp_private.trade_engine.decision2 import engine as DE
    from atp_private.trade_engine.pivots import engine as PE
    from atp_private.trade_engine.scripts import decision_check as DCK
    m15 = PE.bars_15m(m1)
    if not len(m15):
        raise ValueError("no 15M candles")
    t = len(m15) - 1
    C = DCK.build_ctx(m15, m1, fut, max(0, t - 2))
    return DE.decide(C, t), m15["bar_end"].iloc[t]


def run(symbol, access_token, fetch=None, path=None, lookback_days=None, now=None):
    """एक service cycle. रिटर्न saved row. Token नाही ⇒ स्पष्ट ValueError."""
    if not access_token:
        raise ValueError("no Upstox token — engine signal cannot run (do the daily login first)")
    from atp_private.trade_engine.elliott import data_policy as DP
    if fetch is None:
        from atp_private.trade_engine.upstox_api import fetch_candles as fetch
    m1 = fetch(access_token, symbol, 0, interval="1minute", lookback_days=int(lookback_days or DEFAULTS["engine_lookback_days"]))
    if m1 is None or not len(m1):
        raise ValueError("no 1m candles received")
    m1 = m1.copy()
    m1["timestamp"] = pd.to_datetime(m1["timestamp"])
    if getattr(m1["timestamp"].dt, "tz", None) is not None:
        m1["timestamp"] = m1["timestamp"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    now = _naive(now or now_ist())
    m1 = m1[m1["timestamp"] + pd.Timedelta(minutes=1) <= now]                       # फक्त बंद 1m candles
    m1 = DP.filter_allowed(m1[["timestamp", "open", "high", "low", "close"]].sort_values("timestamp").reset_index(drop=True), "annotation")
    dec, bar_end = compute(m1)
    if pd.Timestamp(bar_end) > now:                                                 # शेवटचा 15M अजून बंद नाही ⇒ आधीचा हवा
        raise ValueError("the last 15M candle is not closed yet")
    row = row_from_decision(symbol, dec, bar_end)
    save(row, path)
    return row


def engine_name(value=None):
    """decision3 (default) / decision2 — CLI `--engine` नाहीतर env `ENGINE_SIGNAL_ENGINE`. अज्ञात ⇒ ValueError (अंदाज नाही)."""
    v = str(value or os.environ.get("ENGINE_SIGNAL_ENGINE") or DEFAULTS["engine_name"]).strip().lower()
    if v not in ENGINES:
        raise ValueError(f"engine {v!r} — must be one of {ENGINES}")
    return v


def _hm(s):
    h, m = (int(x) for x in str(s).split(":"))
    return h, m


def in_window(bar_end, s=None):
    """bar_end (IST) `engine_first_bar_end` … `engine_last_bar_end` मध्ये? (09:30 = 09:15 चा opening candle सुद्धा मोजला जातो.)"""
    s = {**DEFAULTS, **(s or {})}
    b = pd.Timestamp(bar_end)
    return _hm(s["engine_first_bar_end"]) <= (b.hour, b.minute) <= _hm(s["engine_last_bar_end"])


def _win(s=None):
    s = {**DEFAULTS, **(s or {})}
    return s["engine_first_bar_end"], s["engine_last_bar_end"]


def window_bar(bar_end, tf="15M"):
    """The bar_end the store window is judged on. 15M ⇒ itself. 5M (DECISIONS 37) ⇒ the end of the 09:15-anchored 15M bin holding that
    5M candle (trigger_frame.bin_start), so the 09:20 / 09:25 candles count with the 09:30 opening bar and 15:05 / 15:10 stay out —
    the same window as the 15M bars."""
    b = pd.Timestamp(bar_end)
    if str(tf).upper() != "5M":
        return b
    from atp_private.trade_engine.decision3.trigger_frame import BAR15, bin_start
    return pd.Timestamp(bin_start([b - pd.Timedelta(minutes=5)]).iloc[0]) + BAR15


def expected_bar_end(now, tf="15M"):
    """आत्ता (IST) शेवटचा बंद व्हायला हवा तो bar_end — 15M (default, आजचं) / 5M (trigger_tf 5M, DECISIONS 37)."""
    return _naive(now).floor("5min" if str(tf).upper() == "5M" else "15min")


def due_bar_end(now, tf="15M"):
    """The every-minute guard (DECISIONS 37): the bar the cycle at `now` should decide = the last bar closed at least one minute ago
    (the old cron's minute-1 offset: Upstox has the bar by then)."""
    return expected_bar_end(_naive(now) - pd.Timedelta(minutes=1), tf)


def has_bar(symbol, bar_ts, path=None):
    """A non-error row stored for (symbol, bar_ts)? Store error ⇒ False (the cycle runs; fail closed there)."""
    try:
        with connect(path) as c:
            r = c.execute("SELECT 1 FROM engine_signals WHERE symbol=? AND bar_ts=? AND decision!=?",
                          (str(symbol).upper(), str(pd.Timestamp(bar_ts)), ERROR)).fetchone()
        return r is not None
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.has_bar: {type(exc).__name__}: {exc}")
        return False


def last_stored(symbol, now, path=None):
    """Catch-up (DECISIONS 37, report §5): the newest non-error bar_ts stored for the symbol on now's day (≤ now), else that day's
    midnight (the whole session is decided). Store error ⇒ None (only the last bar is decided — today's behaviour)."""
    now = _naive(now)
    try:
        with connect(path) as c:
            r = c.execute("SELECT MAX(bar_ts) AS b FROM engine_signals WHERE symbol=? AND decision!=? AND bar_ts<=? AND bar_ts>=?",
                          (str(symbol).upper(), ERROR, str(now), str(now.normalize()))).fetchone()
        return pd.Timestamp(r["b"]) if r is not None and r["b"] else now.normalize()
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.last_stored: {type(exc).__name__}: {exc}")
        return None


def prev_trigger_bar(symbol, now, path=None):
    """M56 E3 (A3): the newest non-error row of now's day (≤ now) ⇒ {"bar_ts", "bar_ohlc", "revised"} for the next cycle's "is the
    bar final" comparison (engine3_live.bar_revision); no row / no stored OHLC / store error ⇒ None (nothing compared)."""
    now = _naive(now)
    try:
        with connect(path) as c:
            r = c.execute("SELECT bar_ts, payload FROM engine_signals WHERE symbol=? AND decision!=? AND bar_ts<=? AND bar_ts>=? "
                          "ORDER BY bar_ts DESC LIMIT 1", (str(symbol).upper(), ERROR, str(now), str(now.normalize()))).fetchone()
        p = json.loads(r["payload"] or "{}") if r is not None else {}
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.prev_trigger_bar: {type(exc).__name__}: {exc}")
        return None
    if not isinstance(p, dict) or not isinstance(p.get("bar_ohlc"), dict):
        return None
    return {"bar_ts": r["bar_ts"], "bar_ohlc": p["bar_ohlc"], "revised": bool(p.get("bar_revision"))}


def keep_original(row, path=None):
    """M56 E3 (review): a row re-decided for a revised bar (payload `bar_revision`) carries the stored row it replaces —
    bar_revision.original = {decision, entries, computed_at} — before INSERT OR REPLACE. A re-decided entry is always older than the
    N18 freshness (it can only cancel / stay stale, never open late). Never raises; no revision ⇒ unchanged."""
    try:
        pay = json.loads(row.get("payload") or "{}")
        rev = pay.get("bar_revision")
        if not isinstance(rev, dict) or "original" in rev:
            return row
        with connect(path) as c:
            old = c.execute("SELECT decision, computed_at, payload FROM engine_signals WHERE symbol=? AND bar_ts=?",
                            (str(row["symbol"]).upper(), str(row["bar_ts"]))).fetchone()
        if old is None:
            return row
        op = json.loads(old["payload"] or "{}")
        rev["original"] = {"decision": old["decision"], "computed_at": old["computed_at"],
                           "entries": op.get("entries") if isinstance(op, dict) else None}
        row["payload"] = json.dumps(pay, ensure_ascii=False, default=str)
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.keep_original: {type(exc).__name__}: {exc}")
    return row


def save_error(symbol, bar_ts, msg, path=None, engine="decision3"):
    """Fail-closed नोंद: त्या bar साठी "error" row ⇒ `pending_entry` नवा entry देत नाही (✅ च्या वाटेतला आधीचा setup मात्र तसाच — gate ठरवतो)."""
    save({"symbol": str(symbol).upper(), "bar_ts": str(pd.Timestamp(bar_ts)), "computed_at": str(now_ist()), "decision": ERROR,
          "gate": "data", "direction": None, "level_lo": None, "level_hi": None, "entry": None, "invalidation": None, "target": None,
          "grade": None, "reason": str(msg)[:300], "payload": json.dumps({"engine": engine, "error": str(msg)[:500]}, ensure_ascii=False)},
         path)


ALERT_REPEAT_MIN = 60                                                       # अजून अपयश ⇒ इतक्या मिनिटांनी पुन्हा एक ओळ


def _alert_state(p):
    try:
        st = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    except (OSError, ValueError):
        return {}
    return st if isinstance(st, dict) else {}                            # valid JSON पण dict नाही (उदा. [1, 2]) ⇒ रिकामं


def _alert_send(line, send):
    try:
        if send is None:
            from atp_private.trade_engine.notifications import send_telegram_message as send
        send(line)
    except Exception:                                                    # noqa: BLE001
        print(line)


def _alert_path(state_path):
    return state_path or os.path.join(ROOT, "data", "engine_signal_alerts.json")


def _once_path(p):
    return os.path.splitext(p)[0] + "_once.json"


def alert_error(symbol, msg, send=None, state_path=None, now=None, setting=False):
    """Engine error ⇒ Telegram: (cause, day) प्रमाणे दिवसातून एकदाच (N9). रिटर्न पाठवलं का. raise नाही.
    setting = True (dashboard `engine3_*` setting error, engine3_live.SettingError) ⇒ "setting error — fix it on the dashboard"."""
    p, sym = _alert_path(state_path), str(symbol).upper()
    now = _naive(now or now_ist())
    st = _alert_state(p)
    cur = st.get(sym) or {}
    action = "fix the setting on the dashboard" if setting else "no action needed, it retries on its own"
    from atp_private.trade_engine.bots_common import error_once as EO
    what = str(msg).strip().splitlines()[0][:120] if str(msg).strip() else "error"
    sent = EO.send_once(EO.cause_key(msg), f"⚠️ Engine {sym}: {what} — {action}", send=send, state_path=_once_path(p), now=now)
    st[sym] = {"failing": True, "since": cur.get("since") or str(now), "last_sent": str(now)}
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(st, open(p, "w", encoding="utf-8"))
    except OSError:
        pass
    return sent


def alert_data_problem(symbol, msg="data problem: FUT volume missing", send=None, state_path=None, now=None):
    """Abhi Z-1c: data problem (NIFTY / BANKNIFTY FUT volume missing) ⇒ एक Telegram ओळ, symbol प्रमाणे दिवसातून जास्तीत जास्त एकदा
    (त्याच alert state file मध्ये). Entry आधीच नाही (caller). रिटर्न पाठवलं का. raise नाही. दिवस "sent" म्हणून फक्त send यशस्वी झाला
    तरच नोंदवतो (send raise / False ⇒ पुढच्या cycle ला पुन्हा प्रयत्न)."""
    p, sym = _alert_path(state_path), str(symbol).upper()
    day = str(_naive(now or now_ist()).date())
    st = _alert_state(p)
    seen = st.setdefault("_data_problem", {})
    if seen.get(sym) == day:
        return False
    line = f"⚠️ Engine {sym}: {str(msg)[:160]} ⇒ no engine entry for {sym} (exits unaffected)"
    try:
        if send is None:
            from atp_private.trade_engine.notifications import send_telegram_message as send
        ok = send(line) is not False                                     # notifications ⇒ False on failure; raise ⇒ failure
    except Exception as exc:                                             # noqa: BLE001
        print(f"{line}  [Telegram send failed: {type(exc).__name__}]")
        ok = False
    if not ok:
        return False
    seen[sym] = day
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(st, open(p, "w", encoding="utf-8"))
    except OSError:
        pass
    return True


def delay_minutes(bar_end, computed_at):
    """V6 delay guard: whole minutes between a bar's close and the moment its row was decided (computed_at). None if unparsable."""
    try:
        return (_naive(computed_at) - _naive(bar_end)).total_seconds() / 60.0
    except (ValueError, TypeError):
        return None


def alert_engine_delay(symbol, bar_end, computed_at=None, limit_min=None, send=None, state_path=None, now=None, tf="5M"):
    """V6 delay guard: a row decided more than `engine_delay_alert_min` (default 5) minutes after its bar close => ONE Telegram notice
    per day (same alert state file; the day is recorded only after a successful send) and a log line every time. Returns True if sent.
    Never raises; exits are unaffected."""
    try:
        lim = float(DEFAULTS["engine_delay_alert_min"] if limit_min is None else limit_min)
        mins = delay_minutes(bar_end, computed_at or now or now_ist())
        if mins is None or mins <= lim:
            return False
        sym = str(symbol).upper()
        line = (f"⚠️ Engine delay: {sym} {tf} bar {pd.Timestamp(bar_end):%H:%M} decided {mins:.0f} min after its close "
                f"(limit {lim:g} min). Cards may be late; exits unaffected.")
        print(line)
        p = _alert_path(state_path)
        day = str(_naive(now or now_ist()).date())
        st = _alert_state(p)
        if st.get("_engine_delay") == day:
            return False
        try:
            if send is None:
                from atp_private.trade_engine.notifications import send_telegram_message as send
            ok = send(line) is not False
        except Exception as exc:                                         # noqa: BLE001
            print(f"[Telegram send failed: {type(exc).__name__}]")
            ok = False
        if not ok:
            return False
        st["_engine_delay"] = day
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            json.dump(st, open(p, "w", encoding="utf-8"))
        except OSError:
            pass
        return True
    except Exception as exc:                                             # noqa: BLE001 — a guard never stops the run
        print(f"⚠️ engine delay check failed: {type(exc).__name__}: {exc}")
        return False


WATCH_WHY_MR = {"no_handover": "no handover seen", "absorption": "absorption (the area is being absorbed)",
                "no_commitment": "no commitment candle", "ltf_missing": "no lower-timeframe data",
                "ltf_against": "lower timeframe still against", "ltf_pending": "no lower-timeframe CHoCH yet",
                "not_dominant": "commitment candle not dominant", "low_volume": "commitment volume low",
                "no_volume_reference": "volume cannot be compared", "data_problem": "data problem", "doji": "doji — next candle",
                "inside": "inside bar — next candle", "pullback": "candle still in the pullback direction"}


def watch_text(symbol, w):
    """EN1 / M53 (INFO tier): one plain line for a WATCH (a model fired without the full required set — no card, no position)."""
    side = "bear call" if int(w.get("direction") or 0) < 0 else "bull put"
    why = str(w.get("watch_why") or "")
    piece = next((mr for k, mr in WATCH_WHY_MR.items() if k in why), None)
    if piece is None:
        piece = "already entered here in this visit (one entry per cluster)" if "EN3" in why else (why[:120] or "required set incomplete")
    a = w.get("area") or {}
    where = f" · area {float(a['lo']):,.0f}–{float(a['hi']):,.0f}" if a.get("lo") is not None and a.get("hi") is not None else ""
    return (f"ℹ️ WATCH · {str(symbol).upper()} {side} ({w.get('name') or w.get('model')}){where}\n"
            f"No entry: {piece}\nAction: none (no card / position; entry only when the full set is there)")


def alert_watch(symbol, watches, send=None, state_path=None, now=None):
    """EN1 (DECISIONS 118 / 119) via the M53 INFO tier: each NEW watch alert (symbol · visit · model) ⇒ one Telegram line, at most once a
    day per key (the alert state file). Returns the count sent; never raises (alerts never stop the run)."""
    p, sym = _alert_path(state_path), str(symbol).upper()
    day = str(_naive(now or now_ist()).date())
    st = _alert_state(p)
    seen = st.setdefault("_watch", {})
    if seen.get("_day") != day:
        seen.clear()
        seen["_day"] = day
    n = 0
    for w in watches or ():
        key = f"{sym}|{w.get('visit_id')}|{w.get('model')}"
        if key in seen:
            continue
        line = watch_text(sym, w)
        try:
            if send is None:
                from atp_private.trade_engine.notifications import send_telegram_message
                send = lambda m: send_telegram_message(m, silent=True)   # noqa: E731 — INFO tier: no sound
            ok = send(line) is not False
        except Exception as exc:                                         # noqa: BLE001
            print(f"{line}  [Telegram send failed: {type(exc).__name__}]")
            ok = False
        if ok:
            seen[key] = True
            n += 1
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(st, open(p, "w", encoding="utf-8"))
    except OSError:
        pass
    return n


def alert_heartbeat(symbols, send=None, state_path=None, now=None):
    """M53 MS-6: one quiet "bot alive" line a day, after the day's first cycle in which every symbol ran — so "no message" means "no
    events", and a missing heartbeat means the pipeline is broken. Silent (INFO). Returns whether it was sent; never raises."""
    p = _alert_path(state_path)
    now = _naive(now or now_ist())
    day = str(now.date())
    st = _alert_state(p)
    if st.get("_heartbeat") == day:
        return False
    # N10: kept as is — golden tests/test_decision3_flip.py and STABLE test_decision3_zone_answers.py filter this line by its
    # "🟢 Bot चालू" prefix; changing it needs Abhi's OK on a golden-test change (OPEN_QUESTIONS). English after that.
    line = (f"🟢 Bot चालू · {' / '.join(str(x).upper() for x in symbols)} · PAPER · engine data OK ({now:%H:%M}). "
            "आज पुढे संदेश नसेल तर = काही घडलं नाही.")
    try:
        if send is None:
            from atp_private.trade_engine.notifications import send_telegram_message
            send = lambda m: send_telegram_message(m, silent=True)       # noqa: E731
        ok = send(line) is not False
    except Exception as exc:                                             # noqa: BLE001
        print(f"{line}  [Telegram send failed: {type(exc).__name__}]")
        ok = False
    if ok:
        st["_heartbeat"] = day
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            json.dump(st, open(p, "w", encoding="utf-8"))
        except OSError:
            pass
    return ok


def watch_brief(w):
    """The JSON-safe part of a WATCH record (no internal `_` keys)."""
    a = w.get("area") or {}
    return {"model": w.get("model"), "name": w.get("name"), "direction": w.get("direction"), "visit_id": w.get("visit_id"),
            "watch_why": w.get("watch_why"), "area": {k: a.get(k) for k in ("id", "lo", "hi", "role")}}


def alert_recovered(symbol, send=None, state_path=None, now=None):
    """आधी अपयशी होता आणि आता चालला ⇒ एक "recovered" ओळ (एकदाच). रिटर्न पाठवलं का."""
    p, sym = _alert_path(state_path), str(symbol).upper()
    st = _alert_state(p)
    cur = st.get(sym) or {}
    if not cur.get("failing"):
        return False
    _alert_send(f"✅ Engine {sym} recovered (failing since {pd.Timestamp(cur.get('since')):%H:%M}) — engine setups resume", send)
    st[sym] = {"failing": False}
    try:
        json.dump(st, open(p, "w", encoding="utf-8"))
    except OSError:
        pass
    return True


TOKEN_REJECTED_LINE = "⚠️ Upstox token rejected — no new entries (exits unaffected) — log in again to refresh the token"
TOKEN_RESTORED_LINE = "✅ Upstox token restored — engine running again."
TOKEN_CAUSE = "token_rejected"


def token_check(token):
    """Run सुरुवातीची authenticated तपासणी (engine3_live.profile_check): "ok" / "rejected (…)" / "unknown (…)". raise नाही."""
    import atp_private.trade_engine.engine3_live as L
    return L.profile_check(token)


def _send_ok(line, send):
    try:
        if send is None:
            from atp_private.trade_engine.notifications import send_telegram_message as send
        return send(line) is not False                                   # notifications ⇒ False on failure; raise ⇒ failure
    except Exception as exc:                                             # noqa: BLE001
        print(f"{line}  [Telegram send failed: {type(exc).__name__}]")
        return False


def _alert_save(st, p):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(st, open(p, "w", encoding="utf-8"))
    except OSError:
        pass


def _token_state(st):
    cur = st.get("_token")
    return cur if isinstance(cur, dict) else {}


def alert_token_rejected(send=None, state_path=None, now=None, detail=None):
    """N9 (30 Oct): Upstox rejected the token ⇒ TOKEN_REJECTED_LINE once per day (not every 15M bar); one restored line when it works
    again. One token, not per symbol. Returns whether it was sent."""
    from atp_private.trade_engine.bots_common import error_once as EO
    line = TOKEN_REJECTED_LINE
    if "HTTP 403" in str(detail or ""):                                  # 403 = rejected token or permission / IP
        line += " [HTTP 403]"
    return EO.send_once(TOKEN_CAUSE, line, send=send, state_path=_once_path(_alert_path(state_path)), now=_naive(now or now_ist()))


def alert_token_restored(send=None, state_path=None, now=None):
    """Token was rejected earlier and the check passes now => ONE TOKEN_RESTORED_LINE (never without a prior rejection)."""
    from atp_private.trade_engine.bots_common import error_once as EO
    return EO.send_restored(TOKEN_CAUSE, TOKEN_RESTORED_LINE, send=send, state_path=_once_path(_alert_path(state_path)))


ENGINE3_SETTINGS_KEY = "15m_dynamic_sr"                                     # one bot (bots_common.one_bot.ON_KEY): engine3_* settings याच पानावर


def engine3_settings(symbol, settings_fn=None):
    """Dashboard (15M SRv2 पान, symbol प्रमाणे) चे `engine3_*` settings (उदा. `engine3_use_1m`, Abhi Z-1o). वाचता आलं नाही ⇒ {} ⇒
    engine3_live.DEFAULTS (default True). कधीच raise नाही."""
    try:
        if settings_fn is None:
            import atp_private.trade_engine.cloud_db as cloud_db
            settings_fn = cloud_db.get_strategy_settings
        st = settings_fn(ENGINE3_SETTINGS_KEY, str(symbol).upper()) or {}
        return {k: v for k, v in dict(st).items() if str(k).startswith("engine3_") or k in WINDOW_KEYS}   # M56 O6: + the store window
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.engine3_settings {symbol}: {type(exc).__name__}: {exc} ⇒ defaults")
        return {}


def run3(symbol, access_token, feed=None, path=None, now=None, s=None, dry_run=False):
    """decision3 (V22) चा एक service cycle: शेवटच्या **बंद** bar चा निर्णय ⇒ store. रिटर्न row (+ "skipped" कारण, असल्यास).
    DECISIONS 37 (`engine3_trigger_tf`, default 5M): the last closed 5M candle + the catch-up of every unstored closed 5M candle of the
    session (since = `last_stored`), each stored when inside the store window; row["caught_up"] = the earlier bar_ts stored. 15M (what-if)
    = today's cycle (the last closed 15M bar), unchanged.
    Data नाही / अपूर्ण / exception ⇒ raise (caller: error row + Telegram ओळ). dry_run ⇒ store मध्ये लिहीत नाही."""
    import atp_private.trade_engine.engine3_live as L
    now = _naive(now or now_ist())
    if feed is None:
        L.prune_cache((s or {}).get("engine3_cache_keep_days"))           # जुन्या cache files (hist_ / fold_) — एक listdir, स्वस्त
        feed = L.UpstoxFeed(access_token, now.date())
        feed.cache = L.history_cache_on(s)                               # M56 O1 (D3): prior days once a day (disk), intraday each cycle
    tf = L.trigger_tf_of(s)
    prev = prev_trigger_bar(symbol, now, path)                          # M56 E3: the stored bar, compared with this fetch
    pk = {"prev_bar": prev} if prev is not None else {}
    if tf != "5M":                                                       # trigger_tf 15M (what-if): today's cycle, unchanged
        r = L.compute(str(symbol).upper(), feed, now, s, **pk)
        row = L.row_from_v22(symbol, r, now_ist)
        if pd.Timestamp(row["bar_ts"]) > now:
            raise ValueError("the last 15M candle is not closed yet")
        if not in_window(row["bar_ts"], s) or pd.Timestamp(row["bar_ts"]).normalize() != now.normalize():
            row["skipped"] = f"bar {pd.Timestamp(row['bar_ts']):%Y%m%d %H:%M} entry window ({_win(s)[0]}–" \
                             f"{_win(s)[1]}, today) outside ⇒ not stored"
            return row
        if not dry_run:
            save(row, path)
        row["watch_alerts_new"] = [watch_brief(w) for w in (r.get("watch_alerts") or [])]
        return row
    # DECISIONS 37: the 5M close + catch-up — every closed 5M candle of the session after the last stored row is decided, in order
    r = L.compute(str(symbol).upper(), feed, now, s, since=last_stored(symbol, now, path), **pk)
    computed = (r.pop("catch_up", None) or []) + [r]
    watches = [watch_brief(w) for x in computed for w in (x.get("watch_alerts") or [])]   # EN1 WATCH (M53 INFO tier, caller)
    rows = [L.row_from_v22(symbol, x, now_ist) for x in computed]
    stored = []
    for row in rows:
        if pd.Timestamp(row["bar_ts"]) > now:
            raise ValueError("the last 5M candle is not closed yet")
        if not in_window(window_bar(row["bar_ts"], "5M"), s) or pd.Timestamp(row["bar_ts"]).normalize() != now.normalize():
            row["skipped"] = f"bar {pd.Timestamp(row['bar_ts']):%Y%m%d %H:%M} entry window ({_win(s)[0]}–" \
                             f"{_win(s)[1]}, today) outside ⇒ not stored"
            continue
        if not dry_run:
            keep_original(row, path)                                     # M56 E3 review: a re-decided bar keeps what it replaced
            save(row, path)
        stored.append(row["bar_ts"])
    last = rows[-1]
    last["caught_up"] = [x for x in stored if x != last["bar_ts"]]
    last["watch_alerts_new"] = watches
    return last


# ---------------------------------------------------------------------------------------------------------------- adapter
def latest(symbol, now=None, max_age_min=None, path=None):
    """सर्वात ताजा engine निर्णय (bar_end ≤ now, वय ≤ max_age_min). नाही ⇒ None. कधीच raise नाही."""
    try:
        now = _naive(now or now_ist())
        age = int(max_age_min if max_age_min is not None else DEFAULTS["engine_max_age_min"])
        with connect(path) as c:
            r = c.execute("SELECT * FROM engine_signals WHERE symbol=? AND bar_ts<=? ORDER BY bar_ts DESC LIMIT 1",
                          (str(symbol).upper(), str(now))).fetchone()
        if r is None:
            return None
        r = dict(r)
        if pd.Timestamp(r["bar_ts"]) < now - pd.Timedelta(minutes=age):
            return None
        return r
    except Exception as exc:
        print(f"⚠️ engine_signal.latest: {type(exc).__name__}: {exc}")
        return None


def opinion(symbol, now=None, path=None, max_age_min=None):
    """Caption साठी shadow मत: "engine: setup ↑ bull put (grade B) · …" / "engine: wait — G-A: I नाही" / "engine: NA (…)"."""
    r = latest(symbol, now, max_age_min, path)
    if r is None:
        return "engine: unavailable (no fresh engine decision)"
    hm = pd.Timestamp(r["bar_ts"]).strftime("%H:%M")
    ents = [e for e in (row_payload(r).get("entries") or []) if entry_ok(e)] if r["decision"] == "setup" else []
    if ents:                                                             # entry models (H1 rows): each fired model, its side
        return f"engine ({hm}): setup · " + ", ".join(f"{str(e['model']).upper()} {'↑' if int(e['direction']) > 0 else '↓'} "
                                                       f"{SIDE_TXT[int(e['direction'])]}" for e in ents)
    if r["decision"] == "setup" and r["direction"] in (1, -1):
        arrow = "↑" if r["direction"] > 0 else "↓"
        lv = f" · area {r['level_lo']:,.0f}–{r['level_hi']:,.0f}" if r.get("level_lo") is not None else ""
        return f"engine ({hm}): setup {arrow} {SIDE_TXT[r['direction']]} · grade {r.get('grade') or '—'}{lv}"
    return f"engine ({hm}): {r.get('decision') or 'wait'} — {r.get('gate') or ''}: {r.get('reason') or ''}".strip()


def own_allowed(symbol, direction, settings, now=None, path=None, key="signal_source"):
    """bot चा स्वतःचा signal वापरायचा का (signal_source नुसार). रिटर्न (ok, कारण)."""
    src = source_of(settings, key)
    if src == "own":
        return True, "signal_source = own"
    if src == "engine":
        return False, "signal_source = engine ⇒ the bot's own signal is not used"
    r = latest(symbol, now, (settings or {}).get("engine_max_age_min"), path)
    want = 1 if str(direction).upper() == "BULLISH" else -1
    if r is None or r["decision"] != "setup":
        return False, f"signal_source = both ⇒ no engine setup ({'NA' if r is None else (r.get('gate') or r.get('decision'))})"
    ents = [int(e["direction"]) for e in (row_payload(r).get("entries") or []) if entry_ok(e)]
    if ents:                                                             # entry models (H1 rows): any fired model on that side agrees
        return (True, "signal_source = both ⇒ engine agrees") if want in ents else \
            (False, f"signal_source = both ⇒ engine entries {'/'.join(DIR_TXT[x] for x in sorted(set(ents)))} ≠ {direction}")
    if r["direction"] != want:
        return False, f"signal_source = both ⇒ engine direction {DIR_TXT.get(r['direction'], '?')} ≠ {direction}"
    return True, "signal_source = both ⇒ engine agrees"


def pending_entry(bot, symbol, settings, now=None, path=None):
    """signal_source = engine: या bot ने अजून न वापरलेला ताजा engine setup. नाही ⇒ None.
    ताजा = bar_ts ≥ now − engine_max_age_min. सर्वात नवा setup (त्यानंतरचा "wait" / "error" bar तो रद्द करत नाही — Abhi च्या ✅ ची वाट
    चालू असताना पुढचा 15M bar आला / data त्रुटी आली तरी तोच setup; Vision gate / ✅ हाच अंतिम तपास). "error" row कधीच setup नाही ⇒
    नवा entry नाही (fail-closed). नवा setup ⇒ जुना बाद. सर्वात नवा setup आधीच वापरला ⇒ None."""
    if source_of(settings) != "engine":
        return None
    try:
        now = _naive(now or now_ist())
        age = int((settings or {}).get("engine_max_age_min") or DEFAULTS["engine_max_age_min"])
        with connect(path) as c:
            rows = [dict(x) for x in c.execute("SELECT * FROM engine_signals WHERE symbol=? AND bar_ts<=? AND bar_ts>=? ORDER BY bar_ts DESC",
                                                (str(symbol).upper(), str(now), str(now - pd.Timedelta(minutes=age)))).fetchall()]
            r = next((x for x in rows if x["decision"] == "setup"), None)
            if r is None or r["direction"] not in (1, -1):
                return None
            done = c.execute("SELECT status FROM engine_consumed WHERE bot=? AND symbol=? AND bar_ts=?",
                             (bot, str(symbol).upper(), r["bar_ts"])).fetchone()
    except Exception:
        return None
    return None if done else r


def mark_consumed(bot, symbol, bar_ts, status, path=None):
    try:
        with connect(path) as c:
            c.execute("INSERT OR REPLACE INTO engine_consumed (bot, symbol, bar_ts, status, at) VALUES (?,?,?,?,?)",
                      (bot, str(symbol).upper(), str(bar_ts), str(status), str(now_ist())))
    except Exception as exc:
        print(f"⚠️ engine_signal.mark_consumed: {exc}")


# ---------------------------------------------------------------------------------------------------------------- entry models (E1–E4)
# decision3 (H1) rows carry payload `entries`: the entry models that fired on that bar, each {model "E1".."E4", name, direction, side, area,
# visit_id, trigger_ts, entry_ref, invalidation, evidence, label}. Each one is its own signal: Vision gate + ✅ ⇒ its own PAPER position.
# Idempotency: (bot, symbol, visit_id, model) in `engine_entry_consumed` (this SQLite, survives restarts) ⇒ at most once per visit per model.
# A window without any `entries` key (older engine rows) ⇒ None ⇒ the caller keeps today's single-setup path (`pending_entry`).
MODELS = ("E1", "E2", "E3", "E4")
MODEL_NAMES = {"E1": "Aggressive", "E2": "Confirmation", "E3": "Structure", "E4": "Sweep-retest"}


def row_payload(r):
    """Engine row ⇒ payload dict ({} when unreadable). Never raises."""
    try:
        p = json.loads((r or {}).get("payload") or "{}")
    except (TypeError, ValueError):
        return {}
    return p if isinstance(p, dict) else {}


def entry_ok(e):
    """A usable entry: model E1–E4, direction ±1, a visit_id. Anything else is ignored (never guessed)."""
    try:
        return (isinstance(e, dict) and str(e.get("model") or "").upper() in MODELS and int(e.get("direction")) in (1, -1)
                and str(e.get("visit_id") or "").strip() != "")
    except (TypeError, ValueError):
        return False


def model_label(e):
    """{"model": "E1", "name": "Aggressive"} ⇒ "E1 — Aggressive" (no name ⇒ the model's own name)."""
    m = str((e or {}).get("model") or "").upper()
    name = str((e or {}).get("name") or "").strip() or MODEL_NAMES.get(m, "")
    lab = f"{m} — {name}" if name else m
    if (e or {}).get("also_fired"):                                      # C6: the other models on the same candle (their own cards)
        lab += " · also on this candle: " + ", ".join(str(x) for x in e["also_fired"]) + " (own card)"
    if (e or {}).get("same_place"):                                      # M54 V-3: EN3 — the same place, one card: extra evidence
        lab += (" · also on this candle: " if "also on this candle" not in lab else " · ") + ", ".join(str(x) for x in e["same_place"]) \
            + " at the same place (extra evidence on this card — one entry per place per visit)"
    try:                                                                 # M56 E8 (DECISIONS 58 kept, no grade): the evidence count
        from atp_private.trade_engine.decision3 import method as M3                               # and names on the card line — information only
        ew = M3.evidence_words((e or {}).get("evidence_list"))
    except Exception:                                                    # noqa: BLE001 — display only
        ew = ""
    if ew:
        lab += f" · {ew}"
    if str((e or {}).get("family") or "").upper() == "C":                # model C (DECISIONS 32): "C · E2 — Confirmation (C-a)"
        sub = str((e or {}).get("sub_model") or "").strip()
        return f"C · {lab}" + (f" ({sub})" if sub else "")
    return lab


def pending_entries(bot, symbol, settings, now=None, path=None, fresh_min=None):
    """signal_source = engine: fresh entry-model entries (bar_ts ≥ now − engine_max_age_min) this bot has not consumed for their
    (visit_id, model) ⇒ [(row, entry)], freshest bar first. A later "wait" / "error" bar does not cancel an entry (the Vision gate / ✅
    is the final check — same as `pending_entry`). None ⇒ no row in the window carries `entries` (older engine) ⇒ legacy path. Store
    error ⇒ [] (fail closed: no entry, never the legacy path).
    M56 E2 (A9): fresh_min (the N18 `card_fresh_min`, minutes after the trigger close; None / ≤ 0 ⇒ only engine_max_age_min) ⇒ an
    entry older than it that this bot never took to the gate (`mark_seen`) comes back marked e["stale"] (the caller consumes it: no
    card, no position); one taken to the gate while fresh stays pending (its card / ✅ / exec window decides, as today)."""
    if source_of(settings) != "engine":
        return None
    sym = str(symbol).upper()
    try:
        now = _naive(now or now_ist())
        age = int((settings or {}).get("engine_max_age_min") or DEFAULTS["engine_max_age_min"])
        fresh = pd.Timedelta(minutes=float(fresh_min)) if fresh_min is not None and float(fresh_min) > 0 else None   # M56 E2 (A9)
        out, seen, models = [], set(), False
        with connect(path) as c:
            rows = [dict(x) for x in c.execute("SELECT * FROM engine_signals WHERE symbol=? AND bar_ts<=? AND bar_ts>=? ORDER BY bar_ts DESC",
                                                (sym, str(now), str(now - pd.Timedelta(minutes=age)))).fetchall()]
            for x in rows:
                if x["decision"] == ERROR:
                    continue
                pay = row_payload(x)
                if "entries" not in pay:
                    continue
                models = True
                same = {}                                                # C6 (28 Oct): the models firing on the SAME trigger candle of
                for e in pay.get("entries") or []:                       # a visit — each keeps its own card (each model once per visit),
                    if entry_ok(e) and e.get("trigger_ts"):              # and each card names the others
                        same.setdefault((str(e["visit_id"]), str(e.get("trigger_ts"))), []).append(str(e["model"]).upper())
                for e in pay.get("entries") or []:
                    if not entry_ok(e):
                        continue
                    k = (str(e["visit_id"]), str(e["model"]).upper())
                    if k in seen:
                        continue
                    seen.add(k)
                    if c.execute("SELECT 1 FROM engine_entry_consumed WHERE bot=? AND symbol=? AND visit_id=? AND model=?",
                                 (bot, sym, k[0], k[1])).fetchone() is None:
                        sib = [m for m in same.get((k[0], str(e.get("trigger_ts"))), []) if m != k[1]] if e.get("trigger_ts") else []
                        ent = {**e, "visit_id": k[0], "model": k[1], "direction": int(e["direction"]), **({"also_fired": sib} if sib else {})}
                        if fresh and now - pd.Timestamp(x["bar_ts"]) > fresh and c.execute(
                                "SELECT 1 FROM engine_entry_seen WHERE bot=? AND symbol=? AND visit_id=? AND model=?",
                                (bot, sym, k[0], k[1])).fetchone() is None:
                            ent["stale"] = (f"{(now - pd.Timestamp(x['bar_ts'])).total_seconds() / 60:.0f} min after the trigger close "
                                            f"(fresh ≤ {fresh.total_seconds() / 60:g} min, N18)")
                        out.append((x, ent))
    except Exception as exc:                                             # noqa: BLE001 — fail closed
        print(f"⚠️ engine_signal.pending_entries: {type(exc).__name__}: {exc}")
        from atp_private.trade_engine.bots_common import gate_alert as GA                         # DECISIONS 47: one ⚠️ per cause per day (never blocks)
        GA.alert("engine_store", symbol, f"{type(exc).__name__}: {exc}")
        return []
    return out if models else None


def mark_seen(bot, symbol, visit_id, model, path=None):
    """M56 E2 (A9): this bot takes the entry (visit, model) to the gate now (its first time is kept) — from then on the N18
    freshness never makes it stale. Never raises."""
    try:
        with connect(path) as c:
            c.execute("INSERT OR IGNORE INTO engine_entry_seen (bot, symbol, visit_id, model, at) VALUES (?,?,?,?,?)",
                      (bot, str(symbol).upper(), str(visit_id), str(model).upper(), str(now_ist())))
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.mark_seen: {type(exc).__name__}: {exc}")


def consume_siblings(bot, symbol, row, entered, path=None):
    """M56 E2 (A2): the bot opened a position from `entered` ⇒ its un-entered SIBLINGS — entries of the SAME engine row (the same
    trigger bar), the same direction, tied to it by place (`place`, a line / area at one price) or by cluster, in another visit — that
    this bot has not consumed are consumed now ("SKIPPED_SIBLING_ENTERED", no zone ⇒ never a zone hit): they never wait as pending
    entries for after this position. Every other entry (another place) is untouched; the other models of the SAME visit keep their own
    cards (C6, 28 Oct); another family (model C) is its own reader. Returns the consumed (visit_id, model) list. Never raises; never
    touches exits."""
    out = []
    try:
        for e in row_payload(row).get("entries") or []:
            if not entry_ok(e):
                continue
            k = (str(e["visit_id"]), str(e["model"]).upper())
            if k[0] == str(entered["visit_id"]):                          # the same visit (place) ⇒ C6: its own card
                continue
            if str(e.get("family") or "").upper() != str(entered.get("family") or "").upper():   # model C is its own reader
                continue
            if int(e.get("direction") or 0) != int(entered.get("direction") or 0):
                continue
            cid = lambda x: (x.get("cluster") or {}).get("id") if isinstance(x.get("cluster"), dict) else None   # noqa: E731
            tied = (e.get("place") and e.get("place") == entered.get("place")) or (cid(e) and cid(e) == cid(entered))
            if not tied:                                                 # another place ⇒ not a sibling
                continue
            if claim_entry(bot, symbol, k[0], k[1], "SKIPPED_SIBLING_ENTERED", row.get("bar_ts"), path):
                out.append(k)
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.consume_siblings: {type(exc).__name__}: {exc}")
    return out


def entry_status(bot, symbol, visit_id, model, path=None):
    """(bot, symbol, visit_id, model) ची नोंद (status) किंवा None. त्रुटी ⇒ "ERROR" (fail closed: consumed मानतो)."""
    try:
        with connect(path) as c:
            r = c.execute("SELECT status FROM engine_entry_consumed WHERE bot=? AND symbol=? AND visit_id=? AND model=?",
                          (bot, str(symbol).upper(), str(visit_id), str(model).upper())).fetchone()
        return r["status"] if r else None
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.entry_status: {exc}")
        return "ERROR"


def claim_entry(bot, symbol, visit_id, model, status, bar_ts=None, path=None, zone=None):
    """Idempotency: the first claim of (bot, symbol, visit_id, model) wins (INSERT OR IGNORE, persisted) ⇒ True; already there ⇒ False.
    zone = (direction, lo, hi) of the entry's area / cluster (`zone_entries_today` counts by it). Store error ⇒ False (fail closed: no
    position). Never raises."""
    try:
        dz, lo, hi = zone if zone else (None, None, None)
        with connect(path) as c:
            cur = c.execute("INSERT OR IGNORE INTO engine_entry_consumed (bot, symbol, visit_id, model, status, bar_ts, at, direction, lo, hi) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (bot, str(symbol).upper(), str(visit_id), str(model).upper(), str(status), None if bar_ts is None else str(bar_ts),
                             str(now_ist()), None if dz is None else int(dz), None if lo is None else float(lo),
                             None if hi is None else float(hi)))
            return cur.rowcount == 1
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.claim_entry: {exc}")
        return False


def set_entry_status(bot, symbol, visit_id, model, status, path=None):
    """Claimed entry ⇒ its final status (EXECUTED / OPEN_FAILED …). Never raises."""
    try:
        with connect(path) as c:
            c.execute("UPDATE engine_entry_consumed SET status=?, at=? WHERE bot=? AND symbol=? AND visit_id=? AND model=?",
                      (str(status)[:200], str(now_ist()), bot, str(symbol).upper(), str(visit_id), str(model).upper()))
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.set_entry_status: {exc}")


def zone_entries_today(bot, symbol, day, direction, lo, hi, path=None):
    """The dashboard execution setting `max_hits_per_zone`, applied to engine entries exactly as the touch paths apply it
    (`cloud_db.get_zone_hits_today`: today's real entry attempts on the same zone and role — every SKIPPED_* / not-entered row left out):
    today's engine entries of this bot / symbol (claims ENTERING / EXECUTED / OPEN_FAILED — a trade attempt) on the same side (role) whose
    area / cluster band overlaps [lo, hi]. day = "YYYY-MM-DD" (the entry bar's day). Store error ⇒ None (the caller enters nothing this
    cycle, consumes nothing). Never raises."""
    try:
        lo, hi = sorted((float(lo), float(hi)))
        with connect(path) as c:
            rows = c.execute("SELECT status FROM engine_entry_consumed WHERE bot=? AND symbol=? AND direction=? AND lo IS NOT NULL "
                             "AND hi IS NOT NULL AND lo<=? AND hi>=? AND substr(COALESCE(bar_ts, at), 1, 10)=?",
                             (bot, str(symbol).upper(), int(direction), hi, lo, str(day)[:10])).fetchall()
        return sum(1 for r in rows if not (str(r["status"] or "").startswith(("SKIPPED_", "NOT_ENTERED_"))))
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ engine_signal.zone_entries_today: {type(exc).__name__}: {exc}")
        return None
