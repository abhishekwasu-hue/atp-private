"""carry_guard.py — M56 S6 (audit B7): SWING / carry-forward trades (credit_spread_auto_trader opens SWING; a carried spread can reach
expiry) are squared off on the expiry day of their legs' contract at EXPIRY_SQUAREOFF_IST (config, default 15:10 IST), and one daily
position-check line (first monitor cycle at / after CARRY_CHECK_IST) lists every open carried trade with its expiry and days left.
The expiry is read from the leg data already stored (legs_json "expiry"); a trade whose legs have no stored expiry is never squared off
by this rule and the daily line says so ("expiry not stored"). Operational times only; never raises."""
import datetime
import json
import os


def _hm(text, default):
    try:
        hh, mm = (int(x) for x in str(text).split(":")[:2])
        return hh, mm
    except (TypeError, ValueError):
        return default


def squareoff_time():
    try:
        from atp_private.trade_engine.config import EXPIRY_SQUAREOFF_IST as t
    except ImportError:
        t = "15:10"
    return _hm(t, (15, 10))


def _date(v):
    try:
        return datetime.date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def legs_expiry(legs):
    """The nearest stored expiry of the legs (date) or None when any leg has none (unknown ⇒ no automatic rule)."""
    exps = [_date((leg or {}).get("expiry")) for leg in legs or []]
    if not exps or any(e is None for e in exps):
        return None
    return min(exps)


def squareoff_due(legs, trade_style, ist_now):
    """(True, detail) on the legs' expiry day at / after the square-off time (or later — an expired contract still OPEN) for a
    non-INTRADAY trade; else (False, None)."""
    if str(trade_style or "INTRADAY").upper() == "INTRADAY":
        return False, None
    exp = legs_expiry(legs)
    if exp is None:
        return False, None
    hh, mm = squareoff_time()
    today = ist_now.date()
    if today > exp or (today == exp and (ist_now.hour, ist_now.minute) >= (hh, mm)):
        return True, (f"Expiry-day square-off — the legs' contract expires {exp.isoformat()}; a {trade_style} / carry-forward trade is "
                      f"closed at {hh:02d}:{mm:02d} IST on its expiry day (never held into expiry).")
    return False, None


def open_carried_trades(db_path):
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT trade_id, symbol, COALESCE(mode,'LIVE'), COALESCE(trading_style,'INTRADAY'), legs_json, strikes_summary "
                            "FROM live_trades WHERE status='OPEN' AND COALESCE(trading_style,'INTRADAY') != 'INTRADAY'").fetchall()
    finally:
        conn.close()


def check_line(rows, today):
    """The daily position-check text (None when no carried trade is open)."""
    if not rows:
        return None
    out = [f"📋 <b>Carried positions check</b> ({len(rows)} open SWING / carry-forward)"]
    hh, mm = squareoff_time()
    for trade_id, symbol, mode, style, legs_json, strikes in rows:
        try:
            legs = json.loads(legs_json or "[]")
        except ValueError:
            legs = []
        exp = legs_expiry(legs)
        if exp is None:
            note = "⚠️ expiry not stored — no automatic expiry-day square-off; check by hand"
        elif exp < today:
            note = f"🛑 contract expired {exp.isoformat()} and the trade is still OPEN — check by hand"
        elif exp == today:
            note = f"expiry TODAY — squared off at {hh:02d}:{mm:02d} IST"
        else:
            note = f"expiry {exp.isoformat()} ({(exp - today).days} days)"
        out.append(f"• {symbol} {mode} {style} {strikes or ''} [{trade_id}] — {note}")
    return "\n".join(out)


def send_daily_check(db_path, ist_now, sender=None):
    """Once a day (first call at / after CARRY_CHECK_IST): the check line. Returns the text sent or None. Never raises."""
    try:
        try:
            from atp_private.trade_engine.config import CARRY_CHECK_IST as t
        except ImportError:
            t = "09:20"
        if (ist_now.hour, ist_now.minute) < _hm(t, (9, 20)):
            return None
        from atp_private.trade_engine.notifications import cooldown_ok
        text = check_line(open_carried_trades(db_path), ist_now.date())
        if text is None:
            return None
        if not cooldown_ok(f"carry_check_{ist_now.date().isoformat()}", cooldown_min=24 * 60,
                           path=os.path.abspath(db_path) + ".carry_check.json"):
            return None
        if sender is None:
            from atp_private.trade_engine.notifications import send_telegram_message
            critical = "🛑" in text or "⚠️" in text
            sender = lambda m: send_telegram_message(m, kind="critical_exit" if critical else "status")   # noqa: E731
        sender(text)
        return text
    except Exception:                                                    # noqa: BLE001
        return None
