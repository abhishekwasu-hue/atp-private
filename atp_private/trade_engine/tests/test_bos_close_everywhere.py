"""M51 (DECISIONS 108 / 110 / 111): ONE meaning of BOS / CHoCH everywhere — a candle CLOSE beyond the swing; a wick beyond that closes
back is a sweep, never a break. The reader's detectors and where each is held to it:

  • decision3.sw.trend (Daily side, BOS / CHoCH)            — tests/test_sw.py (… _is_the_bos: the wick is a sweep)
  • decision3.method.ltf_choch (c1, 5M CHoCH)                 — tests/test_decision3_confirm.py::test_wick_beyond_swing_is_not_choch
  • bots_common level reaction c1                            — tests/test_level_reaction_c1.py::test_wick_above_lh_only_is_no_choch
  • areas BREAK (levels._structural_break, trendline follow-through) — tests/test_lifecycle_follow_through.py / test_break_hold.py
  • decision3.pa_frames.structure_break (+ confluence_pa._leg_bos) — here
  • decision3.levels.Levels._bos (BOS-origin births)          — here
"""
import types

import numpy as np
import pytest

from atp_private.trade_engine.decision3 import levels as LV
from atp_private.trade_engine.decision3 import pa_frames as PF

MIRRORS = pytest.mark.parametrize("up", [True, False], ids=["up", "down"])


def _swing(kind, price, bar, confirm):
    return types.SimpleNamespace(kind=kind, price=float(price), bar=bar, confirm_bar=confirm)


@MIRRORS
def test_structure_break_needs_a_close_beyond_a_wick_is_no_break(up):
    s = 1 if up else -1
    swings = [_swing("H" if up else "L", 100 * s, 2, 4)]
    C = np.array([95, 96, 99, 97, 98, 99.5, 101, 102], float) * s       # bar 5: close 99.5 (a wick to 103 would not count); bar 6 closes beyond
    F = types.SimpleNamespace(C=C, last=len(C) - 1, stamp=lambda i: str(i))
    hit = PF.structure_break(F, swings, 5, 7, up, 2)
    assert hit is not None and hit["bar"] == 6                          # the first CLOSE beyond 100, never the wick bar
    assert PF.structure_break(F, swings, 5, 5, up, 2) is None           # only the wick bar ⇒ no break


@MIRRORS
def test_levels_bos_needs_a_close_beyond_the_last_confirmed_swing(up):
    s = 1 if up else -1
    known = [_swing("L" if up else "H", 90 * s, 1, 2), _swing("H" if up else "L", 100 * s, 3, 4)]
    C = np.array([95, 92, 96, 99, 97, 99.5, 101], float) * s            # bar 5 closes short of 100 (its wick may pass) ⇒ no BOS
    fake = types.SimpleNamespace(A={"close": C}, _broken=set())
    got = [LV.Levels._bos(fake, t, known) for t in range(len(C))]
    assert got[5] is None and got[6] is not None and got[6][0] == (1 if up else -1)
    assert sum(g is not None for g in got) == 1                         # one break per swing (retest / reclaim adds none)
