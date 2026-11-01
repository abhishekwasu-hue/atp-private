"""M79 / M66 EN-1: the signal-engine shim (`atp_private.trade_engine.get_provider`) that ATP's
backend/app/engine_provider/loader.py loads.

Needs ATP's backend on the import path (ATP_BACKEND, a path to ATP's backend/ folder): the shim builds ATP's own contract
objects. Without it these tests skip with that reason. The fixture tests also need ATP_PRIVATE_FIXTURES (same store
rules as tests/test_parity_layer1.py).
"""
import json
import os
import re
import sys
from datetime import time
from pathlib import Path

import pandas as pd
import pytest

BACKEND = os.environ.get("ATP_BACKEND")
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def C():
    if not BACKEND or not os.path.isdir(BACKEND):
        pytest.skip("ATP_BACKEND not set: ATP's backend (the provider contract) is needed")
    sys.path.insert(0, BACKEND)
    from app.engine_provider import contract
    return contract


def test_no_order_broker_or_network_import():
    src = (ROOT / "atp_private" / "trade_engine" / "provider.py").read_text(encoding="utf-8")
    imports = "\n".join(ln for ln in src.splitlines() if re.match(r"\s*(import|from)\s", ln))
    for word in ("order", "broker", "execution", "requests", "urllib", "socket", "upstox", "telegram"):
        assert word not in imports.lower(), word


def test_loader_loads_the_shim(C):
    from app.engine_provider import loader
    loader.reset_for_tests()
    try:
        p = loader.load()
        assert p is not None, loader.reason()
        d = loader.describe(admin=True)
        assert d["installed"] is True and d["interface"] == C.INTERFACE_VERSION == p.interface
        assert d["name"] == "atp-trade-engine" and d["version"] == "engine-snapshot-v2+813358b" and d["tag"] == "engine-snapshot-v2"
        assert isinstance(p, C.TradeEngineProvider)
        assert set(p.timeframes) == {"1m", "5m", "15m", "1d"}
    finally:
        loader.reset_for_tests()


def _request(C, symbol, frames=None, settings=None):
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
    as_of = pd.Timestamp("2026-10-09 09:30").to_pydatetime().replace(tzinfo=IST)
    return C.EngineRequest(symbol=symbol, as_of=as_of, frames=frames or {}, settings=settings or {},
                           calendar=C.MarketCalendar("Asia/Kolkata", time(9, 15), time(15, 30)))


def test_unknown_instrument_is_a_data_problem(C):
    import atp_private.trade_engine as TE
    r = TE.get_provider().read(_request(C, "NSE_EQ:SOMETHING"))
    assert r.data_problems == ("unknown_instrument",) and not r.signals


def test_too_few_bars_is_a_data_problem_never_a_crash(C):
    import atp_private.trade_engine as TE
    r = TE.get_provider().read(_request(C, "NSE_INDEX:Nifty Bank"))
    assert r.data_problems == ("insufficient_data",) and not r.signals and not r.areas


def test_instrument_names():
    from atp_private.trade_engine import provider as PV
    assert PV.instrument_of("NSE_INDEX:Nifty 50") == "NIFTY"
    assert PV.instrument_of("NSE_INDEX:Nifty Bank") == "BANKNIFTY"
    assert PV.instrument_of("BSE_INDEX:SENSEX") == "SENSEX"
    assert PV.instrument_of("banknifty") == "BANKNIFTY"
    assert PV.instrument_of("NSE_EQ:INFY") is None


# --------------------------------------------------------------------------- with the fixtures store
def _root():
    from test_parity_layer1 import _root as r                      # tests/ is on sys.path (pytest, no __init__.py)
    return r()


class _V:
    def __init__(self, m15):
        self.m15 = m15


