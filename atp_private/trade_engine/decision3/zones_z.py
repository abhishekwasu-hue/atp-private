"""Z — zone construction (owner order M7, DECISIONS 81; INBOX 24 Oct "ZONE CONSTRUCTION" Z1–Z8). Every area birth of
decision3.levels is CLASSIFIED (DECISIONS 116 — never a gate: the owner's answer key v4 and the 12–13 Oct golden case confirm swing
support / resistance objects that are no supply / demand zone; they stay, labelled "level") on the candles of its OWN timeframe:

  • Z1 base: the base candle is a base candle — its body at most `z_base_body` of its range (the compact candle where buyers / sellers
    acted); the base = that candle plus the overlapping base candles right before it (at most `z_base_max`, reported). Band unchanged
    (wick-to-body, as the birth built it). A data-problem candle is never a base (DECISIONS 84).
  • Z3 departure: within `z_depart_bars` candles after the base, a leg-out candle away from the zone (body at least `z_leg_body` of its
    range, one direction) AND price away from the base by at least `z_depart_atr` × ATR (`z_atr_n`, own TF). A slow overlapping drift
    never reaches both ⇒ no zone.
  • Z4 the object is a ZONE only from the close of the candle that completed the departure (`zone_from`); before that, and
    without a departure, it is a level; no look-ahead.
  • Z2 / Z5 reported, never a filter: the form (rally-base-drop, drop-base-rally, rally-base-rally, drop-base-drop: the leg-in over
    the same window before the base), the departure strength (ATR multiple), the base candle count.
  • Z6 = the existing width flag (snapshot `too_wide`, "check, no trade") + the refined base on the lower TF; Z8 = `_born` never
    merges (Z-1u) — both unchanged.
Research defaults (DECISIONS 113; community supply / demand conventions — base body ≤ 50 %, leg-out body ≥ 60 %, departure ≈ 1.6 ATR
within ≈ 5 bars), provisional, numbers only in settings. `zone_rule` "legacy" = the births as before (what-if)."""
import numpy as np
import pandas as pd

from . import daily as DD


Z3_NONE = "Z3: no impulsive departure (yet)"
Z3_NO_BOS = "Z3: the leg-out broke no prior swing (yet)"


def _broke_prior_swing(f, known, n, j, dep, away, bars, O, H, L, C):
    """B2 (owner order 28 Oct; standard supply / demand): the departure must also be STRUCTURAL — the leg-out closes beyond the latest
    prior own-TF swing on the away side (supply: a swing low before the base; demand: a swing high), within the same departure window.
    A swing = a candle whose low (high) is below (above) both neighbours, confirmed before the base. Returns (bar of the breaking close,
    the swing bar) / (False, swing bar) when the leg-out did not break it / (None, None) when no prior swing is in the data (the
    ATR / leg-body test alone, as before)."""
    ext = L if away < 0 else H
    sw = None
    for i in range(j - 2, 0, -1):                                   # the latest swing confirmed before the base candle
        if (ext[i] < ext[i - 1] and ext[i] <= ext[i + 1]) if away < 0 else (ext[i] > ext[i - 1] and ext[i] >= ext[i + 1]):
            sw = i
            break
    if sw is None:
        return None, None
    for k in range(j + 1, min(j + 1 + bars, len(f))):
        if known[k] >= n:
            break
        if (C[k] < ext[sw]) if away < 0 else (C[k] > ext[sw]):
            return k, sw
    return False, sw


def snapshot_view(z, t):
    """The Z facts readable at bar t (no look-ahead): the zone facts only from the departure close on; before it — or without a
    departure — the same "level" view a replay cut at t computes (only a Z1 / data-problem reason is known at the birth)."""
    if z is None:
        return None
    if z.get("zone") and t >= z.get("zone_from", -1):
        return {**z, "zone": True}
    why = z.get("why") if not z.get("zone") and not str(z.get("why", "")).startswith("Z3") else Z3_NONE
    return {"zone": False, "why": why}


def frame(lv, tf):
    """(candles with open / high / low / close / timestamp, known 15M bar per candle) of the area's own TF — known = the first 15M bar
    whose close is at / after the candle's own close (−1 = known before the window; ≥ n = not closed in the data ⇒ never read)."""
    if tf == "1H":
        f = lv.h1.reset_index(drop=True)
        cnt = np.bincount(lv.h1_of, minlength=len(f))
        full = cnt.max() if len(cnt) else 0
        first = np.array([int(np.flatnonzero(lv.h1_of == j)[0]) for j in range(len(f))], int)
        # a candle holding all its 15M bars is closed at its last one; a short candle (or the data's last, maybe still forming) is
        # closed only once the next candle starts — the same answer in a replay cut at any bar (no look-ahead, no clock rule)
        known = np.array([int(np.flatnonzero(lv.h1_of == j)[-1]) if cnt[j] == full else
                          (first[j + 1] if j + 1 < len(f) else lv.n) for j in range(len(f))], int)
        return f, known
    f = (lv.daily_df if tf == "D" else lv.weekly_df)
    if f is None or not len(f):
        return None, None
    f = f.reset_index(drop=True)
    kat = np.array([np.datetime64(pd.Timestamp(x)) for x in DD.known_at_of(f)])
    be = lv.bar_end.to_numpy()
    known = np.searchsorted(be, kat, side="left").astype(int)
    known[kat <= be[0]] = -1
    return f, known


def _atr(f, n):
    h, l, c = (f[k].to_numpy(float) for k in ("high", "low", "close"))
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(int(n), min_periods=1).mean().to_numpy()


