"""atp_private.preopen (owner 4 Nov, "Default yes"): the pre-open charts for ATP's own job - the engine's pre-open read on
the bars ATP hands in, the official close with every distance from it, the last unfilled opening gap as a band, and the
Daily phase in the title. Synthetic bars only (the repository's own fixture builder)."""
from datetime import time
from types import SimpleNamespace as NS
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from atp_private import preopen as P

IST = ZoneInfo("Asia/Kolkata")


def test_no_order_broker_or_network_import():
    import inspect
    src = inspect.getsource(P)
    for word in ("order", "broker", "requests", "httpx", "execution"):
        assert f"import {word}" not in src and f"from {word}" not in src


def test_distance_is_measured_from_the_shown_close_and_nearest_comes_first():
    watch = [{"lo": 110.0, "hi": 120.0, "dist": 1.0, "id": "a"}, {"lo": 95.0, "hi": 99.0, "dist": 9.0, "id": "b"},
             {"lo": 100.0, "hi": 104.0, "dist": 5.0, "id": "c"}]
    out = P.remeasure(watch, 102.0)
    assert [x["id"] for x in out] == ["c", "b", "a"]
    assert [x["dist"] for x in out] == [0.0, 3.0, 8.0]
    assert watch[0]["dist"] == 1.0                                         # the reader's list is not changed


def test_newest_close_never_older_than_the_candles_drawn():
    daily = pd.DataFrame({"timestamp": pd.to_datetime(["2026-10-22", "2026-10-23"]), "close": [1.0, 2.0]})
    m15 = pd.DataFrame({"timestamp": pd.to_datetime(["2026-10-23 15:15", "2026-10-26 15:15"]), "close": [2.5, 3.0]})
    assert P.newest_close(daily, m15) == (3.0, pd.Timestamp("2026-10-26").date())
    assert P.newest_close(daily, m15.iloc[:1]) == (2.0, pd.Timestamp("2026-10-23").date())


def test_phase_only_when_the_fold_trend_is_the_engine_trend():
    V = NS(daily=[NS(trend="DOWN", phase="correction")])
    assert P.phase_of(V, {"trend": "DOWN"}) == "correction"
    assert P.phase_of(V, {"trend": "UP"}) is None
    assert P.phase_of(NS(daily=[NS(trend="UP", phase="origin_broken")]), {"trend": "UP"}) == "origin broken"


def test_last_unfilled_gap_skips_filled_gaps(monkeypatch):
    from atp_private.trade_engine.decision3 import gaps as GP
    gaps = [{"zone": (90.0, 95.0), "dir": "up", "fill": "open"}, {"zone": (120.0, 110.0), "dir": "down", "fill": "partly"},
            {"zone": (130.0, 131.0), "dir": "up", "fill": "filled"}]
    monkeypatch.setattr(GP, "opening_gaps", lambda V, t: gaps)
    V = NS(s={}, m15=[0, 1])
    assert P.last_unfilled_gap(V) == {"lo": 110.0, "hi": 120.0, "dir": "down", "fill": "partly"}
    assert P.last_unfilled_gap(NS(s={"opening_gaps": "off"}, m15=[0])) is None


def _bars(df, minutes):
    out = []
    for r in df.itertuples(index=False):
        s = pd.Timestamp(r.timestamp)
        st, en = ((s.normalize() + pd.Timedelta(minutes=555), s.normalize() + pd.Timedelta(minutes=930)) if minutes is None
                  else (s, s + pd.Timedelta(minutes=minutes)))
        out.append(NS(start=st.to_pydatetime().replace(tzinfo=IST), end=en.to_pydatetime().replace(tzinfo=IST),
                      open=r.open, high=r.high, low=r.low, close=r.close, volume=getattr(r, "volume", None)))
    return tuple(out)


