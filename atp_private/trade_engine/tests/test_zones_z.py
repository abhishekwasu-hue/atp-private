"""Z (M7, DECISIONS 81 / 116): zone construction as a classification on the area's own TF candles — synthetic 1H candles, both mirrors.

  • a base candle (small body) + an impulsive leg-out (strong candle away, ≥ z_depart_atr × ATR) ⇒ ZONE from the departure close;
  • a slow overlapping drift away ⇒ LEVEL (no impulsive departure); a large-body base candle ⇒ LEVEL (Z1);
  • form words (rally-base-drop / drop-base-drop …); a candle not closed in the data is never read; the snapshot view hides the zone
    facts before the departure close (no look-ahead)."""
import types

import numpy as np
import pandas as pd
import pytest

from atp_private.trade_engine.decision3 import settings as S3
from atp_private.trade_engine.decision3 import zones_z as ZZ

S = S3.load()
MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["supply", "demand"])


def _lv(candles, mirror):
    """candles: [(o, h, l, c)] of 1H candles, 4 × 15M bars each (the 15M frame only drives the known bars)."""
    if mirror:
        candles = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in candles]
    ts = pd.date_range("2030-01-07 09:15", periods=len(candles), freq="h")
    h1 = pd.DataFrame(candles, columns=["open", "high", "low", "close"]).assign(timestamp=ts)
    h1_of = np.repeat(np.arange(len(candles)), 4)
    be = pd.Series(pd.date_range("2030-01-07 09:30", periods=len(h1_of), freq="15min"))
    return types.SimpleNamespace(h1=h1, h1_of=h1_of, n=len(h1_of), bar_end=be, daily_df=None, weekly_df=None), ts


LEG_IN = [(90, 95, 89, 94), (94, 99, 93, 98), (98, 102, 97, 101)]          # a rally into the base
BASE = [(101, 103, 100, 101.5)]                                           # small body: the base candle
IMPULSE = [(101.5, 101.8, 96, 96.3), (96.3, 96.5, 90, 90.2), (90.2, 91, 89, 90.5)]   # strong candles away
DRIFT = [(101.5, 102.5, 100, 100.8), (100.8, 101.6, 99.5, 100.2), (100.2, 101, 99, 99.6), (99.6, 100.4, 98.6, 99.2),
         (99.2, 100, 98.4, 99.0), (99.0, 99.8, 98.2, 98.8)]                # overlapping, slow


@MIRRORS
def test_impulsive_departure_makes_a_zone_from_its_close(mirror):
    lv, ts = _lv(LEG_IN + BASE + IMPULSE + [(90.5, 91, 89.5, 90)], mirror)
    role = "resistance" if not mirror else "support"
    t, z = ZZ.gate(lv, role, "1H", ts[3], 15, S)
    assert t is not None and z["form"] == ("rally-base-drop" if not mirror else "drop-base-rally")
    dep = int(pd.Timestamp(z["departure_ts"]) == ts[3 + z["depart_bars"]])
    assert dep and t == int(np.flatnonzero(lv.h1_of == 3 + z["depart_bars"])[-1]) and z["depart_atr"] >= S["z_depart_atr"]
    view = {**z, "zone": True, "zone_from": t}
    assert ZZ.snapshot_view(view, t - 1) == {"zone": False, "why": ZZ.Z3_NONE} and ZZ.snapshot_view(view, t)["zone"]
    assert ZZ.label(ZZ.snapshot_view(view, t)).startswith("zone: ") and ZZ.label(ZZ.snapshot_view(view, t - 1)).startswith("level")


@MIRRORS
def test_slow_drift_is_a_level_not_a_zone(mirror):
    lv, ts = _lv(LEG_IN + BASE + DRIFT + [(98.8, 99, 98, 98.5)], mirror)
    t, why = ZZ.gate(lv, "resistance" if not mirror else "support", "1H", ts[3], 15, S)
    assert t is None and why == ZZ.Z3_NONE


@MIRRORS
def test_a_large_body_base_candle_is_a_level(mirror):
    lv, ts = _lv(LEG_IN + [(98, 103, 97.8, 102.8)] + IMPULSE + [(90.5, 91, 89.5, 90)], mirror)
    t, why = ZZ.gate(lv, "resistance" if not mirror else "support", "1H", ts[3], 15, S)
    assert t is None and why.startswith("Z1")


@MIRRORS
def test_a_candle_not_closed_in_the_data_is_never_read(mirror):
    lv, ts = _lv(LEG_IN + BASE + IMPULSE[:2], mirror)                    # the impulse's 2nd candle is the data's last ⇒ maybe forming
    lv.h1_of, lv.n = lv.h1_of[:-2], lv.n - 2                             # cut mid-candle: only 2 of its 4 bars
    lv.bar_end = lv.bar_end[:lv.n]
    t, why = ZZ.gate(lv, "resistance" if not mirror else "support", "1H", ts[3], lv.n - 1, S)
    assert t is None and why == ZZ.Z3_NONE                               # the forming candle's move is not read ⇒ not a zone yet
