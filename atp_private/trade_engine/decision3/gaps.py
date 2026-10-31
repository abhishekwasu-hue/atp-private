"""decision3/gaps.py — G: OPENING GAPS ONLY (owner rule 28 Oct, "only the market-open gap is considered"; standard gap theory —
Edwards & Magee, Bulkowski). Intraday bar-to-bar gaps are NOT gaps here (FVG / imbalance in confluence_pa.py unchanged); the rest of
the reading stays one continuous chart. Evidence only — never a gate (G4, the trigger rule, lives in method.ltf_choch).

  • G1 an opening gap = the session's first 15M bar opens beyond the previous session's close. Full gap: its range does not overlap
    the previous session's last bar's range; open gap: beyond the close, the ranges overlap. Facts: direction, the gap zone (previous
    close … the open; a full gap also its range edges), the size against the recent daily ranges (a comparison, no threshold), the
    first bars' FUT volume against the session averages (when FUT volume is there), and the fill state AT t — open / partly / filled —
    from the bars after the open up to t only (no look-ahead).
  • G2 the class by context (evidence): common (the Daily side is a range / transition, or a gap filled in its own session), breakaway
    (the gap leaves an alive area / the range: the previous close at or inside it, the open beyond its far edge — AND it stays unfilled:
    "breakaway (provisional)" while its session runs unfilled; filled later ⇒ not breakaway; R4, Bulkowski), runaway (in the Daily trend's direction, inside the move),
    exhaustion (in the trend's direction, the tallest opening gap of the move, and by t filled with no new extreme beyond the gap
    session's extreme), island reversal (an exhaustion gap and a later opposite opening gap whose zones overlap).
  • G3 an unfilled gap zone is a price area: listed as a confluence piece when it overlaps the traded area (`at_area`); a filled one
    is removed from the areas (decision3/levels._gap_filled) and stays here as history."""
import numpy as np
import pandas as pd

from . import history as HI

CLASSES = ("common", "breakaway", "breakaway (provisional)", "runaway", "exhaustion", "island reversal")


def _sessions(ts):
    d = pd.to_datetime(pd.Series(ts)).dt.normalize().to_numpy()
    return [i for i in range(1, len(d)) if d[i] != d[i - 1]]


def opening_gaps(V, t):
    """Every opening gap whose session opened at or before bar t, with its facts read at t (G1) and its class (G2). [] when none."""
    A = HI.traded_of(V.levels)                                                      # M56 E4 (D2): traded prices — the previous close is the
    # last TRADED price, never the closing-auction print (DECISIONS 84 / 87)
    ts = V.levels.ts.to_numpy() if hasattr(V.levels.ts, "to_numpy") else np.asarray(V.levels.ts)
    O, H, L, C = A["open"], A["high"], A["low"], A["close"]
    t = int(t)
    firsts = [i for i in _sessions(ts) if i <= t]
    vol = A.get("volume")
    rngs = _daily_ranges(ts, H, L, t)
    out = []
    for i in firsts:
        pc, op = float(C[i - 1]), float(O[i])
        if op == pc:
            continue
        up = op > pc
        full = (L[i] > H[i - 1]) if up else (H[i] < L[i - 1])
        lo, hi = (pc, op) if up else (op, pc)
        fill = _fill(H, L, i, t, pc, op, up)
        prev = [r for d, r in rngs if d < pd.Timestamp(ts[i]).normalize()]
        size = abs(op - pc)
        g = {"bar": i, "ts": str(pd.Timestamp(ts[i])), "dir": "up" if up else "down", "kind": "full" if full else "open",
             "zone": [round(lo, 2), round(hi, 2)], "prev_close": round(pc, 2), "open": round(op, 2), "size": round(size, 2),
             "vs_daily_ranges": None if not prev else {"larger_than": sum(1 for r in prev[-10:] if size > r), "of": len(prev[-10:])},
             "fill": fill}
        if full:
            g["full_edges"] = [round(float(H[i - 1]), 2), round(float(L[i]), 2)] if up else [round(float(H[i]), 2), round(float(L[i - 1]), 2)]
        if vol is not None and len(vol) > i:
            g["first_bar_volume_vs_avg"] = _vol_cmp(vol, ts, i)
        out.append(g)
    _classify(V, out, H, L, ts, t)
    return out


def _session_end(ts, i):
    """The index just after the last bar of bar i's session."""
    d = pd.to_datetime(pd.Series(ts)).dt.normalize().to_numpy()
    return int(np.searchsorted(d, np.datetime64(pd.Timestamp(ts[i]).normalize() + pd.Timedelta(days=1)), side="left"))


