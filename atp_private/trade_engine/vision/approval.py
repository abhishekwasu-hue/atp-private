"""vision/approval.py — Telegram approval v2 (Abhi §10, Monday PAPER): ✅ Approve · ✏️ Modify · ❌ Reject (+ कारण) · 📝 Correct marking.
फक्त approver (TELEGRAM_APPROVER_IDS — telegram_bot._authorized नंतर). प्रत्येक parsed value आधी परत दाखवतो (echo), मगच लागू.

  ✏️ Modify  = फक्त ENTRY (spot वर limit): "entry 22590". SL / target engine चेच (signal tags["gate"]; ✋ manual ⇒ /paper चे SL / T),
               R:R फक्त माहिती म्हणून मोजतो (R:R इशारा नाही — Abhi: R:R dashboard चा); area बाहेर ⇒ इशारा (block नाही). सुधारित ticket ⇒ पुन्हा ✅ हवं; approval window पुन्हा सुरू.
               ✅ नंतर spot entry ला पोहोचला तरच PAPER entry (vision/gate.py: limit_reached); exec window मध्ये नाही ⇒ EXPIRED + would-have.
               Vision पुन्हा चालत नाही. SL / target / lots / strikes / hedge / expiry / risk — Telegram वरून कधीच नाही (dashboard वरच).
  ❌ Reject  = लगेच REJECTED (जुनं वर्तन: position नाही, would-have) + कारण एक tap: wrong trend / wrong zone / no real commitment /
               too late / against my plan / other (मोकळा मजकूर). signal row: reject_reason + decision_reason (chart = row चा image_path).
  📝 Correct = approve असो वा नसो: engine ने काय चुकीचं वाचलं (zone / trend / correction-impulse / commitment candle / मोकळा मजकूर) ⇒
               `corrections` table (chart path, engine reading, parsed + raw) — **engine ला कधीच लागू नाही**, फक्त daily review queue.
Free-text उत्तरं: approver-निहाय pending state (vision_kv "tg_state:<id>" = प्रकार + signal + मुदत) — मुदत संपली / cancel ⇒ काहीच बदल नाही.
"""
import html
import json
import re
from collections import Counter

import pandas as pd

from . import config as VC
from . import decide as VD
from . import store as VS
from . import tg as TG

STATE_TTL_MIN = 15                                                      # reply ची वाट (मग "पुन्हा बटण दाबा")
CANCEL = ("cancel", "रद्द")
NOT_MINE = ("unauthorized", "no_state")                                 # handle_text ने हा मजकूर घेतला नाही ⇒ पुढचा router (review replies)
FORBIDDEN = ("sl", "stop", "stoploss", "target", "tgt", "t", "lot", "lots", "qty", "strike", "strikes", "hedge", "width", "expiry", "risk",
             "cap", "size")
ENTRY_RE = re.compile(r"^entry\s*[:=]?\s*(\d+(?:\.\d+)?)$", re.I)
NUM = r"(\d+(?:\.\d+)?)"
TREND = {"up": "up", "bull": "up", "bullish": "up", "uptrend": "up", "down": "down", "bear": "down", "bearish": "down",
         "downtrend": "down", "sideways": "sideways", "range": "sideways", "flat": "sideways"}
ONLY_ENTRY = ("❌ Only the entry can be changed from Telegram (e.g. <code>entry 22590</code>). SL / target / lots / strikes / hedge / "
              "expiry / risk caps — on the dashboard only. Nothing changed.")


# ------------------------------------------------------------------------------------------------ buttons / state

def _rs(x):
    """N12: the one signed ₹ helper (paper.watch._rs), imported lazily (no import cycle)."""
    from atp_private.trade_engine.paper.watch import _rs as f
    return f(x)

def buttons(sid, modify=True):
    """N2 (30 Oct): the card's ONE row — [✅ Take] [❌ Skip] [📎 Details] (the card's own words). ✏️ Modify / 📝 Correct marking ride on
    the 📎 details message (`details_buttons`); `modify` is kept for the callers."""
    return [("✅ Take", VD.callback_data(sid, "A")), ("❌ Skip", VD.callback_data(sid, "R")), ("📎 Details", VD.callback_data(sid, "D"))]


