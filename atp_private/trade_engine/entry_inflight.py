"""entry_inflight.py — M56 S5 (audit B6, B11): an in-flight marker around every LIVE entry order (the exit in-flight pattern of
order_safety.mark_inflight). trading_engine.open_multi_leg_trade writes the marker BEFORE the LIVE order is sent and clears it after
the live_trades INSERT (or at once on a definite no-fill). A crash in between leaves the marker: the exit monitor (trade_monitor REST
cycle, on start and every cycle) reconciles every marker older than ENTRY_INFLIGHT_GRACE_SEC (config) with the broker:
  • correlation id first — an order-book entry with the leg's correlation_id says whether that leg filled (Upstox returns it);
  • else net qty — the instrument has a non-zero broker net qty and no OPEN LIVE trade in the DB holds that instrument ⇒ untracked;
  • untracked leg(s) ⇒ CRITICAL (critical_exit) "untracked LIVE position" line (cooled down per marker), the marker stays;
  • nothing untracked (all flat, or the trade is in the DB) ⇒ the marker is cleared silently;
  • positions unreadable / an adapter account (no positions API) ⇒ the marker stays + a CRITICAL "check by hand" line.
Reconcile never sends an order. State: data/entry_inflight.json (fcntl lock)."""
import contextlib
import json
import os
import shutil
import time
import uuid

try:
    import fcntl
except ImportError:                                                  # Windows (dev)
    fcntl = None

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "entry_inflight.json")


@contextlib.contextmanager
def _lock():
    fh = None
    try:
        if fcntl is not None:
            os.makedirs(os.path.dirname(PATH), exist_ok=True)
            fh = open(PATH + ".lock", "a")
            fcntl.flock(fh, fcntl.LOCK_EX)
    except OSError:
        if fh is not None:
            fh.close()
        fh = None
    try:
        yield
    finally:
        if fh is not None:
            try:
                fcntl.flock(fh, fcntl.LOCK_UN)
            finally:
                fh.close()


UNREADABLE = "#unreadable"


def _load(backup=False):
    """The markers. An unreadable file is never lost silently: a writer copies it aside first (backup=True) and an UNREADABLE marker
    takes its place, which reconcile clears only when no broker position is untracked."""
    try:
        with open(PATH) as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        pass
    bak = None
    if backup:
        bak = f"{PATH}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
        shutil.copy2(PATH, bak)
    return {UNREADABLE: {"at": 0, "orders": [], "backup": bak}}


def _save(d):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    tmp = f"{PATH}.{os.getpid()}.tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, PATH)


def _slim(o):
    return {k: o.get(k) for k in ("instrument_token", "transaction_type", "quantity", "broker_quantity", "product", "tag",
                                  "correlation_id", "strike", "option_type", "expiry") if k in o}


def mark(symbol, source, account_id, orders, now=None):
    """BEFORE the LIVE entry send. Returns the marker id. Raises OSError when it cannot be written (caller must not send)."""
    mid = f"E{int(time.time() if now is None else now)}_{uuid.uuid4().hex[:8]}"
    with _lock():
        d = _load(backup=True)
        d[mid] = {"at": time.time() if now is None else now, "symbol": symbol, "source": source, "account_id": account_id,
                  "orders": [_slim(o) for o in orders or []]}
        _save(d)
    return mid


def clear(mid):
    """After the DB insert (or a definite no-fill). Never raises."""
    if not mid:
        return
    try:
        with _lock():
            d = _load(backup=True)
            if d.pop(mid, None) is not None:
                _save(d)
    except OSError:
        pass


def leftovers(now=None, grace=None):
    """Markers older than the grace (an entry in another process is normally between send and insert for seconds only)."""
    now = time.time() if now is None else now
    if grace is None:
        try:
            from atp_private.trade_engine.config import ENTRY_INFLIGHT_GRACE_SEC as grace
        except ImportError:
            grace = 120
    return {k: v for k, v in _load().items() if isinstance(v, dict) and now - float(v.get("at") or 0) >= grace}


def _net(positions, tok):
    hits = [p for p in positions if isinstance(p, dict) and p.get("instrument_token") == tok]
    try:
        return sum(int(round(float(p.get("quantity") or 0))) for p in hits) if hits else 0
    except (TypeError, ValueError):
        return None


def _book_leg(book, corr):
    if not corr or not isinstance(book, list):
        return None
    for od in book:
        if isinstance(od, dict) and od.get("correlation_id") == corr:
            return od
    return None


