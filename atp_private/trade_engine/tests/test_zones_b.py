"""B — zones by the standard supply / demand definition (owner order 28 Oct) — synthetic candles, both mirrors.

  • B1 a zone's band = the WHOLE base: distal = the base candles' wick extreme, proximal = their far body edge (zones_z.base_band);
    from the departure close only (before it the swing band of a level — no look-ahead);
  • B2 the departure is structural: the leg-out must close beyond the latest prior swing (none in the data ⇒ the old test alone);
  • B3 a Daily / Weekly band counts as confluence only where its 1H origin base overlaps (Levels.h1_origin)."""
import types

import numpy as np
import pandas as pd
import pytest

from atp_private.trade_engine.decision3 import levels as LV
from atp_private.trade_engine.decision3 import settings as S3
from atp_private.trade_engine.decision3 import zones_z as ZZ
from atp_private.trade_engine.tests.test_zones_z import IMPULSE, LEG_IN, _lv

S = S3.load()
MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["supply", "demand"])


def _m(x, mirror):
    return 200 - x if mirror else x


@MIRRORS
def test_b1_band_is_the_whole_base_distal_wick_proximal_far_body(mirror):
    base = [(101.0, 102.6, 100.4, 101.4), (101.4, 103.0, 100.8, 101.0)]  # two small-body base candles; the second holds the high
    lv, ts = _lv(LEG_IN + base + IMPULSE + [(90.5, 91, 89.5, 90)], mirror)
    t, z = ZZ.gate(lv, "resistance" if not mirror else "support", "1H", ts[4], 19, S)
    assert t is not None and z["base_n"] == 2
    lo, hi = z["band_zone"]                                              # supply: lowest body bottom 101.0 … highest high 103.0;
    assert (lo, hi) == pytest.approx((101.0, 103.0) if not mirror else (_m(103.0, True), _m(101.0, True)))   # demand: the mirror
    one = ZZ.base_band(*(np.array([c[k] for c in base], float) for k in range(4)), [1], -1)
    assert one == pytest.approx((101.0, 103.0))                          # one base candle: its far body edge to its wick


@MIRRORS
def test_b2_the_leg_out_must_break_a_prior_swing(mirror):
    leg_in = [(99.0, 99.5, 97.0, 97.5), (97.5, 98.0, 95.0, 96.0), (96.0, 98.5, 95.6, 98.2),   # a swing low 95.0 before the base
              (98.2, 101.5, 98.0, 101.2)]
    base = [(101.2, 103.0, 100.6, 101.5)]
    shallow = [(101.5, 101.6, 97.0, 97.2), (97.2, 97.4, 95.5, 95.6), (95.6, 96.6, 95.2, 96.4), (96.4, 97, 95.8, 96.8),
               (96.8, 97.2, 96.0, 96.5), (96.5, 97, 96, 96.6)]           # strong, ≥ ATR away, but never closes below 95.0
    lv, ts = _lv(leg_in + base + shallow, mirror)
    role = "resistance" if not mirror else "support"
    t, why = ZZ.gate(lv, role, "1H", ts[4], 23, S)
    assert t is None and why == ZZ.Z3_NO_BOS
    deep = shallow[:2] + [(95.6, 95.8, 93.0, 93.4)] + shallow[3:]       # the third candle closes below the swing low ⇒ a zone from it
    lv2, ts2 = _lv(leg_in + base + deep, mirror)
    t2, z2 = ZZ.gate(lv2, role, "1H", ts2[4], 23, S)
    assert t2 is not None and pd.Timestamp(z2["departure_ts"]) == ts2[7]
    lv3, ts3 = _lv(LEG_IN + base + IMPULSE + [(90.5, 91, 89.5, 90)], mirror)   # no prior swing in the data ⇒ the ATR test alone
    assert ZZ.gate(lv3, role, "1H", ts3[3], 19, S)[0] is not None


def test_b1_band_change_waits_for_the_departure_close():
    """The level is born with its swing band; the whole-base band only from the departure close (Levels._band_due)."""
    L = types.SimpleNamespace(lo=101.0, hi=103.0, born_bar=5, bands=[(5, 101.0, 103.0)], z={"zone": True})
    me = types.SimpleNamespace(_band_due={})
    LV.Levels._base_band(me, L, {"band_zone": (100.0, 103.0)}, 9, LV.RES)
    assert (L.lo, L.hi) == (101.0, 103.0) and me._band_due == {9: [(L, 100.0, 103.0)]}
    L2 = types.SimpleNamespace(lo=101.0, hi=103.0, born_bar=9, bands=[(9, 101.0, 103.0)], z={"zone": True})
    LV.Levels._base_band(me, L2, {"band_zone": (100.0, 103.0)}, 9, LV.RES)
    assert (L2.lo, L2.hi) == (100.0, 103.0) and L2.bands[-1] == (9, 100.0, 103.0)
    narrow = types.SimpleNamespace(lo=99.0, hi=104.0, born_bar=9, bands=[(9, 99.0, 104.0)], z={"zone": True})
    LV.Levels._base_band(me, narrow, {"band_zone": (100.0, 103.0)}, 9, LV.RES)
    assert (narrow.lo, narrow.hi) == (99.0, 104.0)                       # never narrower than the swing band


@pytest.mark.usefixtures("wick_level_bands")   # the fixture was built on the earlier band (Abhi 29 Oct: level_band_rule)
def test_b3_daily_band_counts_only_through_its_1h_origin_base():
    h1 = pd.DataFrame({"timestamp": pd.date_range("2030-01-07 09:15", periods=7, freq="h"),
                       "open": [100, 101, 103, 104, 102, 101, 100.5], "high": [101.5, 103.5, 104.5, 106.0, 104.0, 102.0, 101.0],
                       "low": [99.5, 100.8, 102.6, 103.4, 101.6, 100.4, 100.0], "close": [101, 103, 104, 103.8, 101.8, 100.6, 100.4]})
    me = types.SimpleNamespace(h1=h1, h1_history=None)
    D = types.SimpleNamespace(id=1, tf="D", base_ts=pd.Timestamp("2030-01-07"), role0=LV.RES, lo=99.5, hi=106.0)
    rf = LV.Levels.h1_origin(me, D)
    assert rf == pytest.approx((104.0, 106.0))                           # the 1H candle holding the day's high: wick to body
    assert LV.Levels.h1_origin(me, types.SimpleNamespace(id=2, tf="D", base_ts=None, role0=LV.RES, lo=1, hi=2)) is None
