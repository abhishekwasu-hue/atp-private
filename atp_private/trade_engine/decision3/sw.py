"""decision3/sw.py — SW: swings + trend per timeframe (owner order SW1–SW5, DECISIONS 92 / 98). Additive: nothing in the engine reads
it until the owner approves its proof charts.

SW1  A swing = a confirmed pivot (``sw_pivot_n`` own-TF bars on both sides; known at the close of the last of them) that also passes a
     magnitude filter: its distance from the previous opposite swing is at least ``k`` × that TF's ATR (``sw_atr_n``) at the swing's
     bar. The newest swing is PROVISIONAL (a more extreme pivot of the same kind can still replace it); it becomes FINAL when the next
     opposite swing passes the filter. Nothing here reads a provisional swing.
SW2  EXTERNAL swings = the set with the larger filter (``sw_ext_atr``), INTERNAL = the swings of the tighter set (``sw_int_atr``) that are
     not external (smaller swings inside one external leg).
SW3  Trend from FINAL EXTERNAL swings only. Structure = the last two highs and the last two lows: higher highs + higher lows = UP, lower
     highs + lower lows = DOWN, mixed = RANGE (before any trend). An established trend ends by a close through its protecting swing (the
     last low in UP / the last high in DOWN) = CHoCH ⇒ TRANSITION (DECISIONS 109: the old trend has ended, the new one is not confirmed;
     range rules — edge fades only). TRANSITION ends by a BOS (DECISIONS 111) = a candle CLOSE beyond the last external swing in a
     direction: beyond the last external swing of the CHoCH's side made after the CHoCH ⇒ that trend; beyond the last external swing
     of the other side ⇒ that trend. A wick beyond (a sweep) is no BOS.
Lookback (DECISIONS 98 4a): every function reads all the bars it is given — the caller passes the full stored history of the TF.
No look-ahead: everything at bar t uses bars ≤ t and swings known (final) by t. No number in this file: every size is a setting.
"""
from dataclasses import dataclass, field

import numpy as np

UP, DOWN, RANGE, UNKNOWN, TRANSITION = "UP", "DOWN", "RANGE", "UNKNOWN", "TRANSITION"


@dataclass
class Swing:
    kind: str                 # "H" / "L"
    price: float
    bar: int                  # the bar of the extreme
    known: int                # the bar whose close confirms the pivot (bar + pivot_n)
    final: int = None         # the bar from which the swing is FINAL (the next opposite swing passed the filter); None = provisional
    label: str = "EXTERNAL"   # EXTERNAL / INTERNAL (SW2)


def atr(high, low, close, n):
    """Wilder ATR over n bars (bars ≤ i only); NaN until n true ranges exist."""
    h, lo, c = (np.asarray(x, float) for x in (high, low, close))
    prev = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - lo, np.maximum(np.abs(h - prev), np.abs(lo - prev)))
    out = np.full(len(tr), np.nan)
    if len(tr) < n:
        return out
    out[n - 1] = tr[:n].mean()
    for i in range(n, len(tr)):
        out[i] = out[i - 1] + (tr[i] - out[i - 1]) / n
    return out


def pivots(high, low, n):
    """Fractal pivots: a high above the n bars before it and not below the n bars after it (lows mirrored); the first of equal
    extremes wins. Known at bar i + n (its close). [(kind, price, bar, known)] in known order."""
    h, lo = np.asarray(high, float), np.asarray(low, float)
    out = []
    for i in range(n, len(h) - n):
        if h[i] > h[i - n:i].max() and h[i] >= h[i + 1:i + n + 1].max():
            out.append(("H", float(h[i]), i, i + n))
        if lo[i] < lo[i - n:i].min() and lo[i] <= lo[i + 1:i + n + 1].min():
            out.append(("L", float(lo[i]), i, i + n))
    return sorted(out, key=lambda p: (p[3], p[2]))


