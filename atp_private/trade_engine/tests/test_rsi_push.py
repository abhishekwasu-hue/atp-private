"""C (RSI, layer 5; DECISIONS 65): the regular divergence on the 15M turns inside the move — synthetic candles, both mirrors.

  • C1 every turn the finest structure confirms is a push (a close through the push candle — a wick is no turn);
  • C2 the RSI at a push = the RSI at the bar of the price extreme (a higher RSI elsewhere in the push is never used);
  • C3 a second push into the first push candle's wick-to-body band = equal (higher-or-equal); RSI must be STRICTLY lower;
  • C4 always the most recent consecutive pair — an older ✓ never survives a newer ✗;
  • C5 the forming push counts once it reaches the last push, re-read every bar (cut = full), never from a gap-open first push."""
import types

import numpy as np
import pandas as pd
import pytest

from atp_private.trade_engine.decision3 import rsi_push as RP

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])


def _V(bars, mirror, days=None):
    """bars: [(o, h, l, c)] of a move UP into a supply (pushes = highs); mirror ⇒ the same move DOWN into a demand."""
    if mirror:
        bars = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in bars]
    O, H, L, C = (np.array(x, float) for x in zip(*bars))
    ts = pd.date_range("2030-01-07 09:15", periods=len(bars), freq="15min")
    if days:                                                           # a new session from this bar on
        ts = ts.where(np.arange(len(bars)) < days, ts + pd.Timedelta(days=1))
    return types.SimpleNamespace(levels=types.SimpleNamespace(A={"open": O, "high": H, "low": L, "close": C}), _ts=ts.to_numpy())


UP2 = [(100, 101, 99, 100.5), (100.5, 103, 100, 102.5), (102.5, 106, 102, 105.5),    # 0 move start · 1–2 push 1 (top 106 at bar 2)
       (105, 105.5, 101, 101.5), (101.5, 102, 100.5, 101.8),                         # 3 closes below bar 2's low ⇒ turn · 4 pullback low
       (101.8, 104.5, 101.6, 104.2), (104.2, 108, 104, 107.5),                       # 5 closes above bar 4's high ⇒ push 2 (top 108)
       (107.4, 107.6, 103, 103.4), (103.4, 104, 102.8, 103.6)]                       # 7 closes below bar 6's low ⇒ turn


def _rsi(n, at, mirror):
    r = np.full(n, 50.0)
    for b, v in at.items():
        r[b] = v
    return 100 - r if mirror else r


@MIRRORS
def test_c1_every_close_through_the_push_candle_is_a_turn(mirror):
    d = 1 if mirror else -1
    ps, forming = RP.turns(_V(UP2, mirror).levels.A, 0, len(UP2) - 1, d)
    assert [b for b, _ in ps] == [2, 6] and [k for _, k in ps] == [3, 7] and forming is None
    wick = [list(b) for b in UP2]
    wick[3] = [105, 105.5, 101, 102.5] if not mirror else wick[3]       # bar 3 only wicks below bar 2's low, closes back above it
    if not mirror:
        ps2, _ = RP.turns(_V([tuple(b) for b in wick], False).levels.A, 0, 3, d)
        assert ps2 == []                                                # a wick is no turn (M51)


@MIRRORS
def test_c2_c4_rsi_at_the_extreme_bar_and_the_latest_pair(mirror):
    d = 1 if mirror else -1
    V = _V(UP2, mirror)
    rsi = _rsi(len(UP2), {1: 80, 2: 70, 5: 75, 6: 64}, mirror)          # the segment's RSI peaks (bars 1, 5) are never the push RSI
    r = RP.read(V, len(UP2) - 1, d, 0, rsi, np.zeros(len(UP2)))
    assert r["found"] and r["pair"]["L1"]["bar"] == 2 and r["pair"]["L2"]["bar"] == 6
    assert r["pair"]["kind"] == "true_extreme" and r["statements"][0].startswith("regular ")
    assert (r["pair"]["L1"]["rsi"], r["pair"]["L2"]["rsi"]) == ((70, 64) if not mirror else (30, 36))
    more = UP2 + [(103.6, 105, 103.5, 104.8), (104.8, 109, 104.6, 108.8), (108.7, 108.8, 104, 104.2)]   # push 3: 109 at bar 10, RSI up
    rsi3 = _rsi(len(more), {2: 70, 6: 64, 10: 69}, mirror)
    r3 = RP.read(_V(more, mirror), len(more) - 1, d, 0, rsi3, np.zeros(len(more)))
    assert not r3["found"] and r3["pair"]["L1"]["bar"] == 6 and r3["pair"]["L2"]["bar"] == 10   # the older ✓ (2 → 6) is gone