def details_buttons(sid, modify=True):
    """✏️ (engine SL / target असतील तर) आणि 📝 — on the 📎 details message (N2)."""
    b = [("✏️ Modify", VD.callback_data(sid, "M"))] if modify else []
    return b + [("📝 Correct marking", VD.callback_data(sid, "C"))]


def reason_buttons(sid):
    return [(lbl, VD.callback_data(sid, code)) for code, lbl in VD.REJECT_REASONS.items()]


def _key(uid):
    return f"tg_state:{uid}"


def state_get(uid, path=None):
    try:
        st = json.loads(VS.kv_get(_key(uid), path) or "null")
    except ValueError:
        return None
    return st if isinstance(st, dict) and st.get("kind") and st.get("sid") else None


def state_set(uid, kind, sid, path=None, now=None, ttl=STATE_TTL_MIN):
    now = pd.Timestamp(now or VS.now_ist())
    VS.kv_set(_key(uid), json.dumps({"kind": kind, "sid": sid, "exp": VS._iso(now + pd.Timedelta(minutes=ttl))}), path)


def state_clear(uid, path=None):
    VS.kv_set(_key(uid), "", path)


def _tags(row):
    try:
        return json.loads(row.get("setup_json") or "{}").get("tags") or {}
    except (ValueError, AttributeError, TypeError):
        return {}


