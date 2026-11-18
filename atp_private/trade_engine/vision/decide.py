"""vision/decide.py — V1 निर्णय नियम (pure functions): mode × verdict ⇒ पुढचं पाऊल, drift guard, callback HMAC.

🎓 M56 V1 (C1): Vision never changes size — factor is 1.0 (enter at the dashboard lots) or 0 (skip, shadow track); a "half" action
or a gray verdict never scales the lots (the owner's ✅ = the dashboard lots; gray / WAIT is advice text on the card only). Exits ला
यातलं काहीच लागत नाही.

  auto_veto          agree ⇒ 1 · gray ⇒ vision_gray_action (half / ignore ⇒ 1, skip ⇒ 0) · disagree ⇒ vision_disagree_action
                     (skip ⇒ 0, half / ignore ⇒ 1) · unavailable ⇒ vision_fail_action (ignore 1 / skip 0)
  human_confirm      नेहमी Telegram (✅/❌). Approve ⇒ 1 (every verdict) · Reject / timeout ⇒ skip
  veto_then_confirm  disagree ⇒ आपोआप skip (फक्त माहिती, बटण नाही) · agree / gray / unavailable ⇒ Telegram (✅ ⇒ 1) · timeout ⇒
                     timeout_action: auto_veto = auto_veto चे नियम (enter 1 or skip) · skip = skip. Approver / बटणं नसतील तर worker
                     हा timeout नियम लगेच लावतो.
"""
import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Optional

ACTION_F = {"half": 1.0, "skip": 0.0, "ignore": 1.0}   # M56 V1: "half" no longer halves (Vision never changes size) — enter or skip only
MR_FALLBACK_PCT = 0.10                 # median range नसेल (chart अपयश) तर spot च्या 0.10% (NIFTY 5m bar ~ 0.08%) — drift तपासणी वगळत नाही


@dataclass
class Decision:
    status: str                        # APPROVED | REJECTED | PENDING_HUMAN
    factor: float                      # APPROVED चा (आणि PENDING_HUMAN मध्ये Approve केल्यास) size factor
    reason: str
    timeout_status: Optional[str] = None
    timeout_factor: Optional[float] = None
    ask_human: bool = False


def _final(f, reason):
    f = 1.0 if float(f) > 0 else 0.0                                     # M56 V1: enter at the dashboard lots or skip — never a size
    return Decision("APPROVED" if f > 0 else "REJECTED", f, reason)


def verdict_factor(verdict, s):
    if verdict == "agree":
        return 1.0
    if verdict == "gray":
        return ACTION_F[s["vision_gray_action"]]
    if verdict == "disagree":
        return ACTION_F[s["vision_disagree_action"]]
    return {"ignore": 1.0, "skip": 0.0}[s["vision_fail_action"]]          # unavailable


def decide(mode, verdict, s):
    """Vision मतानंतरचा निर्णय."""
    if mode == "auto_veto":
        return _final(verdict_factor(verdict, s), f"Vision {verdict} (Vision can veto)")
    if mode == "human_confirm":
        f = 1.0                                                          # M56 V1: your ✅ = the dashboard lots (gray = advice only)
        return Decision("PENDING_HUMAN", f, f"Vision {verdict} · your ✅ decides", "REJECTED", 0.0, True)
    if mode == "veto_then_confirm":
        if verdict == "disagree":
            return Decision("REJECTED", 0.0, "Vision disagrees ⇒ skipped automatically")
        f = 1.0                                                          # M56 V1: your ✅ = the dashboard lots (gray = advice only)
        tf = (1.0 if verdict_factor(verdict, s) > 0 else 0.0) if s.get("timeout_action", "auto_veto") == "auto_veto" else 0.0
        why = "unavailable ⇒ asking you" if verdict == "unavailable" else verdict
        return Decision("PENDING_HUMAN", f, f"Vision {why} · your ✅ decides", "APPROVED" if tf > 0 else "REJECTED", tf, True)
    raise ValueError(f"not a V1 mode: {mode}")


def scaled_lots(lots, factor):
    """Reduce-only: floor(lots × factor), कधीच lots पेक्षा जास्त नाही."""
    return max(0, min(int(lots), int(float(lots) * float(factor) + 1e-9)))


