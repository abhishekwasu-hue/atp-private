"""M56 E2 (A2, A9): one place across object types — two lines within one band tolerance, a line and an area at the same price ⇒ ONE
entry (EN3); the un-entered sibling of another place on the same bar is consumed when the bot opens a position; a pending entry older
than the N18 freshness that never reached the gate is stale (consumed, no card)."""
import json
import types

import numpy as np
import pandas as pd

import atp_private.trade_engine.engine_signal as ES
from atp_private.trade_engine.decision3 import engine as E3
from atp_private.trade_engine.decision3 import entry_models as EM
from atp_private.trade_engine.decision3 import settings as S3


def _obj(kind, oid, lo, hi, d=-1, role="resistance"):
    return {"object": kind, "area_id": oid, "area_uid": oid, "tf": "line" if kind == "broken_line" else "1H", "role": role,
            "lo": lo, "hi": hi, "direction": d, "visit_start_bar": 10, "visit_id": f"{oid}@v", "visit_start": "v",
            "models": {"E4": {"status": "fired"}, "E1": {"status": "fired"}}}


def _f(m="E4"):
    return {"model": m, "variant": "b" if m == "E4" else None}


def test_setting_is_registered_and_provisional():
    assert S3.DEFAULTS["cluster_line_tol_atr"] == S3.REGISTER["cluster_line_tol_atr"][0]
    assert "PROVISIONAL" in S3.REGISTER["cluster_line_tol_atr"][3] and S3.REGISTER["cluster_line_tol_atr"][2] == "अंदाज"


def test_line_tol_is_k_times_the_15m_atr():
    n = 40
    A = {"high": np.full(n, 110.0), "low": np.full(n, 100.0), "close": np.full(n, 105.0)}
    V = types.SimpleNamespace(s={"cluster_line_tol_atr": 0.25, "sw_atr_n": 14}, levels=types.SimpleNamespace(A=A))
    assert EM.line_tol(V, 30) == 2.5 and EM.line_tol(V, 3) == 0.0          # ATR 10 ⇒ 2.5; before 14 bars ⇒ not known ⇒ 0
    V.s["cluster_line_tol_atr"] = 0
    assert EM.line_tol(V, 30) == 0.0


def test_two_lines_within_the_tolerance_are_one_place():
    a, b = _obj("broken_line", "line:1", 100.0, 100.0), _obj("broken_line", "line:2", 103.0, 103.0)
    ents = [(_f(), None, -1, a), (_f(), None, -1, b)]
    kept = EM.clusters([a, b], list(ents), obj=("broken_area", "broken_line"), prefix="CB", tol=5.0)
    assert len(kept) == 1 and b["models"]["E4"]["status"] == "cluster_consumed"
    a2, b2 = _obj("broken_line", "line:1", 100.0, 100.0), _obj("broken_line", "line:2", 103.0, 103.0)
    old = EM.clusters([a2, b2], [(_f(), None, -1, a2), (_f(), None, -1, b2)], obj=("broken_area", "broken_line"), prefix="CB", tol=0.0)
    assert len(old) == 2                                                   # tol 0 = the old reading (two places)


def test_line_and_area_at_the_same_price_are_one_place_across_the_passes():
    area = _obj("area", "7", 98.0, 102.0)
    line = _obj("broken_line", "line:3", 103.0, 103.0)
    ents = [({**_f("E1"), "cluster": {"id": "C7"}}, {}, -1, area), ({**_f("E4"), "cluster": {"id": "CBline:3"}}, None, -1, line)]
    out = EM.one_place(ents, 2.0)
    assert [f.get("place") for f, *_ in out] == ["C7", "C7"]
    assert all("place" not in f for f, *_ in EM.one_place(ents, 0.5))     # 1 point apart, tol 0.5 ⇒ two places
    other = _obj("area", "9", 98.0, 102.0, d=1, role="support")             # the other direction is never the same place
    assert all("place" not in f for f, *_ in EM.one_place([ents[0], (_f("E1"), {}, 1, other)], 5.0))


def test_en3_keeps_one_entry_per_place_at_this_bar():
    class Stub:
        _place = E3.V22._place
    st = Stub()
    e1 = {"model": "E1", "cluster": {"id": "C7"}, "area": {"id": 7}, "visit_id": "7@v", "place": "C7"}
    e4 = {"model": "E4", "cluster": {"id": "CBline:3"}, "area": {"id": "line:3"}, "visit_id": "line:3@w", "place": "C7"}
    e9 = {"model": "E1", "cluster": {"id": "C9"}, "area": {"id": 9}, "visit_id": "9@v"}
    keep, watch = E3.V22._en3(st, 5, [e1, e4, e9], [], [], False)
    assert [e["model"] for e in keep] == ["E1", "E1"] and [w["model"] for w in watch] == ["E4"]
    assert "another entry at this bar" in watch[0]["watch_why"]


def _row(entries, bar="2030-01-07 10:00:00"):
    return {"symbol": "NIFTY", "bar_ts": bar, "decision": "setup", "payload": json.dumps({"entries": entries})}


