"""SW (DECISIONS 92 / 98 / 109): swings + trend per TF — synthetic, both mirrors.

  • SW1: a swing needs a confirmed pivot AND ≥ k × ATR from the previous opposite swing; the newest is provisional until the next
    opposite swing passes the filter (nothing reads it before);
  • SW2: the larger filter gives the EXTERNAL set, the tighter one adds INTERNAL swings;
  • SW3: HH + HL = UP; a close through the protecting low = CHoCH ⇒ TRANSITION (range rules); a close beyond the first low made after
    the CHoCH = BOS ⇒ DOWN; a close back above the old trend's last high ⇒ UP again; no look-ahead.
"""
import numpy as np
import pandas as pd
import pytest

from atp_private.trade_engine.decision3 import settings as S3
from atp_private.trade_engine.decision3 import sw as SW

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["up_first", "down_first"])
S = {**S3.DEFAULTS, "sw_atr_n": 3, "sw_pivot_n": 2, "sw_ext_atr": 3.0, "sw_int_atr": 1.0}


def _path(points, mirror=False):
    c = [float(points[0])]
    for a, b in zip(points, points[1:]):
        step = 1.0 if b > a else -1.0
        c += [float(x) for x in np.arange(a + step, b + step / 2, step)]
    c = np.array(c)
    if mirror:
        c = 2 * 100.0 - c
    return c, c + 0.5, c - 0.5


UP_LEGS = [100, 112, 104, 120, 110, 126]                                   # HH / HL ⇒ UP


@MIRRORS
def test_swings_need_the_atr_filter_and_the_newest_is_provisional(mirror):
    c, h, lo = _path(UP_LEGS + [124, 128, 126], mirror)                    # 126 → 124: a 2-point dip (< 3 ATR) is no swing
    ext = SW.swings(h, lo, c, S["sw_pivot_n"], S["sw_atr_n"], S["sw_ext_atr"])
    kinds = [x.kind for x in ext]
    assert kinds == (["H", "L", "H", "L", "H"] if not mirror else ["L", "H", "L", "H", "L"])   # the start is no pivot (no bars before)
    assert ext[-1].final is None and all(x.final is not None for x in ext[:-1])   # the last extreme is provisional
    top = 128.5 if not mirror else 2 * 100.0 - 128 - 0.5
    assert ext[-1].price == pytest.approx(top)                             # the dip did not split the leg: the provisional swing moved on
    ext2, allv = SW.labelled(h, lo, c, S["sw_pivot_n"], S["sw_atr_n"], S["sw_ext_atr"], S["sw_int_atr"])
    assert {x.label for x in allv} >= {"EXTERNAL"} and len(allv) >= len(ext2)


@MIRRORS
def test_choch_is_transition_and_the_bos_sets_the_new_trend(mirror):
    up, down = ("UP", "DOWN") if not mirror else ("DOWN", "UP")
    c, h, lo = _path(UP_LEGS + [106, 116, 98], mirror)                     # close through the HL 110 ⇒ CHoCH; LH 116; below 106 ⇒ BOS
    ext = SW.swings(h, lo, c, S["sw_pivot_n"], S["sw_atr_n"], S["sw_ext_atr"])
    tr, ch, ev, pr = SW.trend(c, ext)
    kinds = [k for _, k, _ in ev]
    assert up in tr and "TRANSITION" in tr and tr[-1] == down
    i_ch = next(b for b, k, _ in ev if k == "CHoCH")
    i_bos = next(b for b, k, _ in ev if k == "BOS")
    assert i_ch < i_bos and all(x == "TRANSITION" for x in tr[i_ch:i_bos]) and ch[i_ch] == down
    assert kinds.count("CHoCH") == 1 and tr[i_ch - 1] == up


@MIRRORS
def test_a_close_back_beyond_the_old_extreme_restores_the_old_trend(mirror):
    up = "UP" if not mirror else "DOWN"
    c, h, lo = _path(UP_LEGS + [106, 130], mirror)                         # CHoCH, then straight back above the HH 126
    ext = SW.swings(h, lo, c, S["sw_pivot_n"], S["sw_atr_n"], S["sw_ext_atr"])
    tr, ch, ev, _ = SW.trend(c, ext)
    assert "TRANSITION" in tr and tr[-1] == up
    assert [k for _, k, _ in ev].count("BOS") == 1 and tr[next(b for b, k, _ in ev if k == "BOS")] == up


@MIRRORS
def test_no_look_ahead_a_cut_at_every_bar_gives_the_same_trend(mirror):
    c, h, lo = _path(UP_LEGS + [106, 116, 98], mirror)
    ext = SW.swings(h, lo, c, S["sw_pivot_n"], S["sw_atr_n"], S["sw_ext_atr"])
    full, *_ = SW.trend(c, ext)
    for t in range(len(c)):
        e = SW.swings(h[:t + 1], lo[:t + 1], c[:t + 1], S["sw_pivot_n"], S["sw_atr_n"], S["sw_ext_atr"])
        assert SW.trend(c[:t + 1], e)[0][-1] == full[t]


def test_tf_states_known_at_close_and_transition_band():
    c, h, lo = _path(UP_LEGS + [106, 116, 98])
    ts = pd.bdate_range("2030-01-01", periods=len(c))
    df = pd.DataFrame({"timestamp": ts, "open": c, "high": h, "low": lo, "close": c})
    st, ext, _ = SW.tf_states(df, S)
    j = next(i for i, x in enumerate(st) if x.trend == "TRANSITION")
    assert st[j].band is not None and st[j].band[0] < st[j].band[1]
    assert SW.state_at(st, st[j].known_at).trend == "TRANSITION"
    assert SW.state_at(st, st[j].known_at - pd.Timedelta(minutes=1)).trend == st[j - 1].trend   # the last COMPLETED bar only
    assert SW.state_at(st, ts[0] - pd.Timedelta(days=1)).trend == "UNKNOWN"


@MIRRORS
def test_in_transition_a_close_beyond_the_last_external_high_is_the_bos(mirror):
    """DECISIONS 111: after a CHoCH down (low 106), the rally makes an external LH (116), a higher low (109) follows, then a CLOSE
    above the LH 116 is the BOS ⇒ UP (the old high 126 is not needed); a wick above it that closes back is a sweep ⇒ still TRANSITION."""
    up = "UP" if not mirror else "DOWN"
    c, h, lo = _path(UP_LEGS + [106, 116, 109, 119], mirror)               # LH 116 after the CHoCH; 119 closes above it
    ext = SW.swings(h, lo, c, S["sw_pivot_n"], S["sw_atr_n"], S["sw_ext_atr"])
    tr, ch, ev, _ = SW.trend(c, ext)
    bos = [b for b, k, _ in ev if k == "BOS"]
    assert "TRANSITION" in tr and tr[-1] == up and len(bos) == 1
    lh = 116.0 if not mirror else 2 * 100.0 - 116.0
    assert ((c[bos[0]] > lh) if not mirror else (c[bos[0]] < lh)) and tr[bos[0] - 1] == "TRANSITION"
    c2, h2, lo2 = _path(UP_LEGS + [106, 116, 109, 115], mirror)            # closes stay below 116 …
    k = len(c2) - 1
    if not mirror:
        h2[k] = 117.5                                                      # … one wick through it (a sweep)
    else:
        lo2[k] = 2 * 100.0 - 117.5
    tr2, *_ = SW.trend(c2, SW.swings(h2, lo2, c2, S["sw_pivot_n"], S["sw_atr_n"], S["sw_ext_atr"]))
    assert tr2[-1] == "TRANSITION"
