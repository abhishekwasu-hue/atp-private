"""vision/worker.py — QUEUED signals → chart render → vision audit → नोंद → (notify mode) Telegram. V0: trading वर परिणाम नाही.

    python3 -m vision.worker --loop-seconds 55        # cron दर मिनिटाला (ProcessLock — एका वेळी एकच worker)
    python3 -m vision.worker --usage [YYYY-MM-DD]     # त्या दिवसाचा token / $ वापर (G-COST मोजमाप)

🎓 क्रम (प्रत्येक signal):
  1. 15 मिनिटांपेक्षा जुना QUEUED/RUNNING ⇒ EXPIRED (restart / उशीर — जुनं मत उपयोगाचं नाही).
  2. तोच symbol/दिशा/TF/level `reuse_window_min` (15) मिनिटांत आधी तपासलेला ⇒ तेच मत (API call नाही, खर्च 0).
  3. 1m candles (Upstox) → signal पर्यंत कापून 2-panel chart (`vision/chart.py`).
  4. Budget: आजचा / महिन्याचा खर्च + या audit चा अंदाज > मर्यादा ⇒ vision नाही (verdict unavailable, `vision_fail_action`), Telegram इशारा दिवसातून एकदा.
  5. Model / API key नाही ⇒ unavailable (खर्च नाही).
  6. Audit (1, गरज असल्यास 2) → `vision_signals` row DONE (verdict, JSON, latency, cost) + `vision_usage`.
  7. mode = notify ⇒ Telegram वर chart + मत (बटणं नाहीत). shadow ⇒ फक्त नोंद.
"""
import argparse
import html
import json
import re
import sys
import time

import pandas as pd

from . import chart as CH
from . import config as VC
from . import decide as VD
from . import images as IM
from . import signal_audit as SA
from . import store as VS

STALE_MIN = 15
VERDICT_MR = {"agree": ("✅", "TAKE"), "gray": ("🟡", "WAIT"), "disagree": ("❌", "SKIP"), "unavailable": ("⚪", "unavailable")}
MODE_EN = VC.MODE_EN                                                     # N11: the Vision mode in plain words
DIR_MR = {"BULLISH": "Bullish", "BEARISH": "Bearish"}


def setup_kind(row):
    t = row.get("tags") or {}
    if t.get("breakout_entry"):
        return "Breakout entry"
    if t.get("directional"):
        return "Directional (IV breakout)"
    return "Reversal (touch)"


def default_fetch(symbol, need_daily=False):
    """(1m frame, daily frame|None) — Upstox. Token Supabase / .env मधून (कधीच print नाही)."""
    import atp_private.trade_engine.cloud_db as cloud_db
    from atp_private.trade_engine.upstox_api import fetch_candles
    token = cloud_db.get_effective_upstox_token(None)
    if not token:
        raise RuntimeError("no Upstox token")
    m1 = fetch_candles(token, symbol, 0, interval="1minute", lookback_days=21)          # v2: major levels (~3 आठवडे) + PWH / PWL
    from atp_private.trade_engine.decision3 import history as HI
    m1 = HI.traded_frame(m1, symbol, "1M")                               # M56 E4 (D2): levels never from an auction print
    d1 = fetch_candles(token, symbol, 0, interval="day", lookback_days=120) if need_daily else None
    return m1, d1


def default_fetch_volume(symbol):
    """Volume pane: index ⇒ त्याच्या front futures चे 1m candles (timestamp, volume) — NIFTY FUT / BANKNIFTY FUT / SENSEX FUT (resolve
    न झाल्यास NA). MCX ⇒ None (1m frame चाच स्वतःचा volume). अपयश ⇒ None ⇒ chart वर "volume: NA (grade cap B)". कधीच raise नाही."""
    try:
        from atp_private.trade_engine.decision3 import volume_pane as VP
        if not VP.is_index(symbol):
            return None
        import atp_private.trade_engine.cloud_db as cloud_db
        from atp_private.trade_engine.bots_common import level_gate_bot as LGB
        token = cloud_db.get_effective_upstox_token(None)
        if not token:
            return None
        return LGB._default_futures_candles(token, str(symbol).upper(), 1, None, VOL_LOOKBACK_DAYS)
    except Exception as exc:                                             # noqa: BLE001 — volume पूरक
        print(f"⚠️ {symbol} futures volume (chart) NA: {type(exc).__name__}")
        return None


VOL_TIMEOUT_S = 5.0                     # chart volume fetch: proposal कधीच यापेक्षा जास्त अडत नाही (timeout ⇒ NA)
VOL_LOOKBACK_DAYS = 2


def engine_volume(row):
    """Gate (level bots) ने signal सोबत दिलेले confirmation-TF bar volumes (timestamp, volume) — setup TF पेक्षा बारीक / समान TF असतील
    तरच (मोठे bars लहान chart bars मध्ये वाटता येत नाहीत). नाही ⇒ None."""
    g = (row.get("tags") or {}).get("gate") if isinstance(row.get("tags"), dict) else None
    bv = (g or {}).get("bar_volumes")
    if not bv:
        return None
    f = pd.DataFrame(bv, columns=["timestamp", "volume"])
    f["timestamp"] = pd.to_datetime(f["timestamp"])
    f["volume"] = pd.to_numeric(f["volume"], errors="coerce")
    d = f["timestamp"].diff().dropna()
    step = d[d > pd.Timedelta(0)].median() if len(d) else None
    s_tf = CH.TF_MAP.get(str(row.get("setup_tf")).upper(), (5, 15))[0]
    if step is None or pd.isna(step) or step > pd.Timedelta(minutes=int(s_tf)):
        return None
    return f


def chart_volume(row, fetch_volume_fn):
    """Volume pane चा डेटा: engine चे bar volumes (fetch नाही) नाहीतर fetch_volume_fn — कमाल VOL_TIMEOUT_S, अपयश / timeout ⇒ None (NA)."""
    ev = engine_volume(row)
    if ev is not None:
        return ev
    if fetch_volume_fn is None:
        return None
    try:
        from atp_private.trade_engine.bots_common import level_reaction as LR
        return LR.call_with_timeout(fetch_volume_fn, (row["symbol"],), VOL_TIMEOUT_S)
    except Exception as exc:                                             # noqa: BLE001 — timeout / अपयश ⇒ NA, proposal अडत नाही
        print(f"⚠️ {row.get('symbol')} chart volume NA: {type(exc).__name__}")
        return None


def fetch_expiries(symbol):
    """Weekly expiry dates (contract master) — v2 signal text साठी. अपयश ⇒ [] (कधीच raise नाही)."""
    try:
        import atp_private.trade_engine.cloud_db as cloud_db
        from atp_private.trade_engine.upstox_api import fetch_option_expiries
        token = cloud_db.get_effective_upstox_token(None)
        return list(fetch_option_expiries(token, symbol) or []) if token else []
    except Exception:
        return []


YES = {"yes": "✓", "no": "✗", "good": "✓", "middle": "~", "bad": "✗"}


def v2_lines(a, hits=None):
    """signal_check_v2 audit ⇒ caption च्या ओळी (trend, level, wave, reversal 4 टप्पे, room, false-break risk, नियम)."""
    s = [f"Trend: HTF {a.get('htf_trend')} · setup {a.get('setup_structure')} ({a.get('trend_context')})",
         f"Level: {a.get('level_kind')} · real {a.get('level_real')} · confluence {a.get('confluence')}",
         f"Wave: {a.get('wave_position')} · correction complete {a.get('correction_complete')}"
         + (f" · {html.escape(a['elliott_note'])}" if a.get("elliott_note") else ""),
         "Reversal: " + " ".join(f"{k} {YES.get(a.get('reversal_' + k), '?')}" for k in ("touch", "reclaim", "strength"))
         + f" close {YES.get(a.get('reversal_close_location'), '?')} ⇒ {a.get('reversal_valid')}"
         + (" · false-break reclaim ✓" if a.get("false_break_reclaim") == "yes" else ""),
         f"Room {a.get('room_to_next_level')} · false-break risk {a.get('false_break_risk')}"
         + (" · <b>BREAKOUT</b>" if a.get("is_breakout_entry") == "yes" else "")]
    if a.get("gap_behaviour"):                                          # v2.1
        s.append(f"Gap: {a.get('gap_behaviour')} · setup {a.get('gap_setup')} · class agrees {a.get('gap_class_agrees')} · line {a.get('line_structure')} "
                 f"({a.get('line_vs_candles')})")
    if a.get("code_overrides"):
        s.append("Code facts: " + html.escape("; ".join(a["code_overrides"])))
    if hits and (hits.get("disagree") or hits.get("gray")):
        s.append("Rules: " + ", ".join([f"❌ {x}" for x in hits.get("disagree") or []] + [f"🟡 {x}" for x in hits.get("gray") or []]))
    return s


def _row_tags(row):
    t = row.get("tags")
    if isinstance(t, dict):
        return t
    try:
        return json.loads(row.get("setup_json") or "{}").get("tags") or {}
    except (ValueError, TypeError, AttributeError):
        return {}


