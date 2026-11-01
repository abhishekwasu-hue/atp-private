"""Test stub of the pre-open's engine payload (owner order 30 Oct (7) P1): `engine3_live.watched_levels` returns the engine's tradeable
levels stamped with the engine's own watch list (`chart_reading.stamp_watch` over step ②). Fixtures without a V22 model that list
here: each level gets the reader's `dist` from the last close (0 = price inside, `Levels.snapshot`) and the levels `Levels.active`
would arm get `watch_rank` in dist order — a sell side arms every resistance not below price, a buy side every support not above it,
both sides (a range) the nearest of each. A stub of the engine for the tests only; the pre-open itself never computes this."""
import copy

BULL, BEAR = "BULLISH", "BEARISH"


def stamp(levels, last, sides):
    out = copy.deepcopy(list(levels or ()))
    for i, x in enumerate(out):
        x.setdefault("id", 1000 + i)
        x.setdefault("tf", "1H")                                          # a snapshot item always names its timeframe
        lo, hi = float(x["lo"]), float(x["hi"])
        x["dist"] = 0.0 if lo <= last <= hi else round(lo - last if last < lo else last - hi, 2)
    sides = set(sides or ())
    res = sorted((x for x in out if x.get("role") == "resistance" and float(x["hi"]) >= last), key=lambda x: x["dist"])
    sup = sorted((x for x in out if x.get("role") == "support" and float(x["lo"]) <= last), key=lambda x: x["dist"])
    arm = res if sides == {BEAR} else sup if sides == {BULL} else (sup[:1] + res[:1]) if sides else []
    from atp_private.trade_engine.decision3 import chart_reading as CR
    CR.stamp_watch(out, arm)
    for x in out:
        x.setdefault("watch_rank", None)
    return out