def gate(lv, role, tf, base_ts, t, s, dp_fn=None):
    """Z1 / Z3 / Z4 for one birth known at 15M bar t. Returns (birth bar, info) or (None, reason)."""
    f, known = frame(lv, tf)
    if f is None or base_ts is None:
        return None, "no own-TF candles for the base"
    ts = pd.to_datetime(f["timestamp"]).to_numpy()
    j = int(np.searchsorted(ts, np.datetime64(pd.Timestamp(base_ts)), side="left"))
    if j >= len(f) or pd.Timestamp(ts[j]) != pd.Timestamp(base_ts):
        return None, "base candle not in the own-TF frame"
    if dp_fn is not None and dp_fn(j):
        return None, "data-problem candle (DECISIONS 84)"
    O, H, L, C = (f[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    body, rng = abs(C[j] - O[j]), max(H[j] - L[j], 1e-12)
    if body > float(s["z_base_body"]) * rng:
        return None, f"Z1: base candle body {body / rng:.0%} of its range (> {float(s['z_base_body']):.0%})"
    away = -1 if role == "resistance" else 1                       # supply ⇒ price leaves downward; demand ⇒ upward
    A = _atr(f, s["z_atr_n"])
    need, leg, strong, dep = float(s["z_depart_atr"]) * A[j], float(s["z_leg_body"]), False, None
    for k in range(j + 1, min(j + 1 + int(s["z_depart_bars"]), len(f))):
        if known[k] >= lv.n:                                       # a candle not closed in the data is never read (no look-ahead)
            break
        if (C[k] - O[k]) * away > 0 and abs(C[k] - O[k]) >= leg * max(H[k] - L[k], 1e-12):
            strong = True
        move = (L[j] - L[k]) if away < 0 else (H[k] - H[j])
        if strong and move >= need:
            dep = k
            break
    if dep is None:
        return None, Z3_NONE
    brk, sw = (_broke_prior_swing(f, known, lv.n, j, dep, away, int(s["z_depart_bars"]), O, H, L, C)
               if s.get("z_depart_structure", "bos") == "bos" else (None, None))
    if brk is False:
        return None, Z3_NO_BOS
    if brk is not None:
        dep = max(dep, brk)                                         # the zone from the close that broke the prior swing
    nb = 1                                                          # Z1 report: overlapping base candles right before (≤ z_base_max)
    while nb < int(s["z_base_max"]) and j - nb >= 0:
        i = j - nb
        if not (L[i] <= H[j] and H[i] >= L[j] and abs(C[i] - O[i]) <= float(s["z_base_body"]) * max(H[i] - L[i], 1e-12)):
            break
        nb += 1
    i0 = max(0, j - int(s["z_depart_bars"]))                        # Z2: the leg-in over the same window before the base
    came_up = C[max(0, j - nb)] - O[i0] > 0 if j - nb >= i0 else None
    form = {(-1, True): "rally-base-drop", (-1, False): "drop-base-drop", (1, False): "drop-base-rally",
            (1, True): "rally-base-rally"}.get((away, came_up), "base")
    t_new = max(int(t), int(known[dep]))
    far = (L[j] - min(L[j + 1:dep + 1])) if away < 0 else (max(H[j + 1:dep + 1]) - H[j])
    pre = list(range(j - nb + 1, j + 1))                            # B1: the base known at the birth (the candles up to the base candle)
    post = []                                                       # … and the base candles after it, before the leg-out (known at the
    for k in range(j + 1, dep):                                     # departure close): overlapping the base candle, a base body
        if len(pre) + len(post) >= int(s["z_base_max"]) or not (L[k] <= H[j] and H[k] >= L[j]
                                                                and abs(C[k] - O[k]) <= float(s["z_base_body"]) * max(H[k] - L[k], 1e-12)):
            break
        post.append(k)
    return t_new, {"form": form, "depart_atr": round(float(far / A[j]), 2) if A[j] > 0 else None, "base_candles": nb,
                   "depart_bars": int(dep - j), "departure_ts": str(pd.Timestamp(ts[dep])),
                   "band_birth": base_band(O, H, L, C, pre, away), "band_zone": base_band(O, H, L, C, pre + post, away),
                   "base_n": len(pre) + len(post)}


def base_band(O, H, L, C, idx, away):
    """B1 (owner order 28 Oct; standard supply / demand): the band of the WHOLE base — the distal edge = the base candles' wick extreme
    (supply: the highest high; demand: the lowest low), the proximal edge = their far body edge (supply: the lowest body bottom; demand:
    the highest body top). A base of doji-like candles (no body room) keeps the wick extreme to the nearest body edge."""
    idx = list(idx)
    if away < 0:                                                    # supply: price leaves downward
        hi = float(max(H[i] for i in idx))
        lo = float(min(min(O[i], C[i]) for i in idx))
        return (min(lo, hi), hi)
    lo = float(min(L[i] for i in idx))
    hi = float(max(max(O[i], C[i]) for i in idx))
    return (lo, max(lo, hi))


# M56 E7 (A7): the zone / level call rests on the Z thresholds (z_base_body, z_leg_body, z_depart_atr, z_depart_bars — research
# defaults, REGISTER class "अंदाज") — every label that shows it says so until the owner sets them (answer-key batch 2 questions)
PROVISIONAL = " · Z provisional"


def label(z):
    """Z5 chart-label words: "zone: rally-base-drop, departure 2.3 ATR" (from the departure close on) / "level (no impulsive
    departure)" (DECISIONS 116: a swing support / resistance object that is not a supply / demand zone — kept, never dropped)."""
    if not z:
        return None
    if not z.get("zone"):                                          # the snapshot sets "zone" at its bar (from `zone_from` on)
        return "level (no impulsive departure)" + PROVISIONAL
    return f"zone: {z['form']}" + (f", departure {z['depart_atr']} ATR" if z.get("depart_atr") is not None else "") + PROVISIONAL