def plain_head(row):
    """Caption ओळ 1 (Abhi, TELEGRAM_CLEANUP 3): साधी English — कोणता index, कोणती बाजू, कुठे, आणि chart वर काय पाहायचं. Engine codes नाहीत."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    tags = _row_tags(row)
    bull = str(row.get("direction") or "").upper() == "BULLISH"
    trade = "bull put (bullish)" if bull else "bear call (bearish)"
    g = tags.get("gate") or {}
    area = [x for x in (g.get("area") or [])[:2] if x is not None]
    if len(area) == 2:                                                  # Abhi: पट्ट्याची रुंदी (pts) पट्ट्याशेजारी
        where = f"{'demand' if bull else 'supply'} area {PT.band_range(*area)}"
    elif row.get("level") is not None:
        where = f"{'support' if bull else 'resistance'} {float(row['level']):,.0f}"
    else:
        where = "the marked level"
    who = "your manual" if tags.get("manual") else "a"
    tf = str(row.get("setup_tf") or "").strip()
    from . import card_summary as CS
    ml = CS.model_label(tags)                                            # engine entry model ⇒ "<symbol> · E1 — Aggressive: …"
    if ml:                                                               # DECISIONS 41 / addition C: the signal's own symbol first, then
        ow = CS.object_words(tags, bull)                                 # the model and the object in plain words (a line is a line)
        where = ow or where
        what = "line" if ow and "line" in ow.split(",")[0] else "area"
        return (f"{row.get('symbol')} · {ml}: {who} {trade} trade at {'the ' if ow else ''}{where}" + (f" ({tf} chart)" if tf else "")
                + f". Look at the {what} and the last candle: did {'buyers' if bull else 'sellers'} really take over there?")
    return (f"{row.get('symbol')}: {who} {trade} trade at {where}" + (f" ({tf} chart)" if tf else "") + ". Look at the area and the last "
            f"candle: did {'buyers' if bull else 'sellers'} really take over there?")


def _body(row, res, mode, reused=False):
    """जुना caption (engine / Vision तपशील) — आता "── details ──" खाली."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    e, mr = VERDICT_MR.get(res.get("verdict") or "unavailable", ("⚪", res.get("verdict")))
    ts = pd.Timestamp(row["signal_ts"])
    ga = [x for x in ((_row_tags(row).get("gate") or {}).get("area") or [])[:2] if x is not None]   # engine / gate पट्टा (TA4) असेल तर तोच
    tags = _row_tags(row)
    eng = bool(tags.get("engine"))
    if eng:                                                              # addition D / DECISIONS 41: the signal's own symbol first, the
        import atp_private.trade_engine.engine_signal as ES                                       # engine's name only as a small label
        bl = ES.display_label(str(row.get("bot_label") or row["bot"]), True)
        head = f"👁 <b>{html.escape(str(row['symbol']))}</b> · <b>Vision — info only</b> · <i>{html.escape(bl)}</i>"
    else:
        head = f"👁 <b>Vision — info only</b> · {html.escape(str(row.get('bot_label') or row['bot']))}"
    from . import card_summary as CS
    ow = CS.object_words(tags, str(row.get("direction") or "").upper() == "BULLISH") if eng else None
    s = [head,
         f"{row['symbol']} · {DIR_MR.get(str(row.get('direction')).upper(), row.get('direction'))} · {setup_kind(row)}",
         f"{html.escape(ow[0].upper() + ow[1:])} · signal {ts:%H:%M}" if ow else
         f"Area {PT.band_range(*ga)} ({row.get('role')}, {_area_tf_of(row, eng)}) · signal {ts:%H:%M}" if len(ga) == 2
         else f"Level {float(row['level']):,.0f} ({row.get('role')}, {row.get('setup_tf')}) · signal {ts:%H:%M}" if row.get("level") is not None
         else f"signal {ts:%H:%M}",
         f"Vision says: {e} <b>{mr}</b>" + (f" (confidence {res['confidence'] * 100:.0f}%)" if res.get("confidence") is not None else "")
         + (" · same view as a moment ago" if reused else "")]
    tl = CS.trigger_line(tags) if eng else ""
    if tl:                                                               # DECISIONS 37: the 5M trigger candle in plain words
        s.insert(3, html.escape(tl))
    a = (res.get("audits") or [None])[0]
    if a:
        if a.get("reason"):
            s.append("<b>Reason:</b> " + html.escape(a["reason"]))
        if "level_kind" in a:                                           # signal_check_v2
            s += v2_lines(a, (res.get("rule_hits") or [None])[0])
        elif a.get("engine_check"):                                     # T-5: engine signal — the method's checklist (vision/engine_audit)
            from . import engine_audit as EA
            s += EA.caption_lines(a, (res.get("rule_hits") or [None])[0])
        else:
            s.append(f"level {a.get('level_real')} · trend {a.get('trend_context')} · reversal {a.get('reversal_valid')} · "
                     f"breakout {a.get('is_breakout_entry')} · false-break {a.get('false_break_risk')}")
        if a.get("elliott_note") and "level_kind" not in a:
            s.append("Elliott: " + html.escape(a["elliott_note"]))
        if len(res.get("audits") or []) > 1:
            s.append("Second check: " + " / ".join(res.get("verdicts") or []))
    elif res.get("error"):
        s.append("Reason: " + html.escape(str(res["error"])[:160]))
    s.append("The bot decided as usual — Vision does not change the trade.")
    return "\n".join(s)                                                 # कापणी callers (_fit, ओळी-निहाय) करतात


def _area_tf_of(row, eng):
    """The details line's area TF: an engine entry model ⇒ the area's own TF (1H / Daily, card_summary._area_tf); every other signal ⇒
    the setup TF (today's card, byte for byte)."""
    if not eng or not _row_tags(row).get("entry_model"):
        return row.get("setup_tf")
    try:
        from . import card_summary as CS
        g = _row_tags(row).get("gate") or {}
        return CS._area_tf(row, g, CS._area(row, g)) or row.get("setup_tf")
    except Exception:                                                    # noqa: BLE001 — display only
        return row.get("setup_tf")


def band_flag_line(row):
    """Abhi: gate पट्टा `approval_band_warn_pts` (tags["gate"]["band_warn_pts"], नाही ⇒ default 150) पेक्षा रुंद ⇒ "⚠️ merged band — check
    (width N pts > 150)" — वरच्या साध्या भागात, निर्णय ओळीनंतर. पट्टा नाही / ठीक ⇒ "". फक्त दाखवणं (निर्णय / gate / order ला हात नाही)."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    try:
        g = _row_tags(row).get("gate") or {}
        area = [x for x in (g.get("area") or [])[:2] if x is not None]
        return PT.band_flag(*area, g.get("band_warn_pts"), g.get("band_warn_rule"),        # layer 6b: approval_band_warn_rule
                            engine_area=g.get("mode") == "engine") if len(area) == 2 else ""   # (default method, DECISIONS 53)
    except Exception:                                                    # noqa: BLE001 — फक्त माहिती, caption कधीच अडत नाही
        return ""


def summary_top(row, res, status, flag, **kw):
    """`approval_card_layout = summary` ⇒ the five summary lines + band line + SEP (vision/card_summary.py). Any error ⇒ None ⇒ the
    caller keeps today's classic top (display never breaks a card)."""
    try:
        from . import card_summary as CS
        return CS.top(row, res, status, flag, **kw)
    except Exception as exc:                                             # noqa: BLE001 — display only
        print(f"⚠️ summary card (classic used): {type(exc).__name__}: {str(exc)[:120]}")
        return None


def caption(row, res, mode, reused=False, layout=None):
    """V0 (फक्त माहिती): साधी ओळ + "Decision needed: none" (+ merged band ओळ) + ── details ── + जुना तपशील (≤ 1024).
    layout (setting `approval_card_layout`) "summary" ⇒ the summary lines replace the two plain lines; details unchanged."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    from . import card_summary as CS
    flag = band_flag_line(row)
    top = summary_top(row, res, "INFO", flag) if CS.layout(layout) == "summary" else None
    top = top or (f"{html.escape(plain_head(row))}\n{PT.DECISION_NONE} (Vision opinion only; the bot decided as usual)\n"
                  + (f"{html.escape(flag)}\n" if flag else "") + PT.SEP)
    body = [x for x in _body(row, res, mode, reused).split("\n") if x]
    return top + "\n" + _fit(body, 1024 - PT.MARGIN - PT.tg_len(top) - 1, keep=1,   # ओळी-निहाय (HTML tag अर्धवट नाही)
                              protect=_reason_line if CS.layout(layout) == "summary" else None)


def _budget_ok(g, model, path=None):
    day, month = VS.spent(path)
    est = SA.estimate_usd(model)
    return day + est <= float(g["vision_daily_budget_usd"]) and month + est <= float(g["vision_monthly_budget_usd"]), day, month


def _warn_budget_once(day, month, g, send_text, path=None):
    k = "budget_warned_" + VS.now_ist().strftime("%Y-%m-%d")
    if VS.kv_get(k, path):
        return
    VS.kv_set(k, "1", path)
    send_text("⚠️ <b>Vision budget</b> used up for now — the next signals go without Vision (the bot decides).")


# --------------------------------------------------------------------------------------------------------- V1
FACTOR_MR = {1.0: "full size", 0.5: "half size", 0.0: "skip"}


NO_BUTTONS_MARK = "no approver"                                       # v1_status ची खूण (बटणं नसल्यामुळे timeout नियम लगेच) — v1_notify ओळखतो


def _fmr(f):
    return FACTOR_MR.get(round(float(f or 0), 2), f"×{f}")


BARS_CACHE = {}                                                          # N17: (symbol, daily) ⇒ (1m, daily) of the last fetch


def _bars_fresh(key, row):
    """N17: reuse the resident worker's last 1m fetch (no 21-day fetch per card) when it already reaches this card's last needed minute
    (asof / signal time − 1 min) and is from today; else fetch."""
    try:
        m1, _d1 = BARS_CACHE[key]
        if m1 is None or not len(m1):
            return False
        need = pd.Timestamp(row.get("asof") or CH.to_ist_naive(row["signal_ts"])) - pd.Timedelta(minutes=1)
        have = CH.norm_1m(m1)["timestamp"].max()
        return have >= need and have.normalize() == need.normalize()
    except Exception:                                                    # noqa: BLE001
        return False


def early_card(row, s, meta, png, img_path, img_sha, final, path=None):
    """N17 (30 Oct): an engine-entry card in human_confirm mode (Vision is information there: it only sets the size) is sent BEFORE the
    Vision call — the row goes PENDING_HUMAN with its deadline now, the card says "Vision: reading the chart…", and `vision_edit` puts
    the verdict on the same card. Setting `card_before_vision` (default on) off ⇒ today's order. Returns True when the card went first."""
    from . import card_summary as CS
    if row.get("mode") != "human_confirm" or not s.get("card_before_vision", True) or png is None \
            or not CS.is_engine_entry(_row_tags(row)):
        return False
    st, extra, d = v1_status(row, "pending", s, meta)
    if not d.ask_human:                                                  # no buttons ⇒ the timeout rule at once (as today), after Vision
        return False
    if not VS.finish(row["signal_id"], st, path, only_from="RUNNING", verdict="pending", image_path=img_path, image_sha256=img_sha,
                     final_decision=extra.pop("final", final), **extra):
        return False
    _safe_notify(row, {"verdict": "pending"}, d, png, path)
    return True


