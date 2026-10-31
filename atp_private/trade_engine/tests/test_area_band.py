"""Abhi 29 Oct (research: the supply / demand base and the order-block half): one general rule for a 1H area band born from one candle
(decision3/levels.area_band) — never a few points, never the whole impulse leg; both sides; the what-if `level_band_rule = wick`."""
import pytest

from atp_private.trade_engine.decision3 import levels as LV


@pytest.mark.parametrize("mirror", [False, True], ids=["supply", "demand"])
def test_area_band_base_candle_far_body_edge_impulse_candle_its_half(mirror):
    f = (lambda x: 200.0 - x) if mirror else (lambda x: float(x))
    k = "L" if mirror else "H"

    def band(o, h, l, c, s=None):                                         # a supply candle; mirror: the same candle upside down
        o, h, l, c = (f(x) for x in (o, h, l, c))
        h, l = max(h, l), min(h, l)
        lo, hi = LV.area_band(k, o, h, l, c, h if k == "H" else l, 0, s)
        return (lo, hi) if not mirror else (round(200.0 - hi, 6), round(200.0 - lo, 6))
    assert band(104.0, 106.0, 100.0, 103.0) == (103.0, 106.0)              # base (body 1 ≤ ½ of 6): the high … the far body edge
    assert band(105.8, 106.0, 100.0, 100.5) == (103.0, 106.0)              # impulse (body 5.3 of 6): the high … its middle (not 105.8)
    assert band(100.5, 106.0, 100.0, 105.9) == (103.0, 106.0)              # an impulse INTO the high: still its upper half, never the leg
    assert band(105.8, 106.0, 100.0, 100.5, {"level_band_rule": "wick"}) == (105.8, 106.0)   # the what-if: wick to the near body edge
    assert band(106.0, 106.0, 100.0, 106.0) == (100.0, 106.0)              # no body room ⇒ never one price (C-2)


def test_area_band_rule_values():
    assert LV.band_rule({}) == "base" and LV.band_rule({"level_band_rule": "wick"}) == "wick"
    with pytest.raises(ValueError):
        LV.band_rule({"level_band_rule": "x"})