def swings(high, low, close, pivot_n, atr_n, k):
    """SW1: the filtered swing sequence (alternating H / L). A pivot of the same kind as the last swing replaces it when more extreme
    (the last swing is provisional); an opposite pivot is a new swing when it lies ≥ k × ATR (at its bar) from the last swing — the
    last swing becomes FINAL at the new one's known bar. [Swing]"""
    a = atr(high, low, close, atr_n)
    out = []
    for kind, px, b, kn in pivots(high, low, pivot_n):
        if not out:
            out.append(Swing(kind, px, b, kn))
            continue
        last = out[-1]
        if kind == last.kind:
            if (px > last.price) if kind == "H" else (px < last.price):
                out[-1] = Swing(kind, px, b, kn)
            continue
        if np.isnan(a[b]) or abs(px - last.price) < k * a[b]:
            continue
        last.final = kn
        out.append(Swing(kind, px, b, kn))
    return out


def labelled(high, low, close, pivot_n, atr_n, k_ext, k_int):
    """SW2: the internal-filter swings, each labelled EXTERNAL when the external-filter set holds the same extreme (kind, bar), else
    INTERNAL; plus the external set itself. Returns (external, all_labelled)."""
    ext = swings(high, low, close, pivot_n, atr_n, k_ext)
    key = {(s.kind, s.bar) for s in ext}
    allv = swings(high, low, close, pivot_n, atr_n, k_int)
    for s in allv:
        s.label = "EXTERNAL" if (s.kind, s.bar) in key else "INTERNAL"
    return ext, allv


@dataclass
class TrendState:
    trend: str = UNKNOWN
    choch: str = None             # the direction a pending CHoCH points to (None = none)
    choch_bar: int = None
    protect: float = None         # the protecting external swing price of the current trend
    events: list = field(default_factory=list)   # [(bar, "CHoCH" / "BOS" / "RANGE" / "TREND", text)]


def _structure(fin):
    hs = [s.price for s in fin if s.kind == "H"]
    ls = [s.price for s in fin if s.kind == "L"]
    if len(hs) < 2 or len(ls) < 2:
        return UNKNOWN
    up = hs[-1] > hs[-2] and ls[-1] > ls[-2]
    down = hs[-1] < hs[-2] and ls[-1] < ls[-2]
    return UP if up else DOWN if down else RANGE


def trend(close, ext):
    """SW3 per bar from FINAL external swings: returns (trend per bar [UP / DOWN / RANGE / TRANSITION / UNKNOWN], CHoCH direction per
    bar while in TRANSITION [str | None], events, protecting swing price per bar)."""
    c = np.asarray(close, float)
    st = TrendState()
    tr, ch, pr = [], [], []
    for t in range(len(c)):
        fin = [s for s in ext if s.final is not None and s.final <= t]
        struct = _structure(fin)
        lastH = next((s for s in reversed(fin) if s.kind == "H"), None)
        lastL = next((s for s in reversed(fin) if s.kind == "L"), None)
        if st.trend in (UNKNOWN, RANGE):
            if struct in (UP, DOWN):
                st.events.append((t, "TREND", f"structure {struct} (last two highs and lows)"))
                st.trend = struct
            elif struct == RANGE and st.trend == UNKNOWN:
                st.trend = RANGE
                st.events.append((t, "RANGE", "mixed structure"))
        elif st.trend in (UP, DOWN):
            up = st.trend == UP
            prot = lastL if up else lastH
            st.protect = None if prot is None else prot.price
            if prot is not None and ((c[t] < prot.price) if up else (c[t] > prot.price)):
                st.trend = TRANSITION
                st.choch, st.choch_bar = (DOWN if up else UP), t
                st.events.append((t, "CHoCH", f"close through the protecting {'low' if up else 'high'} {prot.price:,.2f} ⇒ TRANSITION"))
        else:                                                              # TRANSITION: a BOS either way ends it (DECISIONS 111)
            new_up = st.choch == UP
            # the CHoCH direction: the last external swing of that side made AFTER the CHoCH (the broken one is behind price);
            # the other side: the last external swing of that side (any) — a CLOSE beyond either is the BOS; a wick is not
            ref_new = next((s for s in reversed(fin) if s.bar >= st.choch_bar and s.kind == ("H" if new_up else "L")), None)
            ref_oth = next((s for s in reversed(fin) if s.kind == ("L" if new_up else "H")), None)
            if ref_new is not None and ((c[t] > ref_new.price) if new_up else (c[t] < ref_new.price)):
                st.events.append((t, "BOS", f"close {c[t]:,.2f} beyond the last external {'high' if new_up else 'low'} "
                                            f"{ref_new.price:,.2f} ⇒ {st.choch}"))
                st.trend, st.choch, st.choch_bar = st.choch, None, None
            elif ref_oth is not None and ((c[t] < ref_oth.price) if new_up else (c[t] > ref_oth.price)):
                to = DOWN if new_up else UP
                st.events.append((t, "BOS", f"close {c[t]:,.2f} beyond the last external {'low' if new_up else 'high'} "
                                            f"{ref_oth.price:,.2f} ⇒ {to}"))
                st.trend, st.choch, st.choch_bar = to, None, None
        tr.append(st.trend)
        ch.append(st.choch)
        pr.append(st.protect)
    return tr, ch, st.events, pr