def vision_edit(row, res, s, meta, model, path=None):
    """N17: Vision's verdict after an early card — stored on the row; while the card is still undecided its size (factor) follows the
    verdict as today and the caption is rebuilt with the verdict line (buttons kept). Decided already ⇒ stored only. Never raises."""
    sid = row["signal_id"]
    try:
        VS.update(sid, path, verdict=res["verdict"], audits=len(res.get("audits") or []), confidence=res.get("confidence"),
                  vision_done_at=VS._iso(VS.now_ist()),
                  latency_ms=res.get("latency_ms"), cost_usd=res.get("cost_usd") or 0.0, model=model, error=res.get("error"),
                  prompt_version=(res.get("prompt_version") or SA.PROMPT_VERSION) if res.get("audits") or res.get("verdicts") else None,
                  vision_json=json.dumps({**{k: res.get(k) for k in ("audits", "verdicts", "error", "prompt_version", "usage", "fail_action",
                                                                     "rule_hits")}, "context": meta.get("ctx")}, ensure_ascii=False,
                                         default=VS._json_default))
        fresh = VS.get_signal(sid, path) or {}
        if fresh.get("status") != "PENDING_HUMAN" or fresh.get("tg_outcome"):
            return False
        d = VD.decide(row["mode"], res["verdict"], s)
        VS.update(sid, path, factor=d.factor, decision_reason=d.reason)
        from . import approval as AP
        from . import tg as TG
        r = {**row, **fresh}
        cap = v1_caption(r, res, d, fresh.get("deadline"), buttons=True, approval=_approval(row, path), quote=card_quote(r))
        btn = AP.buttons(sid, AP.base_levels(r) is not None)
        if fresh.get("tg_message_id") and TG.edit_caption(fresh["tg_message_id"], cap, buttons=btn):
            VS.update(sid, path, tg_caption=cap)
            return True
    except Exception as exc:                                             # noqa: BLE001 — the card stays as sent
        print(f"⚠️ vision edit: {type(exc).__name__}: {str(exc)[:120]}")
    return False


def v1_status(row, verdict, s, meta):
    """(status, finish fields, Decision|None). V0 mode ⇒ ("DONE", {}, None)."""
    if row.get("mode") not in VC.V1_MODES:
        return "DONE", {}, None
    d = VD.decide(row["mode"], verdict, s)
    if d.ask_human:
        from . import tg as TG
        try:
            can, why = TG.can_ask()
        except Exception as exc:                                         # credentials वाचता आले नाहीत ⇒ बटणं नाहीत
            can, why = False, f"{type(exc).__name__}"
        if not can:                                                     # approver / बटणं नाहीत ⇒ 10 मिनिटं थांबून तोच नियम नको — लगेच
            st = d.timeout_status or "REJECTED"
            d = VD.Decision(st, float(d.timeout_factor or 0.0) if st == "APPROVED" else 0.0,
                            f"{d.reason} · {NO_BUTTONS_MARK} ({why}) ⇒ no-reply rule at once")
    now = VS.now_ist()
    extra = {"factor": d.factor, "decision_reason": d.reason, "timeout_status": d.timeout_status, "timeout_factor": d.timeout_factor,
             "median_range": (meta or {}).get("median_range")}
    if d.ask_human:
        extra["deadline"] = VS._iso(decide_by(row, now, s["approve_window_min"]))
        extra["final"] = "PENDING"
    else:
        extra.update(decided_at=VS._iso(now), decided_by="vision", final="ENTER" if d.status == "APPROVED" else "SKIP")
    return d.status, extra, d


def decide_by(row, now, window_min):
    """N3 (30 Oct): decide-by is counted from the SIGNAL (its trigger bar's close, else signal_ts) + the user's approve window
    (config `approve_window_min`), never from the card time; a late card still gets one minute so its buttons can be used."""
    from . import card_summary as CS
    now = pd.Timestamp(now)
    st = CS.signal_time(row, _row_tags(row))
    if now.tzinfo is not None:
        now = now.tz_convert("Asia/Kolkata").tz_localize(None)
    base = now if st is None else st
    return max(base + pd.Timedelta(minutes=int(window_min)), now + pd.Timedelta(minutes=1))


def deadline_text(d, deadline, approval=False):
    """T-1 (Abhi, plain words): "⏱ Decide by HH:MM. ✅ take · ❌ skip. No reply ⇒ skipped." (operational deadline). approval (PAPER
    `approval_required`) ⇒ the gate never enters without your ✅ ⇒ no reply is always "skipped"."""
    from . import notify as VN
    take = "✅ take" + ("" if float(d.factor or 0) >= 1 else f" ({VN.size_en(d.factor)})")
    return f"⏱ <b>Decide by {VN.hm(deadline)}</b>. {take} · ❌ skip. No reply ⇒ " + \
        ("skipped." if _skipped_on_timeout(d, approval) else f"taken ({VN.size_en(d.timeout_factor)}).")


def _skipped_on_timeout(d, approval=False):
    return bool(approval) or d.timeout_status != "APPROVED" or not d.timeout_factor


def no_buttons_text(why, skipped=True):
    return (f"⚠️ Buttons unavailable: {html.escape(why or 'VISION_CALLBACK_SECRET / TELEGRAM_APPROVER_IDS missing')}; "
            + ("this signal will be skipped." if skipped else "the no-reply rule decides this signal."))


def v1_caption(row, res, d, deadline=None, buttons=True, why="", layout=None, window_min=None, modify=True, approval=False,
               no_buttons=False, quote=None):
    """V1 card. layout (setting `approval_card_layout`): "classic" (default) = today's card; "summary" = the five summary lines on top
    (window_min = the approve window the deadline came from; modify = the ✏️ button is on the card) — the details below the SEP are
    the same lines, trimmed only when the 1024 caption limit needs it (the summary itself is never cut).
    T-1: approval = PAPER `approval_required` (no reply / no buttons ⇒ always skipped); no_buttons = `TG.can_ask()` failed so the
    no-reply rule was applied at once (why = its reason) ⇒ "Buttons unavailable: <why>; this signal will be skipped"."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    from . import card_summary as CS
    try:
        tags = json.loads(row.get("setup_json") or "{}").get("tags") or {}
    except (ValueError, TypeError, AttributeError):
        tags = {}
    if CS.is_engine_entry(tags):                                         # DECISIONS 52 (O-4): short bullets; details = the reply
        return engine_caption(row, res, d, deadline, buttons=buttons, why=why, approval=approval, no_buttons=no_buttons, tags=tags,
                              quote=quote)
    s = _body(row, res, row["mode"]).replace("<b>Vision — info only</b>", f"<b>Vision — {MODE_EN.get(row['mode'], 'on')}</b>", 1)
    head = html.escape(plain_head(row))                                   # Abhi (TELEGRAM_CLEANUP 3): ओळ 1 साधी, ओळ 2 निर्णय
    if tags.get("test_only"):                                           # Abhi: the TEST card — the real path, never a position
        head = "🧪 TEST — not a trade · " + head
    elif tags.get("dry_run"):                                           # Abhi (Sunday dry-run): replay signal ला स्पष्ट टॅग
        head = "🧪 [DRY-RUN] " + head
    if d.status == "PENDING_HUMAN":
        dline = f"<b>{PT.DECISION_APPROVE}</b> by {pd.Timestamp(deadline).strftime('%H:%M') if deadline else '?'}"
    else:
        dline = PT.DECISION_NONE + (" (entry approved automatically)" if d.status == "APPROVED" else " (entry rejected automatically)")
    flag = band_flag_line(row)                                           # Abhi: रुंद (merged) पट्टा ⇒ निर्णय ओळीनंतर स्पष्ट इशारा
    top = summary_top(row, res, d.status, flag, deadline=deadline, window_min=window_min, modify=modify, buttons=buttons) \
        if CS.layout(layout) == "summary" else None
    top = top or f"{head}\n{dline}\n" + (f"{html.escape(flag)}\n" if flag else "") + PT.SEP
    manual = str(tags.get("manual_text") or "") if tags.get("manual") else ""
    s = s.replace("The bot decided as usual — Vision does not change the trade.", "")
    lines = [x for x in s.split("\n") if x]
    s = ""
    if d.status == "PENDING_HUMAN":
        s += "\n" + deadline_text(d, deadline, approval)
        if not buttons:
            s += "\n" + no_buttons_text(why, _skipped_on_timeout(d, approval))
    elif d.status == "APPROVED":
        if no_buttons:
            s += "\n" + no_buttons_text(why, approval)
        s += f"\n<b>✅ ENTRY APPROVED</b> ({_fmr(d.factor)}) — {html.escape(d.reason)}. The bot enters next minute after the price check (its trade message follows)."
    else:
        from . import notify as VN
        if no_buttons:
            s += "\n" + no_buttons_text(why, True)
        s += f"\n<b>❌ ENTRY REJECTED</b> — {html.escape(d.reason)}. {VN.NOT_TAKEN_SHORT}"
    extra = []
    if manual:                                                          # ✋ /paper: तुमचे strikes / SL / T / R:R (HTML आधीच escape केलेलं)
        extra.append(manual)
    try:                                                                # engine entry model: invalidation (info) + evidence
        extra += CS.model_lines(tags)
    except Exception:                                                   # noqa: BLE001 — display only
        pass
    if (res or {}).get("verdict") in (None, "unavailable"):             # Vision status पहिली (लहान, निर्णयासाठी महत्त्वाची) — लांब reading
        extra.append("Vision: unavailable" + (f" ({html.escape(str(res.get('error'))[:80])})" if (res or {}).get("error") else "") +   # ओळींमुळे
                     " — buttons still work")                            # 1024 मर्यादेत कधीच गळत नाही
    try:                                                                # level bots confirmation (§9): trend / area / form / entry / SL / target / R:R
        from atp_private.trade_engine.bots_common import level_gate_bot as _LGB                  # — not for an engine entry model (its own lines above carry the
        if not (tags.get("engine") and tags.get("entry_model")):        # area, label, invalidation; the old line printed "grade None")
            extra += [html.escape(x) for x in _LGB.gate_caption_lines(tags)]
    except Exception:
        pass
    if row.get("volume_line"):                                          # chart च्या volume pane ची एक ओळ (NA ⇒ "volume: NA (grade cap B)")
        extra.append(html.escape(str(row["volume_line"])))
    tail = ("SL / T: your spot SL / T (paper watcher) + the usual backstop rules." if manual else "SL / target / exits: the bot's usual rules (automatic).")
    dec = [x for x in s.split("\n") if x]                               # ⏱ / ⚠️ बटणं नाहीत / ✅ ❌ — header नंतर लगेच, कधीच गाळत नाही
    try:                                                                # T9: the PA evidence line — just before the tail, so it is the
        pa = CS.pa_lines(tags)                                          # first detail dropped when the caption is full (display only)
    except Exception:                                                   # noqa: BLE001
        pa = []
    lines = lines[:1] + dec + extra + lines[1:2] + [engine_line(row)] + lines[2:] + pa + [tail]
    # वरचा साधा भाग कधीच कापत नाही; details मधून आधी शेवटच्या ओळी, मग extra गाळतो (UTF-16 units, MARGIN सकट)
    return top + "\n" + _fit(lines, 1024 - PT.MARGIN - PT.tg_len(top) - 1, keep=1 + len(dec),
                              protect=_reason_line if CS.layout(layout) == "summary" else None)


# ------------------------------------------------------------------------------------------------ DECISIONS 52 / 53: engine-entry card


def _decision_lines(d, deadline, buttons, why, approval, no_buttons):
    """The card's decision lines (⏱ deadline / ⚠️ no buttons / ✅ ❌ automatic) — the same words as today's V1 card."""
    from . import notify as VN
    out = []
    if d.status == "PENDING_HUMAN":
        out.append(deadline_text(d, deadline, approval))
        if not buttons:
            out.append(no_buttons_text(why, _skipped_on_timeout(d, approval)))
    elif d.status == "APPROVED":
        if no_buttons:
            out.append(no_buttons_text(why, approval))
        out.append(f"<b>✅ ENTRY APPROVED</b> ({_fmr(d.factor)}) — {html.escape(d.reason)}. The bot enters next minute after the price check "
                   "(its trade message follows).")
    else:
        if no_buttons:
            out.append(no_buttons_text(why, True))
        out.append(f"<b>❌ ENTRY REJECTED</b> — {html.escape(d.reason)}. {VN.NOT_TAKEN_SHORT}")
    return out


def _vision_bullet(res):
    """"Vision: ✅ घेतो (0.82) — <first sentence>" / "Vision: NA (<why>) — buttons still work"."""
    from . import card_summary as CS
    res = res or {}
    if res.get("verdict") in (None, "unavailable"):
        return "Vision: unavailable" + (f" ({str(res.get('error'))[:80]})" if res.get("error") else "") + " — buttons still work"
    e, mr = VERDICT_MR.get(res.get("verdict"), ("⚪", str(res.get("verdict"))))
    a = (res.get("audits") or [None])[0]
    r = CS.short_reason(a.get("reason")) if isinstance(a, dict) else ""
    who = "Vision (trader)" if isinstance(a, dict) and a.get("decision") else "Vision"   # V7: the trader's own call
    return (f"{who}: {e} {mr}" + (f" {res['confidence'] * 100:.0f}%" if res.get("confidence") is not None else "")
            + (f' — "{r}"' if r else ""))


def fut_missing(row):
    """DECISIONS 53 (VP3): the chart's volume line says FUT volume is missing ⇒ "FUT volume missing — E2 cannot be read"."""
    from atp_private.trade_engine.decision3 import volume_pane as VP
    return VP.engine_text(str(row.get("volume_line") or "")) == VP.ENGINE_NA_LINE


