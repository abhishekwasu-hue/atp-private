"""Guard for the SW rewrite (M50 / DECISIONS 110): the owner's answer key batch1-v4 (8 lifecycle items, private trade-data
review/answer_key/answer_key_batch1_v4.json) must read the same under the default engine — the reader built as live (Upstox 15M window,
Daily history, 5M LTF, the stored 1H history before the window). Skips without the private data."""
import glob
import json
import os

import pandas as pd
import pytest

TD = os.environ.get("TRADE_DATA", "/home/user/trade-data")
KEY = next((p for p in (f"{TD}/review/answer_key/answer_key_batch1_v4.json", f"{TD}/overseer/answer_key_batch1_v4.json") if os.path.exists(p)),
           f"{TD}/review/answer_key/answer_key_batch1_v4.json")
pytestmark = pytest.mark.skipif(not (os.path.exists(KEY) and glob.glob(f"{TD}/banknifty/vps_spot_history/*/")),
                                reason="private trade-data (answer key v4 / BANKNIFTY history) not present")
TFW = {"Daily": "D", "1H": "1H", "Weekly": "W", "flipped": "1H"}


@pytest.fixture(scope="module")
def data():
    import atp_private.trade_engine.instruments as INS
    INS.set_current("BANKNIFTY")
    from atp_private.trade_engine.tests import banknifty_replay_inputs as BI
    return BI.load()


def _read(data, it):
    """The reader at the item's window end (the last session ≤ it), as live: object lifecycle events (bars ≤ the session close)."""
    import contextlib
    import io
    import atp_private.trade_engine.engine3_live as L
    from atp_private.trade_engine.bots_common import level_reaction as LR
    from atp_private.trade_engine.decision3 import engine as E3, history as HI, levels as LV
    S = L.DEFAULTS
    sess = sorted(pd.to_datetime(data["m15"]["timestamp"]).dt.normalize().unique())
    D = max(pd.Timestamp(x) for x in sess if pd.Timestamp(x) <= pd.Timestamp(it["window"][1]))
    now = D + pd.Timedelta(hours=15, minutes=31)
    m15a = data["m15"]
    m15 = m15a[(m15a["timestamp"] >= D - pd.Timedelta(days=S["engine3_m15_days"])) & (m15a["timestamp"] < D + pd.Timedelta(days=1))]
    m15 = L.closed_session_bars(m15, 15, now)
    pre = m15a[m15a["timestamp"] < m15["timestamp"].iloc[0]]
    pre5 = data["m5"][data["m5"]["timestamp"] < m15["timestamp"].iloc[0]]          # M56 E1/E4 review: the live builder (DP-marked
    h1h = LV.h1_history(pre, "BANKNIFTY", finer=pre5) if len(pre) else None       # from the stored 5M under it, levels.h1_history)
    dd = data["daily"][data["daily"]["timestamp"] <= D]
    daily = LR.prepare_daily(L._naive(dd)[["timestamp", "open", "high", "low", "close"]], now.normalize())
    m5 = data["m5"]
    ltf = L.closed_session_bars(m5[(m5["timestamp"] >= D - pd.Timedelta(days=S["engine3_ltf_days"])) & (m5["timestamp"] < D + pd.Timedelta(days=1))], 5, now)
    with contextlib.redirect_stdout(io.StringIO()):
        V = E3.V22(m15.drop(columns=["volume"], errors="ignore"), None, daily, sealed=HI.sealed_fn("BANKNIFTY"), ltf=ltf, h1_history=h1h)
    lo, hi = it["object"]["lo"], it["object"]["hi"]
    tf = next(v for k, v in TFW.items() if it["object"]["tf_band"].startswith(k))
    # the object = the place the owner named, identified by its BIRTH band (the swing candle's wick to body); B1 (owner order 28 Oct)
    # then draws a zone's band over its whole base (proximal = the far body edge) — the readings (states) asserted below are unchanged
    # Abhi 28 Oct (7) / 29 Oct: one general area band rule (levels.area_band) may widen the birth band — the same place = one edge as the
    # owner's band (its distal swing extreme) and a birth band holding it
    cands = [Lv for Lv in V.levels.L if Lv.tf == tf and (abs(Lv.bands[0][1] - lo) < 1.0 or abs(Lv.bands[0][2] - hi) < 1.0)
             and Lv.bands[0][1] <= lo + 1.0 and Lv.bands[0][2] >= hi - 1.0]
    return V, cands


def _items():
    if not os.path.exists(KEY):
        return []
    return json.load(open(KEY))["items"]


@pytest.mark.parametrize("it", _items(), ids=lambda it: it["id"])
def test_answer_key_v4_item_reads_the_same(data, it):
    from atp_private.trade_engine.decision3 import flip as FL
    V, cands = _read(data, it)
    assert cands, f"{it['id']}: the object {it['object']} is not found by the reader"
    t = len(V.levels.ts) - 1
    ts = V.levels.ts
    w0 = pd.Timestamp(it["window"][0])
    if it["id"] == "L07":
        assert len({Lv.uid for Lv in cands}) == 1                         # ONE object (one id)
    for Lv in cands:
        ev = [(ts.iloc[b], k) for b, k, _ in Lv.events if k in ("broken", "flip", "dead") and ts.iloc[b] >= w0 - pd.Timedelta(days=3)]
        if it["id"] == "L03":                                              # BROKEN only on 28 Sep 09:15 (24–27 Sep beyond, not broken)
            br = [x for x, k in ev if k == "broken"]
            assert br and br[0] == pd.Timestamp("2026-09-28 09:15"), ev
            assert Lv.state_at(t) == FL.FLIPPED and Lv.role_at(t) != Lv.role0
        elif it["id"] == "L04":                                            # the flip still alive (not dead)
            assert Lv.dead_bar is None and Lv.state_at(t) in (FL.FLIPPED, FL.BEYOND), (Lv.state_at(t), ev)
        else:                                                              # alive in its role: never broken in the window
            assert not [x for x, k in ev if k in ("broken", "flip", "dead") and x >= w0], ev
            assert Lv.role_at(t) == Lv.role0 and Lv.state_at(t) not in (FL.FLIPPED, FL.DEAD)