def untracked_legs(marker, positions, tracked_tokens, order_book=None):
    """(legs, why). legs = the marker's legs that are open at the broker and held by no OPEN LIVE trade. why = None when known,
    else the reason the marker cannot be checked (legs then = all marker legs)."""
    legs = marker.get("orders") or []
    if marker.get("unreadable"):                                         # the marker file was lost: any untracked broker position counts
        if not isinstance(positions, list):
            return [], "entry_inflight.json was unreadable and broker positions are unreadable"
        nets = {}
        for p in positions:
            if isinstance(p, dict) and p.get("instrument_token"):
                try:
                    nets[p["instrument_token"]] = nets.get(p["instrument_token"], 0) + int(round(float(p.get("quantity") or 0)))
                except (TypeError, ValueError):
                    return [], "entry_inflight.json was unreadable and a broker quantity is unreadable"
        return [{"instrument_token": t, "broker_net_qty": n} for t, n in nets.items() if n and t not in tracked_tokens], None
    if marker.get("account_id"):                                         # review S3: tracked first (the trade reached the DB ⇒ cleared)
        rest = [o for o in legs if o.get("instrument_token") not in tracked_tokens]
        if not rest:
            return [], None
        return rest, (f"account {marker.get('account_id')}: no positions API here — check that broker by hand "
                      f"(then: python3 clear_exit_state.py --clear-entry-marker <id>)")
    if not isinstance(positions, list):
        return legs, "broker positions unreadable"
    out = []
    for o in legs:
        tok = o.get("instrument_token")
        if tok in tracked_tokens:
            continue                                                     # the trade reached the DB (crash after insert)
        od = _book_leg(order_book, o.get("correlation_id"))
        if od is not None:
            try:
                filled = float(od.get("filled_quantity") or 0)
            except (TypeError, ValueError):
                filled = None
            if filled == 0 and str(od.get("status", "")).lower() in ("rejected", "cancelled"):
                continue                                                 # correlation id: this leg never filled
        net = _net(positions, tok)
        if net is None:
            return legs, f"{tok}: broker quantity unreadable"
        if net != 0 or (od is not None and str(od.get("status", "")).lower() not in ("complete", "rejected", "cancelled")):
            out.append({**o, "broker_net_qty": net})
    return out, None


def _alert_ok(mid, cooldown_min=None):
    try:
        from atp_private.trade_engine.notifications import cooldown_ok
        if cooldown_min is None:
            from atp_private.trade_engine.config import ENTRY_UNTRACKED_ALERT_EVERY_MIN as cooldown_min
        return cooldown_ok(f"entry_untracked_{mid}", cooldown_min=cooldown_min, path=PATH + ".alerts.json")
    except Exception:                                                    # noqa: BLE001
        return True


def _leg_txt(o):
    bits = [str(o.get("transaction_type", "?")), str(o.get("quantity", "?"))]
    if o.get("strike") is not None:
        bits.append(f"{o.get('strike')}{o.get('option_type') or ''}")
    bits.append(f"[{o.get('instrument_token')}]")
    if "broker_net_qty" in o:
        bits.append(f"broker net {o['broker_net_qty']}")
    return " ".join(bits)


def message(mid, marker, legs, why=None):
    head = (f"🛑 <b>CRITICAL — untracked LIVE entry ({marker.get('symbol')}, {marker.get('source')})</b>" if not why else
            f"🛑 <b>CRITICAL — LIVE entry in flight could not be checked ({marker.get('symbol')}, {marker.get('source')})</b>")
    lines = [head, "The bot sent this entry but has no trade row for it — it does NOT manage SL / target / EOD of these legs."]
    if why:
        lines.append(f"Why not checked: {why}")
    lines.append("Legs: " + "; ".join(_leg_txt(o) for o in legs))
    lines.append("Check the broker app now; close by hand (shorts first) or tell the bot. Marker " + str(mid))
    return "\n".join(lines)


def reconcile(positions, tracked_tokens, order_book=None, now=None, sender=None, grace=None):
    """Every leftover marker: clear it (nothing untracked) or send the CRITICAL line (cooled down). Returns a list of
    (marker id, legs, why) still open. Never raises, never sends an order."""
    out = []
    try:
        lefts = leftovers(now, grace)
    except Exception:                                                    # noqa: BLE001
        return out
    for mid, mk in lefts.items():
        try:
            if mid == UNREADABLE:
                mk = {**mk, "unreadable": True, "symbol": "?", "source": f"marker file unreadable, copy {mk.get('backup')}"}
            legs, why = untracked_legs(mk, positions, set(tracked_tokens or ()), order_book)
            if not legs and why is None:
                clear(mid)
                continue
            out.append((mid, legs, why))
            if _alert_ok(mid):
                text = message(mid, mk, legs, why)
                if sender is None:
                    from atp_private.trade_engine.order_safety import send_alert
                    send_alert(text)
                else:
                    sender(text)
        except Exception:                                                # noqa: BLE001
            continue
    return out