def test_mapping_of_a_fired_entry(C):
    """The engine's own decision row (trigger_5m case 8: an entry fired on the 5M candle) ⇒ the interface's fields."""
    from atp_private.parity import extras as X
    from atp_private.parity import runner as R
    from atp_private.trade_engine import provider as PV
    root = _root()
    case = next(c for c in X.trigger_cases(root) if c["n"] == 8)
    row = case["decide5"]
    p = PV.get_provider()
    res = p._result("BANKNIFTY", row, _V(R.load_case(root, case["case"])["m15"]))
    assert isinstance(res, C.EngineResult) and res.interface == 1 and not res.data_problems
    entries = row["entries"]
    assert len(res.signals) == len(entries) >= 1
    for s, e in zip(res.signals, entries):
        a = e["area"]
        assert s.model_id == e["model"] and s.instance_id == e["key"]
        assert s.side == {"support": "buyer", "resistance": "seller"}[a["role"]]
        assert (s.entry_zone.low, s.entry_zone.high) == (min(a["lo"], a["hi"]), max(a["lo"], a["hi"]))
        assert s.invalidation == e["invalidation"] and s.area_id == str(a["uid"])
        assert s.timeframe == "5m" and s.bar_end.isoformat().startswith(row["bar_end"].replace(" ", "T"))
        assert s.card.unknown() == [] and s.card.area_range == (s.entry_zone.low, s.entry_zone.high)
        listed = {k: v for g in ("confirming", "context") for k, v in (e["evidence_list"].get(g) or {}).items()
                  if v in ("present", "absent")}
        assert {(x.token, x.present) for x in s.evidence} == {(k, v == "present") for k, v in listed.items()}
    roles = [a for a in row["active_levels"] if a.get("role") in ("support", "resistance")]
    assert len(res.areas) == len(roles)
    assert all(a.state == a.state.lower() for a in res.areas)


def test_read_on_a_fixture_request_is_valid_and_deterministic(C):
    """End to end: a request built from a fixture case's bars (15M, 5M with the near-month futures volume, Daily), read
    by the engine's live path through the shim: no data problem, a contract-valid result, the same result twice."""
    from zoneinfo import ZoneInfo
    from atp_private.parity import runner as R
    from atp_private.trade_engine import provider as PV
    from atp_private.trade_engine.legs2 import volume as LV
    root = _root()
    folder = os.path.join(root, "inputs", "BANKNIFTY_live_real")
    IST = ZoneInfo("Asia/Kolkata")
    as_of = pd.Timestamp("2026-10-09 09:30")

    def rd(k):
        return pd.read_csv(os.path.join(folder, f"{k}.csv.gz"), float_precision="round_trip", parse_dates=["timestamp"])

    def bars(df, minutes):
        out = []
        for r in df.itertuples(index=False):
            s = pd.Timestamp(r.timestamp)
            st, en = (s.normalize() + pd.Timedelta(minutes=555), s.normalize() + pd.Timedelta(minutes=930)) if minutes is None \
                else (s, s + pd.Timedelta(minutes=minutes))
            if en <= as_of:
                out.append(C.Bar(st.to_pydatetime().replace(tzinfo=IST), en.to_pydatetime().replace(tzinfo=IST),
                                 r.open, r.high, r.low, r.close))
        return tuple(out)
    m15 = pd.concat([rd("h1_pre15"), rd("m15")]).drop_duplicates("timestamp").sort_values("timestamp")
    m5 = pd.concat([rd("h1_pre5"), rd("ltf")]).drop_duplicates("timestamp").sort_values("timestamp")
    nm = LV.near_month(rd("fut"))
    vol = dict(zip(pd.to_datetime(nm["timestamp"]), nm["volume"]))
    b5 = bars(m5, 5)
    fv = tuple(None if vol.get(pd.Timestamp(b.start.replace(tzinfo=None))) is None
               else float(vol[pd.Timestamp(b.start.replace(tzinfo=None))]) for b in b5)
    frames = {"15m": C.Frame("15m", bars(m15, 15)), "5m": C.Frame("5m", b5, futures_volume=fv),
              "1d": C.Frame("1d", bars(rd("daily"), None))}
    req = _request(C, "NSE_INDEX:Nifty Bank", frames)
    p = PV.get_provider()
    a, b = p.read(req), p.read(req)
    assert a.data_problems == () and a == b
    assert a.higher_side is not None and a.areas
    assert all(x.formed_at <= req.as_of for x in a.areas)
    assert all(s.bar_end <= req.as_of for s in a.signals)
    assert R.COMMIT.startswith("813358b")
    json.dumps([x.area_id for x in a.areas])                           # ids are plain text
