"""decision3/rsi_push.py — C (RSI, layer 5; owner order C1–C8, DECISIONS 65): the regular RSI divergence INSIDE the move into the zone,
read on the 15M chart's own turns. Evidence only — never a gate, never a trigger (V22.rsi_divergence returns it as zone evidence).

  • C1 the push list: every turn the finest structure confirms inside the move is a push. A push high (mirror: low) is confirmed when a
    later candle CLOSES below the low of the push's extreme candle (the pullback took out that candle — M51: a close, never a wick); the
    pullback's own low is confirmed the same way (a close above its candle's high) or when price trades beyond the push again; then the
    next push starts. No number: the swing engine's degrees (σ-scaled) missed clear 15M turns (C1: E03, E07, E08, E13, E14).
  • C2 the RSI at a push = the RSI AT THE BAR OF THE PRICE EXTREME (one convention at every degree), never the segment's RSI extreme.
  • C3 "equal": a second push that trades into the wick-to-body band of the first push's extreme candle counts as higher-or-equal
    (mirror for lows); a regular divergence needs RSI STRICTLY lower (mirror: higher).
  • C4 always the most recent consecutive pair — the newest push against the one right before it; an older ✓ never survives a newer ✗.
  • C5 the forming push (L5-b): the running extreme after the last confirmed pullback, marked "forming", re-read every bar (dropped
    when it disappears); its first push is a real swing with a pullback (always, by C1) and never a gap-open candle.
  • C8 the judged pair is returned (`pair`) so the RSI pane draws exactly it, with its values; never across data segments.
  • C5 (owner order 28 Oct) an equal-band pair is labelled apart (`pair.kind` equal_band / true_extreme, "equal-band divergence").
`div_degree_rule` "zone" = the earlier degree read (what-if). No look-ahead: bars ≤ t only."""
import numpy as np
import pandas as pd

RULE = "15M turns (every turn the finest structure confirms)"


def turns(A, start, t, d):
    """The confirmed pushes of the move from bar `start` (exclusive) to t, trade side d (−1 = bear call ⇒ the pushes are highs, +1 ⇒
    lows): [(extreme bar, confirm bar)], plus the forming push (extreme bar) after the last confirmed pullback, or None."""
    H, L, C = A["high"], A["low"], A["close"]
    up = d < 0                                                        # the move into a supply runs up: its pushes are highs
    ext = H if up else L
    opp = L if up else H

    def beyond(a, b):                                                 # a is a further (or equal ⇒ the later bar) push extreme than b
        return a >= b if up else a <= b
    pushes, m, q, state = [], None, None, "push"
    for i in range(int(start) + 1, int(t) + 1):
        if state == "push":
            if m is None or beyond(ext[i], ext[m]):
                m = i
            elif (C[i] < L[m]) if up else (C[i] > H[m]):            # the pullback closed through the push candle ⇒ a turn
                pushes.append((m, i))
                state, q = "pull", None
                for j in range(m + 1, i + 1):                         # the pullback's extreme so far (later bar on a tie)
                    if q is None or (opp[j] <= opp[q] if up else opp[j] >= opp[q]):
                        q = j
        else:
            if (opp[i] <= opp[q]) if up else (opp[i] >= opp[q]):
                q = i
            if ((C[i] > H[q]) if up else (C[i] < L[q])) or beyond(ext[i], ext[m]) and ext[i] != ext[m]:
                state, m = "push", None                               # the pullback turned ⇒ the next push starts after its extreme
                for j in sorted({*range(q + 1, i + 1), i}):            # (one candle can make the pullback's low AND the new push)
                    if m is None or beyond(ext[j], ext[m]):
                        m = j
    forming = m if state == "push" and pushes and m is not None and m > pushes[-1][0] else None
    return pushes, forming


def _gap_open(A, ts, i, up):
    """A gap-open candle: the session's first candle opening beyond the previous candle's range (no overlap) in the push direction."""
    if i <= 0 or pd.Timestamp(ts[i]).date() == pd.Timestamp(ts[i - 1]).date():
        return False
    return A["open"][i] > A["high"][i - 1] if up else A["open"][i] < A["low"][i - 1]