def _daily_ranges(ts, H, L, t):
    d = pd.to_datetime(pd.Series(ts[:t + 1])).dt.normalize()
    g = pd.DataFrame({"d": d, "h": H[:t + 1], "l": L[:t + 1]}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
    return [(k, float(r.h - r.l)) for k, r in g.iterrows()]


def _vol_cmp(vol, ts, i):
    """The gap session's first bar FUT volume against the average first bar of the earlier sessions in the data (a comparison)."""
    firsts = _sessions(ts)
    prev = [float(vol[j]) for j in firsts if j < i and np.isfinite(vol[j]) and vol[j] > 0]
    v = float(vol[i]) if np.isfinite(vol[i]) else None
    if v is None or v <= 0 or not prev:
        return None
    return "higher" if v > float(np.mean(prev)) else "lower"


def _fill(H, L, i, t, pc, op, up):
    """open / partly / filled at t — the bars from the gap bar to t (the gap bar's own range counts: it may fill at once)."""
    seg = slice(i, t + 1)
    if up:
        m = float(np.min(L[seg]))
        return "filled" if m <= pc else ("partly" if m < op else "open")
    m = float(np.max(H[seg]))
    return "filled" if m >= pc else ("partly" if m > op else "open")


def _classify(V, gaps, H, L, ts, t):
    from atp_private.trade_engine.decision3 import sw as SW
    sw = getattr(V, "sw_daily", None)
    snap = None
    for k, g in enumerate(gaps):
        i = g["bar"]
        tr = None
        if sw is not None:
            try:
                tr = SW.state_at(sw, V.bar_end[max(0, i - 1)]).trend
            except Exception:                                            # noqa: BLE001 — evidence only
                tr = None
        with_trend = (tr == SW.UP and g["dir"] == "up") or (tr == SW.DOWN and g["dir"] == "down")
        cls = None
        d_end = _session_end(ts, i)
        if tr in (SW.RANGE, SW.TRANSITION):
            cls = "common"
        elif _fill(H, L, i, min(d_end, t + 1) - 1, g["prev_close"], g["open"], g["dir"] == "up") == "filled":
            cls = "common"                                                 # R4 (owner review 28 Oct (6)): filled in its own session
        if cls is None:
            if snap is None:
                try:
                    snap = V.levels.snapshot(int(t))
                except Exception:                                        # noqa: BLE001
                    snap = []
            pc, op = g["prev_close"], g["open"]
            left = [x for x in snap if (g["dir"] == "up" and x["lo"] <= pc <= x["hi"] and op > x["hi"])
                    or (g["dir"] == "down" and x["lo"] <= pc <= x["hi"] and op < x["lo"])]
            if left and g["fill"] != "filled":                           # R4 (Bulkowski): breakaway = it left a base / range AND stays
                cls = "breakaway" if t + 1 >= d_end else "breakaway (provisional)"   # unfilled — provisional while its session runs
        if cls is None and with_trend:
            same = [x for x in gaps[:k] if x["dir"] == g["dir"]]
            tallest = all(g["size"] > x["size"] for x in same)
            day_end = d_end
            sess = slice(i, min(day_end, t + 1))
            ext = float(np.max(H[sess]) if g["dir"] == "up" else np.min(L[sess]))
            later = slice(min(day_end, t + 1), t + 1)
            new_ext = (later.start < later.stop) and ((np.max(H[later]) > ext) if g["dir"] == "up" else (np.min(L[later]) < ext))
            cls = "exhaustion" if tallest and g["fill"] == "filled" and not new_ext else "runaway"
        g["class"] = cls or "common"
    for k, g in enumerate(gaps):                                         # island: an exhaustion gap + a later opposite opening gap
        if g["class"] != "exhaustion":                                   # whose zone overlaps it (price left on its own)
            continue
        for x in gaps[k + 1:]:
            if x["dir"] != g["dir"] and not (x["zone"][1] < g["zone"][0] or x["zone"][0] > g["zone"][1]):
                g["class"] = x["class"] = "island reversal"
                break


def at_area(gaps, lo, hi):
    """G3: the unfilled opening-gap zones overlapping the band lo … hi — confluence words ("opening gap 22,708–22,750 (down, open)")."""
    out = []
    for g in gaps or ():
        z0, z1 = g["zone"]
        if g["fill"] != "filled" and not (z1 < lo or z0 > hi):
            out.append(f"opening gap {z0:,.2f}–{z1:,.2f} ({g['dir']}, {g['fill']}, {g['class']})")
    return out


def latest(gaps):
    """The newest opening gap (the session's own) or None."""
    return gaps[-1] if gaps else None
