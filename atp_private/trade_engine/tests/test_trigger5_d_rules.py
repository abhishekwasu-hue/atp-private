"""D + E (owner order sec4, DECISIONS 66): the 5M trigger after the 15M push into the area has turned (D1), a trigger candle beyond the
invalidation is a sweep candle (D3), E4 (a)'s failed push only after the 15M close back inside (D4), the scoring's next area beyond the
entry area and one per visit (E1) — synthetic arrays, both mirrors."""
import types

import numpy as np
import pytest

import atp_private.trade_engine.engine3_live as L
from atp_private.trade_engine.decision3 import entry_models5 as EM5

MIRRORS = pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
LVL = {"lo": 100.0, "hi": 104.0}


def _R(h15, c15, h5, k_of, mirror, s=None):
    """A Reader5 on bare arrays: 15M highs / closes of the visit (a push UP into a supply; mirror ⇒ DOWN into a demand), 5M highs."""
    f = (lambda x: 204.0 - np.asarray(x, float)) if mirror else (lambda x: np.asarray(x, float))
    A15 = {"high": f(h15), "low": f(h15), "close": f(c15)}
    A5 = {"high": f(h5), "low": f(h5)}
    R = EM5.Reader5.__new__(EM5.Reader5)
    R.V = types.SimpleNamespace(levels=types.SimpleNamespace(A=A15), s=s or {})
    R.F = types.SimpleNamespace(k_of=np.asarray(k_of, int))
    R.A5 = A5
    return R, (1 if mirror else -1)


@MIRRORS
def test_d1_the_15m_push_must_have_turned(mirror):
    #             15M bars of the visit from 0: a push 103 → 103.6 → 103.9 (still extending), then 103.5 (failed to extend)
    R, d = _R([103.0, 103.6, 103.9, 103.5], [102.8, 103.4, 103.8, 103.0], [0] * 12, [-1, 0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3], mirror)
    assert not R.push_turned15(0, 0, LVL, d)                               # no 15M bar of the visit closed yet
    assert not R.push_turned15(1, 0, LVL, d)                               # the first bar: nothing to fail against
    assert not R.push_turned15(4, 0, LVL, d) and not R.push_turned15(7, 0, LVL, d)   # each closed bar extended the push
    assert R.push_turned15(10, 0, LVL, d)                                   # bar 3 failed to extend ⇒ turned
    R2, d = _R([103.0, 104.6], [102.8, 103.7], [0] * 6, [-1, 0, 0, 1, 1, 1], mirror)
    assert R2.push_turned15(3, 0, LVL, d)                                   # bar 1 swept beyond the far edge and closed back inside


@MIRRORS
def test_d3_a_trigger_candle_beyond_the_invalidation_is_a_sweep_candle(mirror):
    R, d = _R([103.0], [102.8], [102.0, 103.2, 104.9, 103.8], [0, 0, 0, 0], mirror)
    rb = {"lo": 103.0, "hi": 103.5} if not mirror else {"lo": 100.5, "hi": 101.0}
    assert R.sweep_candle(2, LVL, d, 0, rb)                                 # 104.9 beyond the distal edge 104 ⇒ a sweep candle
    assert not R.sweep_candle(1, LVL, d, 0, rb) and not R.sweep_candle(3, LVL, d, 0, rb)   # inside the visit's extreme so far


@MIRRORS
def test_d4_e4a_push_only_after_the_15m_close_back_inside(mirror):
    #            15M: bar 0 swept to 104.8 and closed 104.3 (beyond) · bar 1 closed 103.6 (back inside)
    R, d = _R([104.8, 104.0], [104.3, 103.6], [0] * 9, [-1, -1, -1, 0, 0, 0, 1, 1, 1], mirror)
    Fe = R.P_far(LVL, d)
    assert R.back_inside15(1, 5, Fe, d) is None                             # by the 5M candle 5 only bar 0 closed (beyond)
    assert R.back_inside15(1, 6, Fe, d) == 1                                # bar 1 closed back inside


@MIRRORS
def test_e1_next_area_beyond_the_entry_area_never_overlapping(mirror):
    d = 1 if mirror else -1
    snap = [{"id": 1, "role": "support", "lo": 98.0, "hi": 101.0, "state": "ACTIVE"},     # overlaps the entry area 100–104
            {"id": 2, "role": "support", "lo": 95.0, "hi": 96.0, "state": "ACTIVE"}]
    if mirror:
        snap = [{**x, "role": "resistance", "lo": 204 - x["hi"], "hi": 204 - x["lo"]} for x in snap]
    V = types.SimpleNamespace(levels=types.SimpleNamespace(snapshot=lambda t: snap), s={})
    e = {"direction": d, "entry_ref": 102.0, "area": {"lo": 100.0, "hi": 104.0}}
    assert L.next_area_of(V, 5, e)["id"] == "2"                             # never the area overlapping the entry area
    e_far = {**e, "entry_ref": 95.5 if not mirror else 108.5}                # an entry already past the area: beyond the entry too
    snap.append({"id": 3, "role": snap[0]["role"], "lo": 90.0 if not mirror else 112.0, "hi": 91.0 if not mirror else 114.0,
                 "state": "ACTIVE"})
    assert L.next_area_of(V, 5, e_far)["id"] == "3"
    V.s = {"next_area_rule": "entry_ref"}
    assert L.next_area_of(V, 5, e)["id"] == "1"                             # the what-if (beyond the entry close)


@MIRRORS
def test_the_wait_text_names_the_d_rule_that_holds_the_candle(mirror):
    """27 Oct NIFTY 09:20 (the live E2 / E3 of the earlier code): the 15M push had not turned — the wait words said "no commitment" /
    "the CHoCH candle did not qualify"; they name D1 (and D3) now."""
    R, d = _R([103.0, 103.6, 103.9, 103.5], [102.8, 103.4, 103.8, 103.0], [102.0, 103.2, 104.9, 103.8] + [0] * 8,
              [-1, 0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3], mirror)
    vi = {"s15": 0}
    assert "D1" in R.d5_why(4, LVL, d, 0, vi, None)                        # the closed 15M bar 1 still extended the push
    assert R.d5_why(10, LVL, d, 0, vi, None) is None                       # turned, and no sweep at the candle 10
    R3, d = _R([103.0, 102.9], [102.8, 102.5], [102.0, 103.2, 104.9, 103.8], [-1, 0, 1, 1], mirror)
    assert "D3" in R3.d5_why(2, LVL, d, 0, vi, None) and R3.d5_why(2, LVL, d, 0, vi, None, sweep=False) is None
    assert R3.d5_why(2, LVL, d, 0, {}, None) is None                       # no visit 15M start known ⇒ no claim
    Rl, d = _R([103.0, 103.6], [102.8, 103.4], [0] * 4, [-1, 0, 1, 1], mirror, s={"trigger5_rule": "legacy"})
    assert Rl.d5_why(2, LVL, d, 0, vi, None) is None                       # the legacy trigger: no D words