def card_age_lines(tags, now=None, limit_min=None):
    """V6 card age (display only): "trigger closed 3 min ago" from the entry trigger's bar_end vs now; above `engine_delay_alert_min`
    (default 5) a second line asks to re-check the setup. [] when the trigger time is unknown. Never raises."""
    try:
        import pandas as pd
        import atp_private.trade_engine.engine_signal as ES
        tr = (tags or {}).get("entry_trigger")
        be = tr.get("bar_end") if isinstance(tr, dict) else None
        if not be:
            return []
        lim = float(ES.DEFAULTS["engine_delay_alert_min"] if limit_min is None else limit_min)
        mins = max(0, int((ES._naive(now or ES.now_ist()) - ES._naive(be)).total_seconds() // 60))
        out = [f"⏱ trigger closed {mins} min ago"]
        if mins > lim:
            out.append("⚠️ late card: check the setup is still valid before ✅")
        return out
    except Exception:                                                    # noqa: BLE001 — display only
        return []


def engine_caption(row, res, d, deadline=None, buttons=True, why="", approval=False, no_buttons=False, tags=None, now=None, quote=None):
    """N2 + N3 (30 Oct, DECISIONS 142) — the ONE approval message's caption: six lines (`card_summary.card_lines`: what · why · levels ·
    money · Vision · time) + the decision line in the buttons' own words (✅ Take · ❌ Skip · 📎 Details). Warnings (test / dry-run, the
    merged-band flag, no buttons, FUT volume missing) are added only when they apply. The details come only on 📎 (never automatic).
    Always ≤ 1024 (UTF-16) without cutting a key line. Display only."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    from . import card_summary as CS
    tags = tags if isinstance(tags, dict) else _row_tags(row)
    lines = [html.escape(x) for x in CS.card_lines(row, tags, quote=quote, now=now, deadline=deadline, res=res)]
    status = ("decide now" if d.status == "PENDING_HUMAN" else
              "entry approved automatically" if d.status == "APPROVED" else "entry rejected automatically")
    head = f"🎯 <b>{lines[0] if lines else '?'}</b> — {status}"
    if tags.get("test_only"):
        head = "🧪 TEST — not a trade · " + head
    elif tags.get("dry_run"):
        head = "🧪 [DRY-RUN] " + head
    warn = [html.escape(x) for x in (band_flag_line(row), "FUT volume missing — E2 cannot be read" if fut_missing(row) else "") if x]
    dec = []
    if d.status == "PENDING_HUMAN":
        if buttons:
            dec.append("✅ Take · ❌ Skip · 📎 Details. No reply ⇒ " +
                       ("skipped." if _skipped_on_timeout(d, approval) else f"taken ({_size(d.timeout_factor)})."))
        else:
            dec.append(no_buttons_text(why, _skipped_on_timeout(d, approval)))
    else:
        if no_buttons:
            dec.append(no_buttons_text(why, approval or d.status != "APPROVED"))
        dec.append(("✅ " if d.status == "APPROVED" else "❌ ") + html.escape(str(d.reason or "")))
    out = [head] + lines[1:] + warn + dec
    return _fit(out, 1024 - PT.MARGIN, keep=len(out))


def _size(f):
    from . import notify as VN
    return VN.size_en(f)


def engine_details(row, res, d=None, deadline=None):
    """DECISIONS 52 (O-4) — the full details of an engine-entry card, sent as a reply under the card (never cut by the 1024 caption
    limit): today's details lines (Vision's reading and checklist, the object / area line), the 5M trigger in full, the model's
    invalidation rule and evidence list in full, the volume line (engine words, DECISIONS 53), the engine's shadow opinion, the PA
    evidence in full. HTML. `details_parts` splits it at line ends for Telegram's 4096 text limit."""
    from . import card_summary as CS
    tags = _row_tags(row)
    mode = row.get("mode") or ""
    bull = str(row.get("direction") or "").upper() == "BULLISH"
    body = _body(row, res or {}, mode).replace("<b>Vision — info only</b>", f"<b>Vision — {html.escape(MODE_EN.get(mode, 'on'))}</b>", 1)
    body = body.replace("The bot decided as usual — Vision does not change the trade.", "")
    lines = [x for x in body.split("\n") if x]
    head = (f"📎 <b>Details</b> · {html.escape(str(row.get('symbol') or '?'))} · {html.escape(CS.model_label(tags))} · "
            f"{'bull put' if bull else 'bear call'} (the card above)")
    tl = CS.trigger_line(tags)
    trig = [html.escape(x) for x in CS.trigger_details(tags)]
    if tl and html.escape(tl) in lines:                                  # the trigger line of the old details ⇒ the full trigger block
        i = lines.index(html.escape(tl))
        lines = lines[:i] + trig + lines[i + 1:]
    else:
        lines = lines[:3] + trig + lines[3:]
    extra = CS.model_lines(tags, full=True)                              # Vision NA: its "मत / कारण" lines are in the details above
    if row.get("volume_line"):                                           # DECISIONS 53 (VP3): the engine card's words
        from atp_private.trade_engine.decision3 import volume_pane as VP
        extra.append(html.escape(VP.engine_text(str(row["volume_line"]))))
    extra.append(engine_line(row))
    rv = CS.room_vs_invalidation(tags)                                   # M54 V-8: information only, never a gate
    if rv:
        extra.append(html.escape(rv[0].upper() + rv[1:] + " (information only)."))
    extra += CS.pa_full(tags)
    extra += [html.escape(x) for x in CS.structure_facts(tags)]          # G5 / C3: opening gap + pullback form (facts)
    extra.append("SL / target / exits: the bot's usual rules (automatic).")
    from atp_private.trade_engine.bots_common import plain_text as PT
    return PT.dejargon("\n".join([head] + lines + extra))             # N11: no internal words in the details


def details_parts(text, limit=None):
    """The details text in Telegram text messages (≤ 4096 UTF-16 each, split at line ends; a single over-long line is cut there only)."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    from . import tg as TG
    limit = (limit or TG.TEXT_LIMIT) - PT.MARGIN
    parts, cur = [], []
    for ln in str(text or "").split("\n"):
        if PT.tg_len(ln) > limit:
            ln = PT.tg_cut(re.sub(r"<[^>]+>", "", ln), limit)
        if cur and PT.tg_len("\n".join(cur + [ln])) > limit:
            parts.append("\n".join(cur))
            cur = []
        cur.append(ln)
    if cur:
        parts.append("\n".join(cur))
    return [p for p in parts if p.strip()]


def send_details(message_id, row, res, d=None, deadline=None, reply_fn=None):
    """DECISIONS 52: the engine-entry card's details as reply(ies) threaded under the card's message id (vision/tg.reply). The card
    keeps its ✅ / ❌ buttons (the reply has none). No message id ⇒ nothing sent (never a details message without its card). Returns the
    reply ids; never raises (display only)."""
    if not message_id:
        return []
    try:
        from . import tg as TG
        reply_fn = reply_fn or TG.reply
        return [reply_fn(message_id, p) for p in details_parts(engine_details(row, res, d, deadline))]
    except Exception as exc:                                             # noqa: BLE001 — display only: the card is already sent
        print(f"⚠️ engine card details reply: {type(exc).__name__}: {str(exc)[:120]}")
        return []


def _reason_line(x):
    """Vision's full reason in the details (the summary shows only its first sentence) — kept while other detail lines go."""
    return x.startswith("<b>Reason:</b> ")


def engine_line(row):
    """Abhi (Monday PAPER): common analysis engine (decision2) चं shadow मत — निर्णयात नाही (signal_source = own असताना)."""
    try:
        import atp_private.trade_engine.engine_signal as ES
        return html.escape(ES.opinion(row["symbol"], row.get("signal_ts")))
    except Exception as exc:
        return f"engine: NA ({html.escape(type(exc).__name__)})"


def _fit(lines, limit=1024, keep=2, protect=None):
    """Telegram caption मर्यादा (UTF-16 units): पहिल्या `keep` ओळी (header + निर्णय) आणि शेवटची ओळ टिकवून, शेवटून आधीच्या ओळी पूर्ण गाळतो
    (HTML tag मध्येच कापला जाऊ नये). तरीही मोठं ⇒ शेवटची ओळ, मग tags काढून कापतो. protect (summary card only) = a line test: those
    lines are dropped last (Vision's full reason stays in the details); None ⇒ today's order exactly."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    lines = [PT.dejargon(x) for x in lines]                             # N11: no internal words on the card
    while len(lines) > keep + 1 and PT.tg_len("\n".join(lines)) > limit:
        i = len(lines) - 2
        while protect is not None and i >= keep and protect(lines[i]):
            i -= 1
        if i < keep:
            break
        lines.pop(i)
    if len(lines) > keep and PT.tg_len("\n".join(lines)) > limit:
        lines.pop(-1)
    s = "\n".join(lines)
    return s if PT.tg_len(s) <= limit else PT.tg_cut(re.sub(r"<[^>]+>", "", s), limit)


def missed(row, path=None, now=None):
    """N18 (30 Oct): an engine-entry card whose trigger closed more than `card_fresh_min` (Vision setting, dashboard) ago is not sent as
    "decide now": the row expires (no entry; M54 V-7: a would-have shadow record, comparison only) and a silent "missed: <why>, <age>"
    line goes to the log / EOD digest. True ⇒ missed. Never raises (unknown ⇒ the card goes)."""
    try:
        from . import card_summary as CS
        tags = _row_tags(row)
        if not CS.is_engine_entry(tags):
            return False
        st = CS.signal_time(row, tags)
        lim = float(VC.load(row.get("bot"), path).get("card_fresh_min") or 0)
        if st is None or lim <= 0:
            return False
        n = pd.Timestamp(now or VS.now_ist())
        age = (n - st).total_seconds() / 60.0
        if age <= lim:
            return False
        line = (f"missed: {row.get('symbol')} {CS.model_name(tags)} — the card would be {age:.0f} min after the trigger close "
                f"(fresh ≤ {lim:g} min)")
        if VS.transition(row["signal_id"], "PENDING_HUMAN", "EXPIRED", path, executed_at=VS._iso(n), exec_note=line):
            VS.event(row["signal_id"], "missed", line, path)
            from . import gate as VG                                     # M54 V-7: no card, no entry — but its shadow (would-have)
            VG.shadow_unreached(row, line, status="SHADOW_MISSED", path=path)
            import atp_private.trade_engine.notifications as NT
            NT._log_locally("[missed] " + line)                         # a log line, not a Telegram send
            return True
    except Exception as exc:                                             # noqa: BLE001
        print(f"⚠️ missed check: {type(exc).__name__}: {str(exc)[:120]}")
    return False


def card_leader(row, path=None):
    """N4 (30 Oct): the card this engine-entry signal joins instead of a card of its own — the earliest card of the same bot / symbol /
    area visit (any model), else the card of the signal whose Vision verdict it reused. None ⇒ its own card. Never raises."""
    try:
        from . import card_summary as CS
        tags = _row_tags(row)
        if not CS.is_engine_entry(tags):
            return None
        sid, visit = row.get("signal_id"), tags.get("entry_visit")
        if visit:
            for r in VS.list_signals(str(row.get("signal_ts") or "")[:10] or None, path):
                if (r["signal_id"] != sid and r.get("tg_message_id") and r.get("bot") == row.get("bot") and r.get("symbol") == row.get("symbol")
                        and _row_tags(r).get("entry_visit") == visit and not VS.kv_get(f"tg_group:{r['signal_id']}", path)):
                    return r
        prev = (VS.get_signal(row.get("reused_from"), path) if row.get("reused_from") else None) or {}
        if prev.get("tg_message_id"):
            lead = VS.kv_get(f"tg_group:{prev['signal_id']}", path)
            return (VS.get_signal(lead, path) if lead else None) or prev
    except Exception as exc:                                             # noqa: BLE001 — display only: its own card
        print(f"⚠️ card group: {type(exc).__name__}: {str(exc)[:120]}")
    return None


def join_card(row, lead, d, path=None, now=None):
    """N4: this signal rides on `lead`'s card — one line on that card, no new message; the card's ✅ / ❌ decides it too
    (telegram_bot.apply_to_members). The lead already decided ⇒ the same decision now (one decision per area visit)."""
    from . import card_summary as CS
    from . import notify as VN
    sid, lid = row["signal_id"], lead["signal_id"]
    now = now or VS.now_ist()
    VS.kv_set(f"tg_group:{sid}", lid, path)
    try:
        mem = json.loads(VS.kv_get(f"tg_members:{lid}", path) or "[]")
    except ValueError:
        mem = []
    if sid not in mem:
        VS.kv_set(f"tg_members:{lid}", json.dumps(mem + [sid]), path)
    name = CS.model_name(_row_tags(row)) or "another model"
    VN.post(lead, f"member:{sid}", f"➕ {html.escape(name)} on the same area visit — this card's ✅ / ❌ decides it too", path=path)
    if d.ask_human and lead.get("status") not in ("QUEUED", "RUNNING", "PENDING_HUMAN"):
        from .telegram_bot import apply_to_members
        apply_to_members(lead, "A" if lead.get("status") == "APPROVED" else "R", now, path, who=lead.get("decided_by"), only=[sid])
    return lead.get("tg_message_id")


def v1_notify(row, res, d, png, path, reused=False):
    from . import tg as TG
    sid = row["signal_id"]
    r = VS.get_signal(sid, path) or {}
    lead = card_leader({**row, **r}, path)
    if lead is not None:                                                 # N4: one card per area visit (and per reused verdict)
        return join_card({**row, **r}, lead, d, path)
    if d.ask_human and missed({**row, **r}, path):                       # N18: too old for "decide now"
        return None
    can, why = TG.can_ask()
    btn = None
    modify = False
    if d.ask_human and can:                                              # Abhi §10: ✅ · ❌ · ✏️ (engine SL / target असतील तर) · 📝
        from . import approval as AP
        modify = AP.base_levels({**row, **r}) is not None
        btn = AP.buttons(sid, modify)
    no_btn = not can and (d.ask_human or NO_BUTTONS_MARK in str(d.reason or ""))   # T-1: बटणं नाहीत ⇒ card वर साध्या शब्दांत + दिवसातून एक इशारा
    if no_btn:
        from . import notify as VN
        VN.can_ask_alert(why, path)
    lay, win = card_settings(row.get("bot"), path)
    from . import card_summary as CS
    q = card_quote({**row, **r}) if d.ask_human and CS.is_engine_entry(_row_tags({**row, **r})) else None
    cap = v1_caption({**row, **r}, res, d, r.get("deadline"), buttons=bool(btn) or not d.ask_human, why=why, layout=lay, window_min=win,
                     modify=modify, approval=_approval(row, path), no_buttons=no_btn, quote=q)
    mid = TG.send_photo(png, cap, btn)
    VS.update(sid, path, tg_message_id=mid, notified=1 if mid else 0, tg_caption=cap,   # T-1: मूळ caption ⇒ outcome जोडून, कधीच पुसून नाही
              card_sent_at=VS._iso(VS.now_ist()) if mid else None)  # N21
    return mid                                                           # N2: the details only on 📎 (telegram_bot "D"), never automatic


def card_quote(row, fn=None):
    """N3 line 4: credit ₹ · max loss ₹ · lots from the option chain at card time (`paper.card_quote.quote`). Never raises; {} ⇒ the
    card says the chain was not read."""
    try:
        if fn is None:
            from atp_private.trade_engine.paper.card_quote import quote as fn
        return fn(row.get("bot"), row.get("symbol"), row.get("direction")) or {}
    except Exception as exc:                                             # noqa: BLE001 — display only
        print(f"⚠️ card quote: {type(exc).__name__}: {str(exc)[:120]}")
        return {}


def _approval(row, path=None):
    """PAPER `approval_required` (✅ शिवाय entry नाही)? वाचता आलं नाही ⇒ True (gate सारखंच गृहीत). फक्त card च्या शब्दांसाठी."""
    try:
        return VC.approval_required(VC.load(row.get("bot"), path), row.get("trading_mode") or "PAPER")
    except Exception:                                                    # noqa: BLE001 — display only
        return True


def card_settings(bot, path=None):
    """(approval_card_layout, approve_window_min) of the bot's Vision settings; unreadable ⇒ ("classic", None) = today's card."""
    try:
        s = VC.load(bot, path)
        return s.get("approval_card_layout", "classic"), s.get("approve_window_min")
    except Exception:                                                    # noqa: BLE001 — display only
        return "classic", None


def _safe_notify(row, res, d, png, path, reused=False):
    """Telegram / DB चूक निर्णयावर परिणाम करत नाही (निर्णय आधीच नोंदला आहे; बटणं नसतील तर timeout नियम)."""
    try:
        return v1_notify(row, res, d, png, path, reused=reused)
    except Exception as exc:
        print(f"⚠️ vision V1 Telegram त्रुटी (निर्णय नोंदलेला आहे): {type(exc).__name__}: {exc}")
        return None


def v1_housekeeping(path=None, now=None):
    """Timeouts (PENDING_HUMAN; worker उशीर ⇒ जुने QUEUED / RUNNING), न वापरलेले निर्णय (exec_window नंतर) ⇒ EXPIRED, drift / expiry ची माहिती.
    नियम `gate.resolve_due` चेच (bot सुद्धा तेच लावतो — worker बंद असला तरी). रिटर्न बदललेल्या rows."""
    from . import gate as VG
    now = pd.Timestamp(now or VS.now_ist())
    changed = []
    today = now.strftime("%Y-%m-%d")
    for r in VS.rows_with_status(("PENDING_HUMAN", "QUEUED", "RUNNING"), path):
        if r.get("mode") not in VC.V1_MODES:
            continue
        if str(r["signal_ts"])[:10] < today:                          # मागच्या दिवसाचे (worker बंद होता) ⇒ शांतपणे EXPIRED, entry / संदेश नाही
            if VS.transition(r["signal_id"], r["status"], "EXPIRED", path, exec_note="undecided signal from an earlier day", transition_notified=1):
                changed.append((r["signal_id"], "EXPIRED"))
            continue
        _, to = VG.resolve_due(r, VC.load(r["bot"], path), now, path)
        if to:
            changed.append((r["signal_id"], to))                        # card वरचा "No reply" संदेश: खालचा outcome pass (bot ने timeout लावला तरी)
    for r in VS.rows_with_status(("APPROVED", "REJECTED"), path):
        s = VC.load(r["bot"], path)
        if r.get("decided_at") and pd.Timestamp(r["decided_at"]) + pd.Timedelta(minutes=int(s["exec_window_min"])) <= now:
            lim = r["status"] == "APPROVED" and r.get("mod_entry") is not None          # ✏️ limit entry गाठला नाही ⇒ would-have
            if VS.transition(r["signal_id"], r["status"], "EXPIRED", path,
                             exec_note=VG.limit_note(r, s) if lim else VG.no_return_note(r, s),
                             transition_notified=0 if str(r["signal_ts"])[:10] >= today else 1):
                changed.append((r["signal_id"], "EXPIRED"))
                if lim:
                    VG.limit_expired(r, s, path=path)
                else:                                                    # M54 V-7: the bot never came back ⇒ its shadow all the same
                    VG.shadow_unreached(r, f"bot did not reach entry within {s['exec_window_min']} min after {r['status']}",
                                        path=path)
    outcome_messages(today, path)
    return changed


def outcome_messages(day, path=None):
    """T-1 (Abhi, DECISIONS 29): प्रत्येक outcome ⇒ card वर एक ओळ जोडून (कधीच पुसून नाही) + card ला उत्तर म्हणून नवा संदेश, एकदाच, या क्रमाने:
    no reply (timeout — worker वा bot कुणीही लावला) → drift-rejected / expired → shadow opened / no shadow. ✅ / ❌ चे संदेश
    telegram_bot लगेच पाठवतो; shadow closed = vision/outcome.py. फक्त संदेश — status / order ला हात नाही; कधीच raise नाही."""
    from . import notify as VN
    try:
        rows = [r for r in VS.list_signals(day, path) if r.get("mode") in VC.V1_MODES]
    except Exception as exc:                                             # noqa: BLE001 — display only
        print(f"⚠️ outcome संदेश: {type(exc).__name__}: {exc}")
        return
    for r in rows:
        if r.get("decided_by") == "timeout" and r.get("tg_message_id") and not VN.posted(r["signal_id"], "no_reply", path):
            taken = 0.0 if _approval(r, path) or r.get("timeout_status") != "APPROVED" else float(r.get("factor") or 0.0)
            line = VN.no_reply_line(r.get("deadline") or r.get("decided_at"), taken, _approval(r, path))
            VN.post(r, "no_reply", line, f"{VN.where(r)}: {line}", path)
    try:
        for r in VS.rows_with_status(("DRIFT_REJECTED", "EXPIRED"), path):
            if not r.get("transition_notified") and r.get("mode") in VC.V1_MODES and r.get("decided_at"):
                if r["status"] == "DRIFT_REJECTED":
                    kind, line = "drift", VN.drift_line(r.get("drift_result"), _approval(r, path))
                else:
                    wh = bool((VN.shadow_result(r["signal_id"], path) or {}).get("would_have"))     # M54 V-7
                    kind, line = "expired", VN.expired_line(r, VS.last_transition(r["signal_id"], "EXPIRED", path), would_have=wh)
                VN.post(r, kind, line, f"{VN.where(r)}: {line}", path)
                VS.update(r["signal_id"], path, transition_notified=1)
        for r in rows:
            if r["status"] in ("SHADOWED", "DRIFT_REJECTED") and not VN.posted(r["signal_id"], "shadow", path):
                res = VN.shadow_result(r["signal_id"], path)
                if res is not None:
                    line = VN.shadow_result_text(res)
                    VN.post(r, "shadow", line, f"{VN.where(r)}: {line}", path)
    except Exception as exc:                                             # noqa: BLE001 — display only (review: never raise)
        print(f"⚠️ outcome संदेश: {type(exc).__name__}: {exc}")


BAR_WAIT = True                                                          # tests / scripts साठी master switch (setting सोबत)


def bar_wait(row, s, now=None):
    """`vision_wait_for_bar_close`: signal चा setup bar अजून बंद नसेल तर (मूल्यमापन नंतर) ⇒ (थांबायचं?, bar माहिती)."""
    from . import context as CX
    s_tf = CX.trigger_minutes(row)                                       # DECISIONS 37: the trigger candle's TF (5M entries: 5M)
    sb = CX.signal_bar(CH.to_ist_naive(row["signal_ts"]), s_tf, now or VS.now_ist(), (row.get("last_bar") or {}).get("timestamp"))
    return bool(BAR_WAIT and s.get("vision_wait_for_bar_close", True) and not sb["closed"]), sb


# --------------------------------------------------------------------------------------------------------- V4 (R0, audit-only)
def v4_price_facts(row, meta, facts):
    """V4 price check: (known, anchors). known = Vision ला दिलेल्या facts मजकुरातले आकडे + chart वरचे levels + signal च्या किंमती (21 दिवसांचे
    1m OHLC नाहीत — नाहीतर प्रत्येक पूर्णांक "known" होतो). anchors (price-range साठी) = फक्त किंमती: level / spot / invalidation +
    ctx levels / room / invalidation / spot — bar counts / MR / अंतरं नाहीत."""
    from . import checklist as CK
    ctx = (meta or {}).get("ctx") or {}
    anchors = [row.get(k) for k in ("level", "spot", "invalidation")]
    anchors += [ctx.get(k) for k in ("spot", "spot_signal", "invalidation", "level")]
    anchors += [x.get("price") for x in ctx.get("levels") or [] if isinstance(x, dict)]
    anchors.append((ctx.get("room") or {}).get("next_price"))
    anchors = CK.facts_prices([x for x in anchors if isinstance(x, (int, float)) and not isinstance(x, bool)])
    return CK.facts_prices(anchors, facts), anchors


def _warn_v4_budget_once(why, send_text, path=None):
    """V4 budget संपलं ⇒ दिवसातून एकच Telegram ओळ (प्रत्येक signal ला नाही)."""
    k = "v4_budget_warned_" + VS.now_ist().strftime("%Y-%m-%d")
    if send_text is None or VS.kv_get(k, path):
        return
    VS.kv_set(k, "1", path)
    send_text(f"👁 Vision V4 checklist (audit only) paused for today: {html.escape(why)}. V2 audits and orders are unaffected.")


def maybe_v4(row, png, meta, g, model, path=None, send_text=None, client_factory=None, timeout_sec=20):
    """Global `vision_v4_audit` = "v4" ⇒ Method Pack checklist (audit-only). run_once मध्ये **सगळ्या rows चे V2 निर्णय नोंदल्यानंतर** दुसऱ्या
    पासमध्ये चालतो (V2 / gate ला उशीर नाही). निकाल `vision_signals.v4_json` + `pack_version`, खर्च `vision_usage` (task signal_v4, pack_version).
    Budget: स्वतःची दैनिक उप-मर्यादा `vision_v4_daily_cap` + signals राखीव कधीच नाही (V4.budget_ok); संपलं ⇒ दिवसातून एकदा Telegram.
    Shadow mode ⇒ फक्त नोंद; बाकी ⇒ एक Telegram संदेश. Gate / निर्णय / order ला कधीच हात नाही; कधीच raise नाही. रिटर्न निकाल dict | None."""
    if (g or {}).get("vision_v4_audit", "off") != "v4" or png is None or not model or not VC.api_key_present():
        return None
    sid = row["signal_id"]
    try:
        from . import checklist as CK
        from . import method_pack as MP
        from . import v4 as V4
        pack = MP.load()
        facts = SA.signal_text(row)
        est = V4.estimate(1, facts, pack[0], model)["usd_uncached"]
        today = VS.now_ist()
        ok, why = V4.budget_ok(est, g, VS.spent_by_task(path), today.replace(tzinfo=None) if getattr(today, "tzinfo", None) else today,
                               sub_cap=float(g.get("vision_v4_daily_cap", 0.0)))
        if not ok:
            res = {"status": "skipped", "error": why, "pack_version": pack[1], "prompt_version": V4.PROMPT_VERSION}
            if row.get("mode") != "shadow":                                 # shadow ⇒ फक्त नोंद (Telegram नाही)
                _warn_v4_budget_once(why, send_text, path)
        else:
            known, anchors = v4_price_facts(row, meta, facts)
            client = (client_factory or SA.make_client)(timeout_sec)
            res = V4.audit(client, [png], facts, model, known, pack=pack, anchors=anchors,
                           on_usage=lambda u, c: VS.add_usage(V4.TASK, model, u, c, sid, path, pack_version=pack[1]),
                           effort=VC.env_effort("signal"), thinking=VC.env_thinking("signal"))
        VS.update(sid, path, pack_version=res.get("pack_version"),
                  v4_json=json.dumps({**{k: res.get(k) for k in ("status", "data", "error", "usage", "cost_usd", "latency_ms",
                                                                 "pack_version", "prompt_version")},
                                      "decision3_map": dict(CK.DECISION3_MAP)}, ensure_ascii=False, default=str))
        if ok and row.get("mode") != "shadow" and send_text is not None:
            title = f"{row.get('symbol')} {row.get('direction')} {pd.Timestamp(row['signal_ts']):%H:%M}"
            send_text(CK.telegram_text(res, title))
        return res
    except Exception as exc:                                             # noqa: BLE001 — V4 अपयश ⇒ V2 / gate वर परिणाम नाही
        try:
            VS.event(sid, "v4_error", f"{type(exc).__name__}: {str(exc)[:200]}", path)
        except Exception:                                                # noqa: BLE001
            pass
        return None


V4_MAX_PER_CYCLE = 2                                                    # एका run_once मध्ये कमाल V4 calls (V2 rows ना उशीर नको)


def ready_queued(path=None):
    """QUEUED rows ज्यांचा bar बंद झाला (लगेच V2 ला तयार) — bar-close ची वाट पाहणारे मोजत नाही (ते V4 कायम अडवत नाहीत)."""
    from .context import bar_end_of
    now = VS.now_ist()
    n = 0
    for r in VS.rows_with_status("QUEUED", path):
        try:
            be = bar_end_of(r)
            if be is not None and be.to_pydatetime() > now:
                continue
        except Exception:                                                # noqa: BLE001
            pass
        n += 1
    return n


def _drop_v4(jobs, why, path=None):
    """Audit-only ⇒ सोडलेले V4 jobs पुढे नेत नाही; फक्त नोंद (event + log)."""
    for j in jobs:
        sid = (j.get("row") or {}).get("signal_id")
        print(f"ℹ️ V4 skipped for {sid}: {why}")
        try:
            VS.event(sid, "v4_dropped", why, j.get("path"))
        except Exception:                                                # noqa: BLE001
            pass


def run_v4_jobs(jobs, path=None, limit=None, check_queue=False):
    """दुसरा पास: प्रत्येक job (kwargs) maybe_v4 ला — एकाचं अपयश बाकींना थांबवत नाही; कधीच raise नाही. run_once मधून: कमाल `limit` jobs,
    आणि नवे (bar बंद झालेले) QUEUED rows असतील तर पास वगळतो (त्यांचा V2 आधी); उरलेले / वगळलेले jobs सोडले जातात (नोंदीसह)."""
    jobs = list(jobs or [])
    if check_queue and jobs:
        try:
            waiting = ready_queued(path)
        except Exception:                                                # noqa: BLE001
            waiting = 0
        if waiting:
            _drop_v4(jobs, f"{waiting} new signal(s) queued — V2 first", path)
            return []
    if limit is not None and len(jobs) > limit:
        _drop_v4(jobs[limit:], f"V4 cap {limit} per cycle", path)
        jobs = jobs[:limit]
    out = []
    for j in jobs:
        try:
            out.append((j["row"]["signal_id"], maybe_v4(**j)))
        except Exception:                                                # noqa: BLE001
            out.append((j.get("row", {}).get("signal_id"), None))
    return out


def process_row(row, fetch_fn=default_fetch, client_factory=SA.make_client, send_photo=None, send_text=None, path=None, data_cache=None,
                wait_for_bar=True, fetch_volume_fn=None, v4_jobs=None):
    """एक RUNNING row पूर्ण करणे. रिटर्न अंतिम result dict. कधीच raise नाही (चूक ⇒ FAILED row).
    `vision_wait_for_bar_close` (default on): signal चा setup bar बंद होईपर्यंत row परत QUEUED (data fetch / खर्च नाही); बंद झाल्यावर chart आणि
    संदर्भ त्या bar च्या close पर्यंत (asof) — मग निर्णय, आणि entry च्या क्षणी drift guard."""
    from atp_private.trade_engine.notifications import send_telegram_message, send_telegram_photo
    send_photo = send_photo or send_telegram_photo
    send_text = send_text or send_telegram_message
    sid = row["signal_id"]
    img_path = img_sha = None
    try:
        import json
        setup = json.loads(row.get("setup_json") or "{}")
        row = {**row, "bot_label": setup.get("bot_label"), "tags": setup.get("tags") or {}, "invalidation": setup.get("invalidation"),
               "last_bar": setup.get("last_bar")}
        s, g = VC.load(row["bot"], path), VC.load("_global", path)
        model = VC.env_model("signal")
        wait, sb = bar_wait(row, s)
        if wait and wait_for_bar:
            VS.requeue(sid, path)                                       # bar बंद झाल्यावर पुन्हा (worker चा 5 s loop; events / print नाही)
            return {"verdict": None, "deferred": True, "bar_end": sb["end"]}
        if wait_for_bar and s.get("vision_wait_for_bar_close", True) and BAR_WAIT and pd.Timestamp(sb["end_ts"]) > pd.Timestamp(CH.to_ist_naive(row["signal_ts"])):
            row["asof"] = sb["end_ts"]                                    # bar बंद झाला ⇒ तिथपर्यंतचा chart (signal नंतरचा, पण निर्णयाच्या आधीचा)

        # 3. chart (reuse असला तरी Telegram साठी ताजा chart)
        need_daily = True                                               # v2.1: daily candles ⇒ ATR14 / trend / leg (gap वर्ग); 60M ⇒ daily panel
        key = (row["symbol"], need_daily)
        if data_cache is not None and key in data_cache:
            m1, d1 = data_cache[key]
        elif fetch_fn is default_fetch and _bars_fresh(key, row):        # N17: the last fetch already holds this card's bars
            m1, d1 = BARS_CACHE[key]
        else:
            m1, d1 = fetch_fn(row["symbol"], need_daily)
            if data_cache is not None:
                data_cache[key] = (m1, d1)
            if fetch_fn is default_fetch:
                BARS_CACHE[key] = (m1, d1)
        row["expiries"] = []                                             # M56 V3: no expiry framing in Vision ⇒ no expiry fetch
        row["ctx_settings"] = VC.ctx_settings(row["bot"], path)
        if row.get("asof") is not None and m1 is not None and len(m1):   # bar चा शेवटचा 1m candle data मध्ये आला का (review S3)
            last_need = pd.Timestamp(row["asof"]) - pd.Timedelta(minutes=1)
            have = CH.norm_1m(m1)["timestamp"].max()
            if have < last_need and VS.now_ist() < (pd.Timestamp(row["asof"]) + pd.Timedelta(minutes=2)).to_pydatetime():
                VS.requeue(sid, path)                                   # थोडं थांबून पुन्हा (कमाल 2 मिनिटं)
                if data_cache is not None:
                    data_cache.pop(key, None)
                return {"verdict": None, "deferred": True, "bar_end": sb["end"]}
        vfn = fetch_volume_fn or (default_fetch_volume if fetch_fn is default_fetch else None)   # network फक्त default fetch असताना
        vk = ("fut_volume", row["symbol"])
        if engine_volume(row) is None and data_cache is not None and vk in data_cache:
            fut = data_cache[vk]
        else:
            fut = chart_volume(row, vfn)
            if engine_volume(row) is None and data_cache is not None and vfn is not None:
                data_cache[vk] = fut
        if m1 is None or not len(m1):
            png, meta = None, {"error": "no 1m candles"}
        else:
            png, meta = CH.render(m1, row, d1, fut=fut) if fut is not None else CH.render(m1, row, d1)
        row["volume_line"] = meta.get("volume_line")                      # caption ची एक volume ओळ
        row["ctx"] = meta.get("ctx")                                      # v2 signal text (अचूक किंमती OHLC वरून)
        if png:
            # §11: `_sent.png` आधी disk वर (overwrite नाही), मग तीच फाईल परत वाचून (sha256 तपासून) vision आणि Telegram ला — तेच bytes.
            img_path, img_sha = IM.save_exclusive(IM.signal_path(row, IM.SENT), png)
            png = IM.read_verified(img_path, img_sha)
        final = row.get("algo_decision") or "ENTER"                     # V0: vision फक्त माहिती ⇒ अंतिम निर्णय = algorithm चा

        # 2. reuse
        pv = SA.PROMPT_VERSION                                            # review: engine rows reuse only engine audits (fewer paid calls)
        if VS._engine_tag(row.get("setup_json")) and s.get("vision_engine_audit", "engine") == "engine":
            from . import engine_audit as EA
            try:                                                          # model C cards (DECISIONS 32) reuse only model C audits
                tg = (json.loads(row.get("setup_json") or "{}") or {}).get("tags") or {}
            except (ValueError, TypeError, AttributeError):
                tg = {}
            pv = EA.prompt_version({"tags": tg if isinstance(tg, dict) else {},       # V1: the bot's own Vision prompt (trader / checklist)
                                    "ctx_settings": {"vision_engine_prompt": s.get("vision_engine_prompt", EA.TRADER_VERSION)}})
        prev = (VS.find_reusable(row, int(s["reuse_window_min"]), path=path, prompt_version=pv)
                if int(s["reuse_window_min"]) > 0 else None)
        if prev is not None:
            pj = json.loads(prev.get("vision_json") or "{}")
            res = {**pj, "verdict": prev["verdict"], "confidence": prev.get("confidence"), "cost_usd": 0.0, "latency_ms": 0, "error": None}
            pa = (pj.get("audits") or [None])[0]
            if pa:                                                      # code तथ्यं वेळेनुसार बदलतात (L break, PDC acceptance) — नव्या ctx वर पुन्हा (review S6)
                fa, _ = SA.apply_facts(SA.validate(pa)[0] or pa, meta.get("ctx"), row.get("direction"))
                cv = SA.code_verdict(fa, s.get("v2_disagree_rules"), s.get("v2_gray_rules"), meta.get("ctx"), row.get("direction"))
                if cv in SA.SEVERITY and SA.SEVERITY[cv] > SA.SEVERITY.get(res["verdict"], 1):
                    res["verdict"] = cv
            elif res["verdict"] == "agree":
                res["verdict"] = "gray"                                 # जुनं मत तपासता येत नाही ⇒ entry नाही
            pj = {**pj, "reused_image_sha256": prev.get("image_sha256"),          # vision ने पाहिलेली image = आधीच्या signal ची
                  "context": meta.get("ctx"), "reused_context": True}             # संदर्भ या signal चा; मत आधीचं
            st, extra, d = v1_status(row, res["verdict"], s, meta)
            ok = VS.finish(sid, st, path, only_from="RUNNING", verdict=res["verdict"], vision_json=pj, audits=0, confidence=prev.get("confidence"), latency_ms=0,
                      cost_usd=0.0, model=prev.get("model"), reused_from=prev["signal_id"], image_path=img_path, image_sha256=img_sha,
                      prompt_version=prev.get("prompt_version"), final_decision=extra.pop("final", final), **extra)
            if not ok:                                                  # bot / service ने आधीच ठरवलं (उदा. उशीर ⇒ timeout) — overwrite नाही
                return res
            if d is not None:
                _safe_notify(row, res, d, png, path, reused=True)
            elif row["mode"] == "notify":
                VS.set_notified(sid, send_photo(png, caption(row, res, row["mode"], reused=True, layout=s.get("approval_card_layout"))), path)
            return res

        early = early_card(row, s, meta, png, img_path, img_sha, final, path)   # N17: the card first, Vision edits it
        # 4–5. render / model / key / budget
        res = {"verdict": "unavailable", "audits": [], "verdicts": [], "confidence": None, "cost_usd": 0.0, "latency_ms": 0, "model": model}
        if png is None:
            res["error"] = f"no chart: {meta.get('error')}"
        elif not model:
            res["error"] = "VISION_SIGNAL_MODEL env missing"
        elif not VC.api_key_present():
            res["error"] = "ANTHROPIC_API_KEY missing"
        else:
            ok, day, month = _budget_ok(g, model, path)
            if not ok:
                res["error"] = "budget used up"
                _warn_budget_once(day, month, g, send_text, path)
            else:
                client = client_factory(int(s["vision_timeout_sec"]))
                res = SA.audit(client, png, row, model, second_below=float(s["second_audit_below_conf"]), effort=VC.env_effort("signal"),
                               thinking=VC.env_thinking("signal"),
                               on_usage=lambda u, c: VS.add_usage("signal", model, u, c, sid, path),
                               budget_ok=lambda: _budget_ok(g, model, path)[0],
                               disagree_rules=s.get("v2_disagree_rules"), gray_rules=s.get("v2_gray_rules"))
        res["fail_action"] = s["vision_fail_action"] if res["verdict"] == "unavailable" else None
        if early:
            vision_edit(row, res, s, meta, model, path)
            return res
        st, extra, d = v1_status(row, res["verdict"], s, meta)
        ok = VS.finish(sid, st, path, only_from="RUNNING", verdict=res["verdict"], vision_json={**{k: res.get(k) for k in ("audits", "verdicts", "error", "prompt_version", "usage",
                                                                                                    "fail_action", "rule_hits")},
                                                                               "context": meta.get("ctx")},
                  audits=len(res.get("audits") or []), confidence=res.get("confidence"), latency_ms=res.get("latency_ms"),
                  cost_usd=res.get("cost_usd") or 0.0, model=model, image_path=img_path, image_sha256=img_sha, error=res.get("error"),
                  prompt_version=(res.get("prompt_version") or SA.PROMPT_VERSION) if res.get("audits") or res.get("verdicts") else None,
                  final_decision=extra.pop("final", final), **extra)
        if not ok:
            return res
        a0 = (res.get("audits") or [None])[0]
        if isinstance(a0, dict) and a0.get("decision"):                   # V7: the trader's decision in vision_events (trail / measure)
            try:
                VS.event(sid, "trader_decision", json.dumps({k: a0.get(k) for k in ("decision", "plan", "wait_for", "wrong_if",
                                                                                   "engine_claim_matches", "confidence")}), path)
            except Exception:                                            # noqa: BLE001 — a record only, never the card
                pass
        if d is not None:
            _safe_notify(row, res, d, png, path)
        elif row["mode"] == "notify":
            VS.set_notified(sid, send_photo(png, caption(row, res, row["mode"], layout=s.get("approval_card_layout"))), path)
        if g.get("vision_v4_audit", "off") == "v4":                       # R0 V4 (audit-only): V2 निर्णयानंतर
            job = {"row": row, "png": png, "meta": meta, "g": g, "model": model, "path": path, "send_text": send_text,
                   "client_factory": client_factory, "timeout_sec": int(s["vision_timeout_sec"])}
            if v4_jobs is None:
                run_v4_jobs([job])                                      # एकट्या row चा caller (smoke / dry-run) ⇒ लगेच
            else:
                v4_jobs.append(job)                                     # run_once ⇒ सगळ्या rows चे V2 निर्णय आधी, मग V4
        return res
    except Exception as exc:
        err = f"{type(exc).__name__}: {str(exc)[:200]}"
        if row.get("mode") in VC.V1_MODES:                              # V1: worker अपयश ⇒ vision unavailable म्हणून निर्णय (bot अडकू नये)
            try:
                st, extra, d = v1_status(row, "unavailable", VC.load(row["bot"], path), {})
                if VS.finish(sid, st, path, only_from="RUNNING", verdict="unavailable", error=err, image_path=img_path, image_sha256=img_sha,
                             final_decision=extra.pop("final", "ENTER"), **extra):
                    _safe_notify(row, {"verdict": "unavailable", "error": err}, d, None, path)
                return {"verdict": "unavailable", "error": str(exc)}
            except Exception:
                pass
        VS.finish(sid, "FAILED", path, only_from="RUNNING", verdict="unavailable", error=err, image_path=img_path,
                  image_sha256=img_sha, final_decision=row.get("algo_decision") or "ENTER")
        return {"verdict": "unavailable", "error": str(exc)}


def run_once(path=None, **kw):
    VS.expire_stale(STALE_MIN, path)
    try:
        v1_housekeeping(path)
    except Exception as exc:                                            # housekeeping ची चूक नवे signals थांबवत नाही
        print(f"⚠️ vision housekeeping त्रुटी: {type(exc).__name__}: {exc}")
    cache = {}
    done = []
    v4_jobs = []
    for row in VS.claim_queued(path=path):
        r = process_row(row, path=path, data_cache=cache, v4_jobs=v4_jobs, **kw)
        if not (isinstance(r, dict) and r.get("deferred")):
            done.append((row["signal_id"], r))
    run_v4_jobs(v4_jobs, path=path, limit=V4_MAX_PER_CYCLE, check_queue=True)   # R0 V4: दुसरा पास — V2 निर्णय सगळे नोंदल्यानंतरच
    return done


def shadow_report(day, path=None, trades_db=None, out=print):
    """V1 signals चा दिवसाचा सारांश: entry घेतलेले (EXECUTED) वि. नाकारलेले (SHADOWED / DRIFT_REJECTED) आणि त्यांचे PAPER trades (P&L).
    Read-only (live_trades फक्त वाचतो)."""
    from . import outcome as VO
    import os
    rows = [r for r in VS.real_signals(VS.list_signals(day, path)) if r.get("mode") in VC.V1_MODES]   # M54 V-8: no TEST rows
    if trades_db is None:
        from atp_private.trade_engine.config import DB_PATH
        trades_db = DB_PATH
    have_db = os.path.exists(trades_db)
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    out(f"{day}: V1 signals {len(rows)} · " + (", ".join(f"{k} {v}" for k, v in sorted(by.items())) or "—")
        + ("" if have_db else f" · ⚠️ trades DB नाही ({trades_db}) ⇒ P&L नाही"))
    tot = {"EXECUTED": [0, 0.0], "SHADOW": [0, 0.0]}
    for r in rows:
        tr = None
        if have_db and r["status"] in ("EXECUTED", "SHADOWED", "DRIFT_REJECTED"):
            try:
                tr = VO.find_trade(r, trades_db, path)
            except Exception as exc:
                tr = {"status": f"trade शोध चूक: {type(exc).__name__}"}
        pnl = (tr or {}).get("realized_pnl")
        key = "EXECUTED" if r["status"] == "EXECUTED" else "SHADOW" if r["status"] in ("SHADOWED", "DRIFT_REJECTED") else None
        if key and tr and pnl is not None:
            tot[key][0] += 1
            tot[key][1] += float(pnl)
        t = f" · trade {tr.get('status')} P&L {float(pnl):,.0f}" if tr and pnl is not None else (f" · trade {tr.get('status')}" if tr else "")
        lv = f"{float(r['level']):,.2f}" if r.get("level") is not None else "-"
        out(f"  {str(r['signal_ts'])[11:16]} {r['bot']} {r['direction']} L{lv} {r['setup_tf']} → {r['verdict'] or '-'} · "
            f"{r['status']} ×{r['factor'] if r['factor'] is not None else '-'} ({r['decided_by'] or '-'}) · {(r['decision_reason'] or r['error'] or '')[:90]}{t}")
    out(f"बंद trades: entry घेतलेले {tot['EXECUTED'][0]} (P&L {tot['EXECUTED'][1]:,.0f}) · नाकारलेले-shadow {tot['SHADOW'][0]} "
        f"(P&L {tot['SHADOW'][1]:,.0f}) — shadow P&L जास्त ⇒ vision ने चांगले trades नाकारले. EXPIRED = bot entry पर्यंत पोहोचला नाही "
        "(gates बदलले / setup बदलला) — trade नाही.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--loop-seconds", type=int, default=0, help="इतके सेकंद दर --poll ने तपासत राहा (cron दर मिनिटाला ⇒ 55)")
    p.add_argument("--poll", type=int, default=5)
    p.add_argument("--usage", nargs="?", const="today", default=None, help="त्या दिवसाचा token / $ वापर")
    p.add_argument("--shadow", nargs="?", const="today", default=None, help="त्या दिवसाचे V1 निर्णय + नाकारलेल्या signals चे shadow trades")
    a = p.parse_args(argv)
    if a.shadow:
        day = VS.now_ist().strftime("%Y-%m-%d") if a.shadow == "today" else a.shadow
        return shadow_report(day)
    if a.usage:
        day = VS.now_ist().strftime("%Y-%m-%d") if a.usage == "today" else a.usage
        u = VS.usage_summary(day)
        rows = VS.list_signals(day)
        print(f"{day}: signals {len(rows)} (DONE {sum(r['status'] == 'DONE' for r in rows)}, reuse {sum(bool(r['reused_from']) for r in rows)}), "
              f"API calls {u['calls']}, input {u['input_tokens']:,} + cache-read {u['cache_read']:,} + cache-write {u['cache_write']:,}, "
              f"output {u['output_tokens']:,} tokens, खर्च ${u['cost_usd']:.4f}")
        for r in rows:
            print(f"  {r['signal_ts'][11:16]} {r['bot']} {r['symbol']} {r['direction']} L{r['level']} {r['setup_tf']} → {r['verdict']} "
                  f"({r['confidence']}) ${r['cost_usd'] or 0:.4f} {r['latency_ms'] or 0}ms {r['error'] or ''}")
        return 0
    from atp_private.trade_engine.process_lock import ProcessLock, ProcessLockHeld
    try:
        with ProcessLock("vision_worker"):
            VS.expire_stale(STALE_MIN)
            for sid in VS.requeue_orphans():                             # N20: the lock is ours ⇒ RUNNING rows are a dead run's
                print(f"♻️ {sid}: RUNNING from a stopped worker ⇒ queued again")
            t_end = time.monotonic() + max(0, a.loop_seconds)
            while True:
                for sid, res in run_once():
                    print(f"{VS.now_ist():%H:%M:%S} {sid} → {res.get('verdict')} {res.get('error') or ''}")
                if time.monotonic() + a.poll >= t_end:
                    break
                time.sleep(a.poll)
    except ProcessLockHeld:
        print("⏭️ vision worker आधीच चालू आहे")
    return 0


if __name__ == "__main__":
    sys.exit(main())