@dataclass
class TFState:
    known_at: object              # the close of the own-TF bar this state is read at (the last COMPLETED bar)
    trend: str
    choch: str = None             # TRANSITION: the direction of the CHoCH
    protect: float = None
    band: tuple = None            # RANGE / TRANSITION: (last final external low, last final external high) — the range edges
    bar: int = -1                 # the own-TF bar index


def tf_states(df, s, k_ext=None):
    """SW1–SW3 on one TF's own bars (all history given). Returns (states per bar [TFState], external swings, labelled swings).
    known_at = the bar's close (daily.known_at_of) — a reader at time ts uses the last state known by ts (`state_at`)."""
    from atp_private.trade_engine.decision3 import daily as DD
    from atp_private.trade_engine.decision3 import history as HI
    x = HI.traded(df)                                                    # M56 E4 (A4): a data-problem bar reads as traded price only
    H, L, C = (x[k].to_numpy(float) for k in ("high", "low", "close"))   # (an auction-extended close inside its traded range)
    k_ext = s["sw_ext_atr"] if k_ext is None else k_ext
    ext, allv = labelled(H, L, C, s["sw_pivot_n"], s["sw_atr_n"], k_ext, s["sw_int_atr"])
    tr, ch, _ev, pr = trend(C, ext)
    kat = DD.known_at_of(df.reset_index(drop=True))
    out = []
    for i in range(len(C)):
        band = None
        if tr[i] in (RANGE, TRANSITION):
            fin = [x for x in ext if x.final is not None and x.final <= i]
            lo = next((x.price for x in reversed(fin) if x.kind == "L"), None)
            hi = next((x.price for x in reversed(fin) if x.kind == "H"), None)
            band = (lo, hi) if lo is not None and hi is not None and lo < hi else None
        out.append(TFState(kat[i], tr[i], ch[i], pr[i], band, i))
    return TFStates(out), ext, allv


class TFStates(list):
    """The per-bar states of one TF, with their known_at keys for a bisect (`state_at`)."""

    def __init__(self, xs):
        super().__init__(xs)
        self.keys = [x.known_at for x in xs]


def state_at(states, ts):
    """The last TFState known at ts (known_at ≤ ts); none ⇒ UNKNOWN."""
    import bisect
    import pandas as pd
    keys = getattr(states, "keys", None)
    if not isinstance(keys, list):
        keys = [x.known_at for x in states]
    j = bisect.bisect_right(keys, pd.Timestamp(ts)) - 1
    return states[j] if j >= 0 else TFState(None, UNKNOWN)