def read(V, t, d, move_from, rsi, seg):
    """The layer-5 read at bar t: {found, divergences, pair, degree, pushes, statements} (V22.rsi_divergence's shape)."""
    A, ts = V.levels.A, V._ts
    side = "bear" if d < 0 else "bull"
    up = d < 0
    word = "highs" if up else "lows"
    mf = int(move_from)
    ps, forming = turns(A, mf, t, d)
    pts = [(b, "confirmed", k) for b, k in ps]
    ext = A["high"] if up else A["low"]
    if forming is not None and ps:
        b0 = ps[-1][0]
        body0 = max(A["open"][b0], A["close"][b0]) if up else min(A["open"][b0], A["close"][b0])
        if (ext[forming] >= body0) if up else (ext[forming] <= body0):   # a push only once it reaches the last push (C3 band); a
            pts.append((forming, "forming", int(t)))                    # bounce still short of it leaves the latest confirmed pair
        else:
            forming = None
    base = {"rule": RULE, "degree": "15M", "pushes": {"15M": len(ps)}, **({"forming_push": {"15M": {
        "time": str(pd.Timestamp(ts[forming])), "price": float((A["high"] if up else A["low"])[forming]), "push": "forming"}}}
        if forming is not None else {})}
    if len(pts) < 2:
        return {**base, "found": False, "divergences": [], "pair": None,
                "statements": [f"no {side} divergence: the move into the zone shows fewer than two pushes ({word}) on the 15M turns "
                               f"(from {str(pd.Timestamp(ts[mf]))[:16]})"]}
    (b1, s1, k1), (b2, s2, k2) = pts[-2], pts[-1]                      # C4: always the most recent consecutive pair
    p1, p2 = float(ext[b1]), float(ext[b2])
    body1 = max(A["open"][b1], A["close"][b1]) if up else min(A["open"][b1], A["close"][b1])
    if (p2 > p1) if up else (p2 < p1):
        rel = "higher high" if up else "lower low"
    elif (p2 >= body1) if up else (p2 <= body1):                       # C3: into the first push candle's wick-to-body band
        rel = "equal high" if up else "equal low"
    else:
        rel = "lower high" if up else "higher low"
    r1, r2 = float(rsi[b1]), float(rsi[b2])                            # C2: the RSI at the bar of each price extreme

    def pt(b, p, r, st):
        return {"bar": int(b), "time": str(pd.Timestamp(ts[b])), "price": round(p, 2), "rsi": round(r, 2) if np.isfinite(r) else None,
                "push": st}
    pair = {"degree": "15M", "status": s2, "price_rel": rel, "L1": pt(b1, p1, r1, s1), "L2": pt(b2, p2, r2, s2),
            "rsi_diff": round(r2 - r1, 2) if np.isfinite(r1) and np.isfinite(r2) else None}
    why = None
    if seg[b1] != seg[b2]:
        why = "the two pushes are in different data segments"
    elif not (np.isfinite(r1) and np.isfinite(r2)):
        why = "RSI not available at a push (warm-up)"
    elif rel in ("lower high", "higher low"):
        why = f"price made a {rel} ({p2:,.2f} vs {p1:,.2f}) — no new extreme"
    elif (r2 >= r1) if up else (r2 <= r1):                            # C3: strictly lower (mirror: higher)
        why = f"RSI did not diverge ({r1:.2f} → {r2:.2f}{', equal' if r2 == r1 else ''})"
    elif s2 == "forming" and _gap_open(A, ts, b1, up):
        why = "the first push is a gap-open candle (C5)"
    kind = "equal_band" if rel.startswith("equal") else "true_extreme"   # C5 (28 Oct): an equal-band pair is reported apart from a
    pair.update(is_div=why is None, reason=why, kind=kind)                # true higher-high / lower-low divergence (owner allows it)
    name = ("equal-band " if kind == "equal_band" else "regular ") + side + " divergence"
    st = (f"{name if why is None else 'no ' + side + ' divergence'} on the latest two pushes: price "
          f"{rel} {p1:,.0f} → {p2:,.0f}, RSI {r1:.1f} → {r2:.1f}" + (" (forming)" if s2 == "forming" else "") + ("" if why is None
                                                                                                          else f" — {why}"))
    return {**base, "found": why is None, "divergences": [pair] if why is None else [], "pair": pair, "statements": [st]}