@pytest.fixture(scope="module")
def request_():
    from atp_private.trade_engine.tests import oct12_fixture as F
    m15, _fut, _ltf = F.build()
    m15 = m15[["timestamp", "open", "high", "low", "close"]].copy()
    m15["timestamp"] = pd.to_datetime(m15["timestamp"])
    g = m15.groupby(m15["timestamp"].dt.normalize())
    daily = pd.DataFrame({"timestamp": g["timestamp"].first().dt.normalize(), "open": g["open"].first(), "high": g["high"].max(),
                          "low": g["low"].min(), "close": g["close"].last()}).reset_index(drop=True)
    first, c0 = daily["timestamp"].iloc[0], float(daily["open"].iloc[0])     # older sessions in front (the engine reads >= 30 Daily)
    days = pd.bdate_range(end=first - pd.Timedelta(days=1), periods=120)
    import numpy as np
    wave = c0 * (1 + 0.04 * np.sin(np.arange(len(days)) / 9.0) - 0.0004 * (len(days) - np.arange(len(days))))
    older = pd.DataFrame({"timestamp": days, "open": wave * 0.999, "high": wave * 1.006, "low": wave * 0.994, "close": wave})
    daily = pd.concat([older, daily], ignore_index=True)
    end = m15["timestamp"].iloc[-1] + pd.Timedelta(minutes=15)
    frames = {"15m": NS(bars=_bars(m15, 15), futures_volume=None), "1d": NS(bars=_bars(daily, None), futures_volume=None)}
    return NS(symbol="BANKNIFTY", as_of=end.to_pydatetime().replace(tzinfo=IST), frames=frames, settings={},
              calendar=NS(holidays=(), early_closes=(), regular_open=time(9, 15))), float(m15["close"].iloc[-1])


def test_build_draws_three_charts_from_the_handed_bars(request_):
    req, close = request_
    r = P.build(req)
    if "problem" in r:
        pytest.fail(f"engine read refused the synthetic bars: {r['problem']}")
    assert [tf for tf, _, _ in r["items"]] == ["Daily", "1H", "15M"] and r["errors"] == []
    for _tf, png, cap in r["items"]:
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and cap.startswith("BANKNIFTY · ")
    assert r["facts"]["close"] == close and r["facts"]["official"] is False
    off = P.build(req, official_close=(close - 7.5, "2026-10-12"))
    assert off["facts"]["close"] == close - 7.5 and off["facts"]["official"] is True and off["facts"]["close_day"] == "2026-10-12"


def test_unknown_symbol_is_a_problem_never_a_crash(request_):
    req, _ = request_
    assert P.build(NS(**{**vars(req), "symbol": "NOPE"}))["problem"] == "unknown_instrument"


def test_title_and_caption_carry_the_phase_and_the_gap_label():
    from atp_private.trade_engine.decision3 import preopen_chart as PCH
    f = {"ctx": {"trend": "DOWN"}, "phase": "correction", "nearest": None}
    assert PCH._title("NIFTY", "Daily", f, "UP") == "NIFTY · Daily · Daily DOWN (correction) · Weekly UP"
    assert PCH.caption("NIFTY", "1H", f) == "NIFTY · 1H · Daily DOWN (correction)"
    assert PCH._title("NIFTY", "Daily", {"ctx": {"trend": "UP"}}, None) == "NIFTY · Daily · Daily UP · Weekly n/a"
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    labels = PCH._overlay(ax, {"gap_band": {"lo": 100.0, "hi": 110.0, "dir": "up", "fill": "open"}, "last": 120.0,
                               "last_word": "NSE close"}, 10, "Daily")
    plt.close(fig)
    words = [t for _, t, _, _ in labels]
    assert "opening gap up 100–110 (open)" in words and "NSE close 120" in words
    y0, _y1, notes = PCH._ylim(115.0, 125.0, {"gap_band": {"lo": 10.0, "hi": 11.0}}, False)
    assert notes == ["opening gap 10–11 off chart (below)"] and y0 > 11
