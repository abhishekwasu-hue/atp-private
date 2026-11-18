"""notify_policy.py — the Telegram notification policy (owner order 30 Oct N1, DECISIONS 142): ONE map, message type ⇒ on / silent / off,
plus a quiet mode, editable on the dashboard (System tools → Telegram notifications; stored as one cloud_db row, no row ⇒ the defaults).
Every Telegram send (notifications.send_telegram_*, vision/tg.send_*) asks it with its message type; an untagged send is "other".

  on      sent with sound          silent  sent without sound (disable_notification)          off  not sent (local log only)
  quiet mode on ⇒ every type except the decision card ("approval_card") is silent at most (an "off" stays off).

Defaults (the owner's rule): sound only on the decision card and on actionable errors; everything else silent (digests: N6 / N8)."""
import time

TYPES = {                                   # type: (default, what it is)
    "approval_card": ("on", "the decision card (✅ / ❌ buttons)"),
    "error": ("on", "an actionable error (token rejected, engine / data error, order blocked)"),
    "area_visit": ("on", "N14: price entered a trade-side area (later states edit it silently)"),
    "fill_exit": ("silent", "PAPER fill / exit / SL / target-near lines"),
    "status": ("silent", "intraday status (positions / P&L)"),
    "preopen": ("silent", "the pre-open message + charts"),
    "eod": ("silent", "end-of-day summaries"),
    "reading": ("silent", "chart reading / reading gallery / visual audit"),
    "vision_info": ("silent", "Vision information (budget, checklist, archive)"),
    "other": ("silent", "any other message (untagged senders, old bots)"),
    "critical_exit": ("on", "M56 S3: exit failed / exit blocked / no price or token for an open position — always sound, cannot be changed"),
}
LOCKED = ("critical_exit",)                 # M56 S3: no dashboard value, no quiet mode and no caller silent=True can mute these
MODES = ("on", "silent", "off")
_CACHE = {"at": 0.0, "s": None}
CACHE_SEC = 60                              # a dashboard change reaches a running bot within a minute (operational, not a rule)


def settings(load=None, now=None):
    """The stored policy (cloud_db.get_telegram_policy), cached for CACHE_SEC; never raises (unreachable ⇒ defaults)."""
    now = time.monotonic() if now is None else now
    if load is None and _CACHE["s"] is not None and now - _CACHE["at"] < CACHE_SEC:
        return _CACHE["s"]
    try:
        if load is None:
            import atp_private.trade_engine.cloud_db as cloud_db
            load = cloud_db.get_telegram_policy
        s = load()
    except Exception:                                                    # noqa: BLE001 — never block a message on the policy store
        s = None
    s = s or defaults()
    _CACHE.update(at=now, s=s)
    return s


def defaults():
    return {**{k: v[0] for k, v in TYPES.items()}, "quiet_mode": "off"}


def mode(kind=None, s=None):
    """The send mode of a message type: "on" / "silent" / "off"."""
    if kind in LOCKED:
        return "on"
    s = s or settings()
    k = kind if kind in TYPES else "other"
    m = s.get(k, TYPES[k][0])
    m = m if m in MODES else TYPES[k][0]
    if s.get("quiet_mode") == "on" and k != "approval_card" and m == "on":
        m = "silent"
    return m


def resolve(kind=None, silent=False, s=None):
    """(send?, silent?) for one message: off ⇒ not sent; an explicit silent=True from the caller is never made loud."""
    if kind in LOCKED:
        return True, False
    m = mode(kind, s)
    return m != "off", bool(silent) or m == "silent"