def _e(m, visit, family=None):
    return {"model": m, "visit_id": visit, "direction": -1, "area": {"id": 1, "lo": 1.0, "hi": 2.0}, "trigger_ts": "x",
            **({"family": family} if family else {})}


def test_only_tied_siblings_are_consumed_when_a_position_opens(tmp_path):
    p = str(tmp_path / "s.db")
    ent = {**_e("E1", "A@v"), "place": "C7"}
    row = _row([ent, _e("E2", "A@v"), {**_e("E4", "L@w"), "place": "C7"}, {**_e("E1", "Z@z"), "cluster": {"id": "C9"}},
                {**_e("E4", "M@m"), "place": "C7", "direction": 1}, {**_e("E2", "C@x", family="C"), "place": "C7"}])
    ES.save(row, p)
    got = ES.consume_siblings("bot", "NIFTY", row, ent, p)
    assert got == [("L@w", "E4")]                                          # the un-entered sibling: same place, same direction
    assert ES.entry_status("bot", "NIFTY", "L@w", "E4", p) == "SKIPPED_SIBLING_ENTERED"
    for v, m in (("A@v", "E2"), ("Z@z", "E1"), ("M@m", "E4"), ("C@x", "E2")):   # same visit (C6) / another place / other side / C
        assert ES.entry_status("bot", "NIFTY", v, m, p) is None
    assert ES.zone_entries_today("bot", "NIFTY", "2030-01-07", -1, 0, 10, p) == 0   # never a zone hit


def test_en3_one_place_across_bars_line_then_area():
    """A line E4 entered at bar u and an area E1 at u + 1 at the same price: the second never reaches the gate (EN3 memo)."""
    class Stub:
        _place = E3.V22._place
        s, levels = {}, None

        def decide(self, u):
            return {"entries": [{"model": "E4", "object": "broken_line", "direction": -1, "visit_id": "line:3@w",
                                 "cluster": {"id": "CBline:3"}, "area": {"id": "line:3", "tf": "line", "lo": 101.0, "hi": 101.0}}]}
    st = Stub()
    line = {"object": "broken_line", "area_id": "line:3", "tf": "line", "lo": 101.0, "hi": 101.0, "direction": -1,
            "models": {"E4": {"status": "fired_earlier", "bar": 4}}}
    e1 = {"model": "E1", "object": "area", "direction": -1, "cluster": {"id": "C7"}, "visit_id": "7@v",
          "area": {"id": 7, "tf": "1H", "lo": 98.0, "hi": 102.0}}
    keep, watch = E3.V22._en3(st, 5, [e1], [line], [], False)
    assert keep == [] and "entered earlier" in watch[0]["watch_why"]
    far = {**e1, "area": {"id": 8, "tf": "1H", "lo": 80.0, "hi": 85.0}}
    st.__dict__.pop("_en3_memo", None)
    keep, _w = E3.V22._en3(st, 5, [far], [line], [], False)
    assert keep == [far]                                                   # another price ⇒ another place


def test_a_re_decided_bar_keeps_the_original_decision(tmp_path):
    import json as J
    p = str(tmp_path / "s.db")
    ES.save({"symbol": "NIFTY", "bar_ts": "2030-01-07 10:00:00", "decision": "setup", "computed_at": "x",
             "payload": J.dumps({"entries": [{"model": "E1"}]})}, p)
    row = {"symbol": "NIFTY", "bar_ts": "2030-01-07 10:00:00", "decision": "wait",
           "payload": J.dumps({"bar_revision": {"bar_ts": "2030-01-07 10:00:00"}})}
    ES.keep_original(row, p)
    orig = J.loads(row["payload"])["bar_revision"]["original"]
    assert orig["decision"] == "setup" and orig["entries"] == [{"model": "E1"}]


def test_pending_entry_older_than_n18_is_stale_unless_it_reached_the_gate(tmp_path):
    p = str(tmp_path / "s.db")
    ES.save(_row([_e("E1", "A@v"), _e("E2", "A@v")]), p)
    st = {"signal_source": "engine"}
    now = pd.Timestamp("2030-01-07 10:03")
    assert [e.get("stale") for _r, e in ES.pending_entries("b", "NIFTY", st, now, p, fresh_min=5)] == [None, None]
    ES.mark_seen("b", "NIFTY", "A@v", "E1", p)
    later = ES.pending_entries("b", "NIFTY", st, pd.Timestamp("2030-01-07 10:08"), p, fresh_min=5)
    assert [(e["model"], bool(e.get("stale"))) for _r, e in later] == [("E1", False), ("E2", True)]
    assert not any(e.get("stale") for _r, e in ES.pending_entries("b", "NIFTY", st, pd.Timestamp("2030-01-07 10:08"), p))   # no limit
    assert not any(e.get("stale") for _r, e in ES.pending_entries("b", "NIFTY", st, pd.Timestamp("2030-01-07 10:08"), p, fresh_min=0))