def _f(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ ✏️ Modify
def base_levels(row):
    """engine चे SL / target / area / entry: signal tags["gate"] (bots_common/level_gate_bot.gate_tags); ✋ manual ⇒ /paper चे SL / T.
    नाहीत ⇒ None (✏️ बटण नाही)."""
    try:
        tags = _tags(row)
        g = tags.get("gate") or {}
        if _f(g.get("sl")) is not None:
            area = [_f(x) for x in (g.get("area") or [])[:2]]
            return {"side": str(g.get("side") or row.get("direction") or "").upper(), "sl": _f(g["sl"]), "target": _f(g.get("target")),
                    "entry": _f(g.get("entry")), "area": area if len(area) == 2 and None not in area else None, "src": "engine",
                    "show_rr": g.get("rr") is not None}                   # gate tags मध्ये rr फक्त dashboard R:R gate चालू असेल तर
        if tags.get("manual") and tags.get("manual_id"):
            from atp_private.trade_engine.paper import manual as PM
            m = PM.get(tags["manual_id"])
            if m and _f(m.get("sl")) is not None:
                return {"side": str(m.get("direction") or row.get("direction") or "").upper(), "sl": _f(m["sl"]), "target": _f(m.get("target")),
                        "entry": _f(m.get("spot")), "area": None, "src": "manual", "show_rr": True}   # Abhi चे स्वतःचे SL / T ⇒ R:R माहिती
    except Exception as exc:
        print(f"⚠️ approval base_levels: {type(exc).__name__}: {exc}")
    return None


def parse_entry(text):
    """"entry 22590" ⇒ (22590.0, None). इतर काहीही (sl / target / lots …) ⇒ (None, स्पष्ट चूक)."""
    t = " ".join(str(text or "").replace(",", "").split())
    m = ENTRY_RE.match(t)
    if m:
        v = float(m.group(1))
        return (v, None) if v > 0 else (None, "❌ entry must be above 0. Nothing changed.")
    words = re.findall(r"[a-z]+", t.lower())
    if any(w in FORBIDDEN for w in words):
        return None, ONLY_ENTRY
    return None, "❌ Not understood — write: <code>entry 22590</code> (limit on spot). To cancel: cancel. Nothing changed."


def modify_ticket(row, entry):
    """(ticket, None) किंवा (None, चूक). SL / target बदलत नाहीत; R:R = (target − entry) / (entry − SL) (दिशेनुसार)."""
    b = base_levels(row)
    if b is None:
        return None, "❌ Cannot modify: this signal has no engine SL / target."
    if b["side"] not in ("BULLISH", "BEARISH"):
        return None, f"❌ Cannot modify: the setup's side is unknown ({html.escape(b['side'] or '?')})."
    d = 1 if b["side"] == "BULLISH" else -1
    sl, tg = b["sl"], b["target"]
    if (entry - sl) * d <= 0:
        return None, f"❌ entry {entry:g} must be {'above' if d > 0 else 'below'} SL {sl:g} ({b['side']}). Nothing changed."
    if tg is not None and (tg - entry) * d <= 0:
        return None, f"❌ entry {entry:g} is beyond target {tg:g} — no trade left. Nothing changed."
    show_rr = bool(b.get("show_rr", True))                               # engine: फक्त dashboard R:R gate चालू असेल तर (Abhi)
    rr = round((tg - entry) * d / ((entry - sl) * d), 2) if (tg is not None and show_rr) else None
    warn = []
    if b["area"]:
        lo, hi = sorted(b["area"])
        if not lo <= entry <= hi:
            warn.append(f"⚠️ entry outside the area {lo:,.0f}–{hi:,.0f}")
    return {"side": b["side"], "entry": entry, "sl": sl, "target": tg, "rr": rr, "area": b["area"], "engine_entry": b["entry"],
            "src": b["src"], "warnings": warn, "show_rr": show_rr}, None


def _row_res(row):
    """The signal row's own Vision result (verdict + audits) for the summary card; unreadable ⇒ just the verdict."""
    try:
        vj = json.loads(row.get("vision_json") or "{}")
    except (ValueError, TypeError):
        vj = {}
    return {"verdict": row.get("verdict"), "audits": (vj.get("audits") if isinstance(vj, dict) else None) or []}


def ticket_text(row, t, deadline, exec_min, layout=None, window_min=None):
    """The changed-entry ticket. layout (setting `approval_card_layout`) "summary" ⇒ the summary lines replace the two plain lines on
    top (vision/card_summary.py); the details below the SEP stay today's text."""
    from atp_private.trade_engine.bots_common import plain_text as PT
    from . import card_summary as CS
    eng = f" (engine: {t['engine_entry']:g})" if t.get("engine_entry") is not None else ""
    area = f" · area {PT.band_range(min(t['area']), max(t['area']))}" if t.get("area") else ""   # Abhi: पट्ट्याची रुंदी प्रत्येक approval मध्ये
    try:
        g = _tags(row).get("gate") or {}
    except Exception:                                                    # noqa: BLE001 — फक्त माहिती
        g = {}
    g = g if isinstance(g, dict) else {}                                 # a non-dict gate tag never raises here (review #355)
    flag = PT.band_flag(min(t["area"]), max(t["area"]), g.get("band_warn_pts"), g.get("band_warn_rule"),   # layer 6b: setting
                        engine_area=g.get("mode") == "engine") if t.get("area") else ""                     # (default = points)
    show_rr = bool(t.get("show_rr", True))                               # engine signal + R:R gate बंद ⇒ R:R कुठेच नाही (Abhi)
    rr = "NA" if t["rr"] is None else f"{t['rr']:g}"
    tgt = "NA" if t["target"] is None else f"{t['target']:g}"
    ref = "engine reference (info): " if t.get("src") == "engine" else ""   # Abhi RR2: trade चे SL / target = dashboard
    lines = [f"✏️ <b>Changed ticket</b> · {html.escape(str(row.get('symbol')))} {t['side']} · {html.escape(str(row.get('setup_tf') or ''))}",
             f"Entry (limit, spot) <b>{t['entry']:g}</b>{eng} · {ref}SL {t['sl']:g} · target {tgt}{area}"
             + (f" · R:R <b>{rr}</b>" if show_rr else "")]
    lines += t["warnings"]
    lines += ["Only the entry changed — the trade's SL / target / lots / strikes / hedge / expiry / risk: from the dashboard." if ref else
              "Only the entry changed — SL / target / lots / strikes / hedge / expiry / risk: from the engine / dashboard.",
              f"⏱ <b>until {pd.Timestamp(deadline):%H:%M}</b> ✅ again. After ✅, PAPER entry only if spot reaches {t['entry']:g}; "
              f"not within {exec_min} min ⇒ no position (would-have record)."]
    rr_txt = "" if not show_rr else (" — R:R not available" if t["rr"] is None else f" — reward is {t['rr']:g}× the risk")
    head = (f"{html.escape(str(row.get('symbol')))}: your changed entry {t['entry']:g} ({'engine reference ' if ref else ''}stop {t['sl']:g}, "
            f"target {tgt}){rr_txt}. "
            "Check the new numbers, then approve again.")
    top = None
    if CS.layout(layout) == "summary":
        try:
            top = CS.top(row, _row_res(row), "PENDING_HUMAN", flag, deadline=deadline, window_min=window_min, ticket=t)
        except Exception as exc:                                         # noqa: BLE001 — display only ⇒ today's top
            print(f"⚠️ summary ticket (classic used): {type(exc).__name__}: {str(exc)[:120]}")
    if top:
        return top + "\n" + "\n".join(lines)
    return (f"{head}\n<b>{PT.DECISION_APPROVE}</b> by {pd.Timestamp(deadline):%H:%M}\n" + (f"{html.escape(flag)}\n" if flag else "")
            + f"{PT.SEP}\n" + "\n".join(lines))


def start_modify(row, uid, answer, cq_id, send=None, path=None, now=None):
    send = send or TG.send_text
    b = base_levels(row)
    if b is None:
        answer(cq_id, "Cannot modify: no engine SL / target")
        return False, "no_levels"
    state_set(uid, "entry", row["signal_id"], path, now)
    area = f" · area {min(b['area']):,.0f}–{max(b['area']):,.0f}" if b["area"] else ""
    eng = f"entry {b['entry']:g} · " if b["entry"] is not None else ""
    tgt = "NA" if b["target"] is None else f"{b['target']:g}"
    send(f"✏️ {html.escape(str(row['symbol']))} {html.escape(str(row.get('direction') or ''))}: write the new <b>entry</b> — "
         f"<code>entry 22590</code> (limit on spot). To cancel: cancel\nEngine: {eng}SL {b['sl']:g} · target {tgt}{area} (these do not change)"
         + ("\nThese are engine reference (info) — the trade's SL / target = dashboard settings." if b.get("src") == "engine" else ""))   # Abhi RR2
    answer(cq_id, "✏️ write the entry (e.g. entry 22590)")
    return True, "modify_prompt"


def apply_entry(uid, sid, text, send=None, path=None, now=None, edit=None, send_buttons=None):
    """"entry X" ⇒ ticket ⇒ row (mod_entry, mod_json, नवी deadline) — status PENDING_HUMAN तसाच (पुन्हा ✅ हवं).
    edit = (message_id, original_caption, line) — T-1: जुना card पुसत नाही (ओळ जोडतो, बटणं काढतो); नवा ticket = नवा card (त्याचा caption नोंद)."""
    send = send or TG.send_text
    edit = edit or TG.append_outcome
    send_buttons = send_buttons or TG.send_photo
    now = pd.Timestamp(now or VS.now_ist())
    entry, err = parse_entry(text)
    if err:
        send(err)                                                        # state तसाच — पुन्हा लिहू शकता
        return False, "bad_input"
    row = VS.get_signal(sid, path)
    if row is None or row["status"] != "PENDING_HUMAN" or (row.get("deadline") and pd.Timestamp(row["deadline"]) <= now):
        state_clear(uid, path)
        send(f"⌛ signal is now {html.escape(str((row or {}).get('status') or 'gone'))} ⇒ cannot modify. Nothing changed.")
        return False, "not_pending"
    t, err = modify_ticket(row, entry)
    if err:
        send(err)
        return False, "bad_input"
    s = VC.load(row["bot"], path)
    dl = now + pd.Timedelta(minutes=int(s["approve_window_min"]))       # Abhi: Modify नंतर approval window पुन्हा सुरू
    if not VS.transition(sid, "PENDING_HUMAN", "PENDING_HUMAN", path, mod_entry=entry, mod_json=json.dumps(t, ensure_ascii=False),
                         deadline=VS._iso(dl)):
        state_clear(uid, path)
        send("⌛ the signal is already decided ⇒ cannot modify.")
        return False, "race"
    state_clear(uid, path)
    line = f"✏️ entry changed ({entry:g}) — changed ticket below; these buttons are off · {row['symbol']} {row['direction']}"
    prev = str(row.get("tg_outcome") or "").strip()
    edit(row.get("tg_message_id"), row.get("tg_caption"), f"{prev}\n{line}" if prev else line)
    tk = ticket_text(row, t, dl, int(s["exec_window_min"]), layout=s.get("approval_card_layout"), window_min=s.get("approve_window_min"))
    mid = send_buttons(None, tk, buttons(sid, True))
    if mid:                                                              # पुढचे outcomes या नव्या card वर (मूळ caption = ticket)
        VS.update(sid, path, tg_message_id=mid, tg_caption=tk, tg_outcome=None)
    return True, "modified"


# ------------------------------------------------------------------------------------------------ ❌ कारण
def reason_prompt_text(row):
    return f"❌ Reason? (one tap) · {html.escape(str(row['symbol']))} {html.escape(str(row.get('direction') or ''))}"


def prompt_reason(row, send_buttons=None, set_buttons=None):
    """N2: the optional ❌ reason = buttons on the SAME card (its keyboard after the ❌ edit); no card id ⇒ the old separate prompt."""
    try:
        mid = row.get("tg_message_id")
        if not send_buttons and mid and (set_buttons or TG.set_buttons)(mid, reason_buttons(row["signal_id"])):
            return
        if send_buttons:
            send_buttons(None, reason_prompt_text(row), reason_buttons(row["signal_id"]))
        else:                                                            # N1: the optional ❌-reason prompt is no decision — silent
            TG.send_photo(None, reason_prompt_text(row), reason_buttons(row["signal_id"]), kind="other")
    except Exception as exc:
        print(f"⚠️ reject कारण विचारता आलं नाही: {type(exc).__name__}: {exc}")


def _store_reason(sid, label, path=None):
    VS.update(sid, path, reject_reason=label[:300], decision_reason=f"you rejected — {label}"[:300])
    VS.event(sid, "reject_reason", label, path)


def set_reason(row, code, uid, answer, cq_id, edit=None, msg_id=None, send=None, path=None, now=None):
    """edit = (message_id, original_caption, line) — T-1: कारणाचा प्रश्न तसाच ठेवून उत्तराची ओळ जोडतो (पुसत नाही)."""
    edit = edit or TG.append_outcome
    send = send or TG.send_text
    if row.get("human_decision") != "reject":
        answer(cq_id, "You did not reject this signal")
        return False, "not_rejected"
    if code == "RO":
        state_set(uid, "reason", row["signal_id"], path, now)
        answer(cq_id, "Write the reason")
        send("❌ Write the reason (free text). To cancel: cancel")
        return True, "reason_prompt"
    label = VD.REJECT_REASONS[code]
    _store_reason(row["signal_id"], label, path)
    answer(cq_id, f"Reason saved: {label}")
    line = f"❌ reason: <b>{label}</b> ✓ · {row['symbol']} {row.get('direction') or ''}"
    if msg_id and str(msg_id) == str(row.get("tg_message_id")):          # N2: the reason buttons sat on the card ⇒ a line on the card
        from . import notify as VN
        VN.post(row, "reason", line, path=path, append=edit if edit is not TG.append_outcome else None)
    elif msg_id:
        edit(msg_id, reason_prompt_text(row), line)
    return True, label


# ------------------------------------------------------------------------------------------------ 📝 Correct marking
def parse_correction(text):
    """रिटर्न ({"type", …}, None) किंवा (None, चूक). प्रकार: zone / trend / wave / commitment / free."""
    raw = " ".join(str(text or "").split())
    if not raw:
        return None, "❌ Empty text — write what was wrong. To cancel: cancel"
    if len(raw) > 500:
        return None, "❌ Text too long (up to 500 characters)."
    low = raw.lower()
    if low.startswith("zone"):
        m = re.match(rf"^zone\s*[:=]?\s*{NUM}\s*(?:-|–|to|/)\s*{NUM}$", low.replace(",", ""))
        if not m or float(m.group(1)) == float(m.group(2)):
            return None, "❌ Write zone like: <code>zone 22570-22640</code> (two different numbers). Not saved."
        lo, hi = sorted((float(m.group(1)), float(m.group(2))))
        return {"type": "zone", "lo": lo, "hi": hi}, None
    if low.startswith("trend"):
        w = low.split()
        if len(w) != 2 or w[1] not in TREND:
            return None, "❌ Write trend like: <code>trend up</code> / <code>trend down</code> / <code>trend sideways</code>. Not saved."
        return {"type": "trend", "value": TREND[w[1]]}, None
    if low.startswith("commitment"):
        m = re.match(r"^commitment(?:\s+candle)?\s+(\d{1,2}):(\d{2})$", low)
        if not m or not (0 <= int(m.group(1)) < 24 and 0 <= int(m.group(2)) < 60):
            return None, "❌ Write commitment like: <code>commitment candle 10:45</code>. Not saved."
        return {"type": "commitment", "time": f"{int(m.group(1)):02d}:{m.group(2)}"}, None
    pos = re.sub(r"\bnot\s+(?:an?\s+)?(correction|impulse)\b", " ", low)     # "correction, not impulse" ⇒ correction
    kinds = [k for k in ("correction", "impulse") if k in pos]
    if len(kinds) == 1:
        return {"type": "wave", "value": kinds[0]}, None
    return {"type": "free"}, None


def describe(p):
    if p["type"] == "zone":
        return f"zone {p['lo']:g}–{p['hi']:g}"
    if p["type"] == "trend":
        return f"trend {p['value']}"
    if p["type"] == "wave":
        return f"wave: {p['value']}"
    if p["type"] == "commitment":
        return f"commitment candle {p['time']}"
    return "free text"


def start_correction(row, uid, answer, cq_id, send=None, path=None, now=None):
    send = send or TG.send_text
    state_set(uid, "correction", row["signal_id"], path, now)
    send(f"📝 {html.escape(str(row['symbol']))} {html.escape(str(row.get('setup_tf') or ''))}: what did the engine read wrong? e.g. "
         "<code>zone 22570-22640</code> · <code>trend down</code> · <code>this is a correction, not impulse</code> · "
         "<code>commitment candle 10:45</code> · or free text. (Daily review only — not applied to the engine.) To cancel: cancel")
    if answer:
        answer(cq_id, "📝 write it")
    return True, "correction_prompt"


def apply_correction(uid, sid, text, by, send=None, path=None, now=None):
    send = send or TG.send_text
    p, err = parse_correction(text)
    if err:
        send(err)
        return False, "bad_input"
    row = VS.get_signal(sid, path)
    if row is None:
        state_clear(uid, path)
        send("❌ Signal not found — not saved.")
        return False, "missing"
    cid = VS.add_correction({"ts": now, "signal_id": sid, "bot": row.get("bot"), "symbol": row.get("symbol"), "tf": row.get("setup_tf"),
                             "image_path": row.get("image_path"), "engine_reading": row.get("setup_json"), "ctype": p["type"], "parsed": p,
                             "raw_text": " ".join(str(text).split()), "by_": by}, path)
    state_clear(uid, path)
    send(f"📝 Saved ({html.escape(describe(p))}) · {html.escape(str(row['symbol']))} {html.escape(str(row.get('setup_tf') or ''))} · "
         f"signal {sid} · #{cid} — not applied to the engine; in the daily review queue.")
    return True, cid


def start_correction_cmd(text, uid, send=None, path=None, now=None):
    """/correct [signal_id] — ✅ / ❌ नंतर (बटणं गेल्यावर) सुद्धा 📝. id नाही ⇒ आजचा शेवटचा signal."""
    send = send or TG.send_text
    parts = (text or "").split()
    row = None
    if len(parts) > 1:
        row = VS.get_signal(parts[1], path)
    else:
        day = pd.Timestamp(now or VS.now_ist()).strftime("%Y-%m-%d")
        rows = sorted(VS.list_signals(day, path), key=lambda r: r.get("created_at") or "")
        row = rows[-1] if rows else None
    if row is None:
        send("❌ /correct: signal not found (usage: /correct [signal_id])")
        return False, "missing"
    return start_correction(row, uid, None, None, send, path, now)


# ------------------------------------------------------------------------------------------------ free-text router
def handle_text(m, authorized, path=None, send=None, now=None, edit=None, send_buttons=None):
    """approver चा साधा मजकूर (command नाही): pending state असेल तरच हाताळतो. रिटर्न (handled, label); handled False ⇒ पुढचा router
    (review replies) पाहील."""
    if not authorized(m.get("from"), m.get("chat")):
        return False, "unauthorized"
    uid = str((m.get("from") or {}).get("id"))
    st = state_get(uid, path)
    if st is None:
        return False, "no_state"
    send = send or TG.send_text
    now = pd.Timestamp(now or VS.now_ist())
    text = str(m.get("text") or "").strip()
    if pd.Timestamp(st["exp"]) <= now:
        state_clear(uid, path)
        send("⌛ Reply time is over — press the button again. Nothing changed.")
        return True, "state_expired"
    if text.lower() in CANCEL:
        state_clear(uid, path)
        send("Cancelled — nothing changed.")
        return True, "cancelled"
    if st["kind"] == "entry":
        return apply_entry(uid, st["sid"], text, send, path, now, edit, send_buttons)
    if st["kind"] == "correction":
        return apply_correction(uid, st["sid"], text, f"telegram:{uid}", send, path, now)
    if st["kind"] == "reason":
        if not text:
            send("❌ Empty text — write the reason. To cancel: cancel")
            return False, "bad_input"
        label = f"other: {' '.join(text.split())}"
        _store_reason(st["sid"], label, path)
        state_clear(uid, path)
        send(f"❌ Reason saved: {html.escape(label[:200])}")
        return True, "reason"
    state_clear(uid, path)
    return False, "unknown_state"


# ------------------------------------------------------------------------------------------------ 15:45 daily summary (Abhi §10e)
def daily_summary(day=None, vpath=None, jpath=None):
    """{approvals, modifications, rejections: {कारण: n}, timeouts, corrections, pnl, trades_closed, trades_open, would_have} — dry-run वगळून."""
    from atp_private.trade_engine.paper import journal as PJ
    day = str(day or VS.now_ist().strftime("%Y-%m-%d"))
    sig = VS.real_signals(VS.list_signals(day, vpath))                # M54 V-8: smoke / TEST card / dry-run rows left out
    rej = Counter((r.get("reject_reason") or "कारण नाही") for r in sig if r.get("human_decision") == "reject")
    tr = [t for t in PJ.rows(day, jpath) if not t.get("dry_run")]
    closed = [t for t in tr if t.get("exit_time")]
    wh = [w for w in PJ.would_have_rows(jpath) if str(w.get("ts") or "")[:10] == day and not w.get("dry_run")]
    return {"day": day, "approvals": sum(1 for r in sig if r.get("human_decision") == "approve"),
            "modifications": sum(1 for r in sig if r.get("mod_entry") is not None),
            "modified_approved": sum(1 for r in sig if r.get("mod_entry") is not None and r.get("human_decision") == "approve"),
            "limit_expired": sum(1 for r in sig if r.get("mod_entry") is not None and r["status"] == "EXPIRED"),
            "rejections": dict(rej), "timeouts": sum(1 for r in sig if r.get("decided_by") in ("timeout", "stale")),
            "corrections": len(VS.corrections(day, path=vpath)), "pnl": round(sum(float(t.get("net_pnl") or 0) for t in closed), 2),
            "trades_closed": len(closed), "trades_open": len(tr) - len(closed), "would_have": len(wh)}


def daily_summary_text(day=None, vpath=None, jpath=None):
    """15:45 सारांशाचा "तुमचे निर्णय + P&L" भाग — साधे English शब्द (Abhi, TELEGRAM_CLEANUP 4). आकडे daily_summary चेच."""
    d = daily_summary(day, vpath, jpath)
    nrej = sum(d["rejections"].values())
    rej = ", ".join(f"{html.escape('no reason given' if k == 'कारण नाही' else k)} {v}"
                    for k, v in sorted(d["rejections"].items(), key=lambda x: -x[1]))
    appr = f"approved {d['approvals']}"
    if d["modified_approved"] or d["limit_expired"]:
        appr += (f" ({d['modified_approved']} with a changed entry"
                 + (f"; {d['limit_expired']} never reached the changed entry" if d["limit_expired"] else "") + ")")
    return "\n".join([
        f"<b>Your decisions today</b>: {appr}, rejected {nrej}" + (f" ({rej})" if rej else "")
        + f", changed entry {d['modifications']}, no answer {d['timeouts']}.",
        f"<b>Trades</b>: closed {d['trades_closed']}, still open {d['trades_open']}, net P&L <b>{_rs(d['pnl'])}</b>. "
        f"Skipped trades tracked for comparison: {d['would_have']}.",
        f"Chart corrections you sent: {d['corrections']} (kept for review; not applied to the engine)."])