@MIRRORS
def test_c3_equal_push_into_the_band_counts_and_rsi_must_be_strictly_lower(mirror):
    d = 1 if mirror else -1
    eq = [list(b) for b in UP2]
    eq[6] = [104.2, 105.8, 104, 105.6]                                  # top 105.8: below 106 but into bar 2's body top (105.5)
    eq[7] = [105.5, 105.6, 103, 103.4]
    V = _V([tuple(b) for b in eq], mirror)
    n = len(eq)
    r = RP.read(V, n - 1, d, 0, _rsi(n, {2: 70, 6: 64}, mirror), np.zeros(n))
    assert r["found"] and r["pair"]["price_rel"] == ("equal high" if not mirror else "equal low")
    assert r["pair"]["kind"] == "equal_band" and "equal-band" in r["statements"][0]           # C5: labelled apart from a true HH / LL
    r_eq = RP.read(V, n - 1, d, 0, _rsi(n, {2: 70, 6: 70}, mirror), np.zeros(n))
    assert not r_eq["found"] and "equal" in r_eq["pair"]["reason"]      # equal RSI is no divergence (P08)
    low = [list(b) for b in UP2]
    low[6] = [104.2, 105.2, 104, 105.0]                                  # top 105.2: short of the band ⇒ a lower high
    low[7] = [105.0, 105.1, 103, 103.4]
    r_lo = RP.read(_V([tuple(b) for b in low], mirror), n - 1, d, 0, _rsi(n, {2: 70, 6: 60}, mirror), np.zeros(n))
    assert not r_lo["found"] and r_lo["pair"]["price_rel"] == ("lower high" if not mirror else "higher low")


@MIRRORS
def test_c5_forming_push_reaches_the_last_push_cut_equals_full_never_a_gap_open_first_push(mirror):
    d = 1 if mirror else -1
    run = UP2[:6] + [(104.2, 107, 104, 106.8)]                            # bar 6 is still rising (no close through it yet)
    n = len(run)
    rsi = _rsi(n, {2: 70, 6: 62}, mirror)
    r = RP.read(_V(run, mirror), n - 1, d, 0, rsi, np.zeros(n))
    assert r["found"] and r["pair"]["status"] == "forming" and r["pair"]["L2"]["push"] == "forming"
    later = run + [(106.8, 107.2, 103, 103.4), (103.4, 104, 102.8, 103.6)]   # the bars after t (a full day): never read at t
    full = RP.read(_V(later, mirror), n - 1, d, 0, _rsi(len(later), {2: 70, 6: 62}, mirror), np.zeros(len(later)))
    assert full["pair"] == r["pair"]                                      # bars ≤ t only: a cut replay reads the same
    short = UP2[:6]                                                       # bar 5 tops at 104.5: short of push 1 ⇒ not a push yet
    rs = RP.read(_V(short, mirror), 5, d, 0, _rsi(6, {2: 70, 5: 60}, mirror), np.zeros(6))
    assert rs["pair"] is None and not rs["found"]
    g = [list(b) for b in run]
    g[2] = [104, 106, 103.5, 105.5]                                       # push 1's top candle opens a new session above bar 1's high
    gap = RP.read(_V([tuple(b) for b in g], mirror, days=2), n - 1, d, 0, rsi, np.zeros(n))
    assert not gap["found"] and "gap-open" in gap["pair"]["reason"]


@MIRRORS
def test_pairs_never_cross_data_segments(mirror):
    d = 1 if mirror else -1
    n = len(UP2)
    seg = np.where(np.arange(n) < 4, 0, 1)
    r = RP.read(_V(UP2, mirror), n - 1, d, 0, _rsi(n, {2: 70, 6: 64}, mirror), seg)
    assert not r["found"] and "segments" in r["pair"]["reason"]
