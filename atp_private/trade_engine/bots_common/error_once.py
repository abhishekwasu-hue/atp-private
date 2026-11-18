"""Error alerts: at most one Telegram line per (cause, IST day); one "restored" line after a failure. Never raises."""
import json
import os
import re
from datetime import datetime, timedelta, timezone

_IST = timezone(timedelta(hours=5, minutes=30))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(_ROOT, "data", "error_once.json")      # tests / callers override with state_path=


def cause_key(err):
    """Short stable cause: exception class + first line, digits stripped (so timestamps / ports / codes do not split a cause)."""
    first = (str(err).strip().splitlines() or [""])[0]
    name = type(err).__name__ + ": " if isinstance(err, BaseException) else ""
    return re.sub(r"\d+", "", name + first)[:120].strip()


def _day(now):
    if now is None:
        return str(datetime.now(_IST).date())
    return str(now.date())


def _load(p):
    try:
        with open(p, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st = st if isinstance(st, dict) else {}
    for k in ("sent", "open"):
        if not isinstance(st.get(k), dict):
            st[k] = {}
    return st


def _save(st, p):
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(st, f)
    except OSError:
        pass


def _send(line, send):
    try:
        if send is None:
            from atp_private.trade_engine.notifications import send_telegram_message
            return send_telegram_message(line, kind="error") is not False
        return send(line) is not False
    except Exception as exc:                                         # noqa: BLE001
        print(f"{line}  [Telegram send failed: {type(exc).__name__}]")
        return False


def send_once(cause, line, send=None, state_path=None, now=None):
    """Send `line` unless `cause` was already sent on this IST day (then log locally only). A failed send is not recorded (retried
    next call). Returns True when sent."""
    p, day = state_path or STATE_PATH, _day(now)
    st = _load(p)
    if st["sent"].get(cause) == day:
        print(f"(duplicate error suppressed today) {line}")
        return False
    if not _send(line, send):
        return False
    st["sent"] = {k: v for k, v in st["sent"].items() if v == day}
    st["sent"][cause] = day
    st["open"][cause] = day
    _save(st, p)
    return True


def send_restored(cause, line, send=None, state_path=None):
    """After a send_once for `cause`: send the ONE restored line and close it. Never without a prior failure. Returns True when sent."""
    p = state_path or STATE_PATH
    st = _load(p)
    if cause not in st["open"]:
        return False
    if not _send(line, send):
        return False
    st["open"].pop(cause, None)
    st["sent"].pop(cause, None)
    _save(st, p)
    return True