def drift_guard(row, spot, direction, max_drift_mr, origin=None):
    """Approve ते entry च्या क्षणी पुन्हा तपासणी — after M56 V1 the ONLY skip rule between an approval and the entry, and it reads the
    price only, never Vision (source: the V1 spec, docs/VISION_HUMAN_EYE.md "Drift guard"; its number is the setting max_drift_mr).
    रिटर्न अपयशांची यादी (रिकामी ⇒ ठीक).
      1. spot signal-spot पासून max_drift_mr × median range पेक्षा दूर
      2. invalidation ओलांडली: setup मध्ये invalidation असेल तर ती; नाहीतर level ची बाजू बदलली (bot ची चालू दिशा signal च्या उलट)
      3. pullback origin ओलांडला — bot ने origin दिला तरच (सध्याचे 5-Min / 15M bots origin मोजत नाहीत ⇒ हा नियम त्यांच्यासाठी लागू नाही)
      4. Bot चे daily loss / kill switch / max-open: bot चे नेहमीचे gates entry पर्यंत पुन्हा चालतात ⇒ इथे तपासणी नाही (रचनेनेच)."""
    out = []
    s0, mr = row.get("spot"), row.get("median_range")
    if not mr and s0:
        mr = abs(float(s0)) * MR_FALLBACK_PCT / 100.0
    if s0 is not None and mr and spot is not None and abs(float(spot) - float(s0)) > float(max_drift_mr) * float(mr):
        out.append(f"drift: spot {float(spot):,.1f} vs signal {float(s0):,.1f} (> {max_drift_mr} × median range {float(mr):.1f})")
    bull = str(row.get("direction", "")).upper().startswith("BULL")
    inv = row.get("invalidation")
    if inv is None and row.get("setup_json"):
        try:
            import json
            inv = json.loads(row["setup_json"]).get("invalidation")
        except (ValueError, AttributeError):
            inv = None
    inv = float(inv) if inv is not None else None
    if inv is not None and spot is not None and ((bull and spot < inv) or (not bull and spot > inv)):
        out.append(f"invalidation {float(inv):,.1f} crossed")
    elif direction is not None and str(direction).upper() != str(row.get("direction", "")).upper():
        out.append(f"the level's side changed ({row.get('direction')} → {direction})")
    if origin is not None and spot is not None and ((bull and spot > origin) or (not bull and spot < origin)):
        out.append(f"pullback origin {float(origin):,.1f} crossed (breakout)")
    return out


# --------------------------------------------------------------------------------------------------------- callback HMAC
def secret():
    return (os.environ.get("VISION_CALLBACK_SECRET") or "").strip()


def sign(signal_id, action, key=None):
    k = (key if key is not None else secret()).encode("utf-8")
    return hmac.new(k, f"{signal_id}|{action}".encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def callback_data(signal_id, action, key=None):
    return f"v1|{signal_id}|{action}|{sign(signal_id, action, key)}"


# Abhi §10: ✏️ Modify (M), 📝 Correct marking (C), ❌ नंतर कारण (एक tap; RO = other ⇒ मोकळा मजकूर)
REJECT_REASONS = {"RT": "wrong trend", "RZ": "wrong zone", "RC": "no real commitment", "RL": "too late", "RP": "against my plan",
                  "RO": "other"}
ACTIONS = ("A", "R", "M", "C", "D", *REJECT_REASONS)                   # N2: D = 📎 Details


def parse_callback(data, key=None):
    """(signal_id, action) किंवा None (format / HMAC चूक). action ∈ ACTIONS (A, R, M, C, कारणे)."""
    try:
        tag, sid, action, sig = str(data).split("|")
    except ValueError:
        return None
    k = key if key is not None else secret()
    if tag != "v1" or action not in ACTIONS or not k:
        return None
    return (sid, action) if hmac.compare_digest(sig, sign(sid, action, k)) else None


def approver_ids():
    return {x.strip() for x in (os.environ.get("TELEGRAM_APPROVER_IDS") or "").split(",") if x.strip()}
