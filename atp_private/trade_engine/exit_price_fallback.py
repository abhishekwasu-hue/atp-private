"""exit_price_fallback.py — M56 S1 (audit B3): a missing leg price never silently skips an open trade's exits.

The exit monitor (trading_engine.manage_open_trades) used to `continue` past a trade when any leg's LTP was missing (token expired,
LTP outage): SL, TSL, target and the EOD square-off were skipped with no alert in PAPER. Now:
  1. the missing legs are asked once more (the caller re-queries the broker);
  2. a last known price no older than EXIT_LTP_MAX_AGE_SEC (config, operational setting) fills the gap — the exits run as usual;
  3. still missing ⇒ a CRITICAL "exit undecided — price missing" Telegram line (kind critical_exit, PAPER and LIVE alike, cooled
     down per trade) — except at an INTRADAY trade's EOD square-off, which runs with the last known price of any age: the trade
     is squared off whatever the price-based checks say (never carried forward on a stale price) and a CRITICAL line says so.
State: <database>.last_ltp.json ({instrument_key: [price, epoch]}). Never raises."""
import json
import os
import time


def _path(db_path):
    return os.path.abspath(db_path) + ".last_ltp.json"                 # one cache per database (data/historical_data.db.last_ltp.json)


def alert_ok(db_path, trade_id, cooldown_min=None):
    """One "exit undecided" line per trade per cooldown (state next to the database). Never raises (failure ⇒ True)."""
    try:
        from atp_private.trade_engine.notifications import cooldown_ok
        if cooldown_min is None:
            from atp_private.trade_engine.config import EXIT_UNDECIDED_ALERT_EVERY_MIN as cooldown_min
        return cooldown_ok(f"exit_undecided_{trade_id}", cooldown_min=cooldown_min, path=os.path.abspath(db_path) + ".exit_alerts.json")
    except Exception:                                                    # noqa: BLE001
        return True


def _load(db_path):
    try:
        with open(_path(db_path), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def remember(db_path, prices, now=None):
    """Stores every non-None price of `prices` with its time."""
    try:
        got = {k: v for k, v in (prices or {}).items() if v is not None}
        if not got:
            return
        now = time.time() if now is None else now
        d = _load(db_path)
        d.update({k: [float(v), now] for k, v in got.items()})
        tmp = f"{_path(db_path)}.{os.getpid()}.tmp"                       # two monitors may write at once
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        os.replace(tmp, _path(db_path))
    except Exception:                                                    # noqa: BLE001 — a cache only
        pass


def last_known(db_path, keys, max_age_sec=None, now=None):
    """{key: price} for the keys with a stored price (no older than max_age_sec when given)."""
    now = time.time() if now is None else now
    d = _load(db_path)
    out = {}
    for k in keys:
        v = d.get(k)
        try:
            price, at = float(v[0]), float(v[1])
        except (TypeError, ValueError, IndexError):
            continue
        if max_age_sec is None or now - at <= float(max_age_sec):
            out[k] = price
    return out


def undecided_message(symbol, trade_id, trade_mode, missing, eod_due):
    legs = ", ".join(str(k) for k in missing)[:200]
    tail = ("EOD square-off could NOT run (no price ever seen for these legs) — close the position by hand now."
            if eod_due else "SL / TSL / target were not checked this cycle; the next cycle tries again.")
    return (f"🚨 <b>{symbol} ({trade_mode}) — exit undecided: price missing</b>\n"
            f"Trade {trade_id}: no price for {legs}. {tail}")


def stale_eod_message(symbol, trade_id, trade_mode, legs):
    legs = ", ".join(str(k) for k in legs)[:200]
    return (f"🚨 <b>{symbol} ({trade_mode}) — EOD square-off with a STALE price</b>\n"
            f"Trade {trade_id}: no live price for {legs}; closed at market using the last known price for the record. Check the fill.")
