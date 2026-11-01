"""EN (owner order EN1–EN5, DECISIONS 93 / 118): the entry gate, both directions.

  • EN1 an ENTRY only with the complete required set (handover + commitment + its volume + LTF CHoCH by close); a model firing without
    it = a WATCH alert (no card, no position) with the missing piece named; `en_rule = models` = the earlier reading (what-if);
  • EN2 the invalidation = the zone's distal edge, or a false-break / sweep extreme beyond it — never an internal level;
  • EN3 one entry per cluster per visit — a place already entered earlier in the visit turns a later entry into a WATCH, read by
    deciding the earlier bar again (the same answer live and in a replay)."""
import types

import pytest

from atp_private.trade_engine.decision3 import engine as E3
from atp_private.trade_engine.decision3 import entry_models as EM
from atp_private.trade_engine.decision3 import settings as S3

DIRS = pytest.mark.parametrize("d", [-1, 1], ids=["bear_call", "bull_put"])


def _entry(model, req, area_id=7, cluster=None, visit="v1@2030-01-07", wait="no_handover"):
    return {"model": model, "name": model, "direction": -1, "area": {"id": area_id}, "invalidation": 104.0,
            "invalidation_rule": "price above the area's distal edge 104.00", "visit_id": visit,
            "cluster": cluster, "label": None, "evidence_list": {"legacy_required": req}, "confirming": {},
            "_eval": {"commit": {"confirm_wait": wait}, "context": {}, "zone_read": None, "trendline": None}, "_lvl": {"id": area_id}}


def _V(**s):
    V = E3.V22.__new__(E3.V22)
    V.s = S3.load(s)
    V.pb = types.SimpleNamespace(at=lambda t, d: None)
    return V


def _read(entries, armed=()):
    return lambda V, t, trend, act: {"entries": list(entries), "armed": list(armed), "first_area": None}


def test_en1_entry_only_with_the_full_required_set_else_watch():
    V = _V()
    r = V._models_eval(5, "DOWN", [], _read=_read([_entry("E1", "absent"), _entry("E2", "present", area_id=8)]))
    assert [e["model"] for e in r["entries"]] == ["E2"] and r["decision"] == E3.SETUP
    assert [w["model"] for w in r["watch"]] == ["E1"] and "no_handover" in r["watch"][0]["watch_why"]
    r2 = V._models_eval(5, "DOWN", [], _read=_read([_entry("E1", "absent")]))
    assert not r2["entries"] and r2["decision"] == E3.WAIT and r2["chk"]["⑥"][1].startswith("watch: E1")
    r3 = _V(en_rule="models")._models_eval(5, "DOWN", [], _read=_read([_entry("E1", "absent")]))
    assert [e["model"] for e in r3["entries"]] == ["E1"] and not r3["watch"]                # the what-if: every firing an entry


@DIRS
def test_en2_invalidation_is_the_distal_edge_never_inside(d):
    R = EM.Reader.__new__(EM.Reader)
    R.V = types.SimpleNamespace(s=S3.load())
    lvl = {"id": 7, "lo": 98.0, "hi": 104.0}
    inside = 103.5 if d < 0 else 98.5                                     # the refined base / visit extreme inside the zone
    R._model_invalidation = lambda *a, **k: (inside, "model level", {})
    inv, rule, facts = R.invalidation("E2", 5, lvl, d, 0, None)
    assert inv == (104.0 if d < 0 else 98.0) and "distal edge" in rule and facts["model_invalidation"] == inside
    beyond = 104.6 if d < 0 else 97.4                                     # a false-break / sweep extreme beyond the distal edge
    R._model_invalidation = lambda *a, **k: (beyond, "sweep extreme", {})
    assert R.invalidation("E4", 5, lvl, d, 0, None)[0] == beyond
    R.V.s = S3.load({"en_inv_rule": "model"})
    R._model_invalidation = lambda *a, **k: (inside, "model level", {})
    assert R.invalidation("E2", 5, lvl, d, 0, None)[0] == inside            # the what-if keeps the model's own level


@DIRS
def test_en2_e4b_broken_area_invalidation_is_the_band_far_edge_never_inside(d):
    """EN2 / DECISIONS 83: E4 (b) on a broken (flipped) AREA ⇒ the farther of the retest extreme and the band's far edge opposite the
    new trade direction; a broken LINE keeps the retest extreme (DECISIONS 101); `en_inv_rule` "model" = the retest extreme (what-if)."""
    R = EM.Reader.__new__(EM.Reader)
    R.V = types.SimpleNamespace(s=S3.load())
    band = {"id": 7, "lo": 98.0, "hi": 104.0}
    inside = 103.5 if d < 0 else 98.5                                     # the retest extreme inside the broken band
    inv, rule, facts = R.e4b_invalidation("area", band, inside, d)
    assert inv == (104.0 if d < 0 else 98.0) and "far edge" in rule and "retest extreme" in rule and facts["model_invalidation"] == inside
    beyond = 104.6 if d < 0 else 97.4                                     # the retest swept beyond the far edge
    inv, rule, facts = R.e4b_invalidation("area", band, beyond, d)
    assert inv == beyond and rule.endswith(f"the retest extreme {beyond:,.2f}") and facts == {"distal_edge": (104.0 if d < 0 else 98.0)}
    assert R.e4b_invalidation("line", {"id": 3, "lo": 98.0, "hi": 104.0}, inside, d) == (inside, R.e4b_invalidation(
        "line", {}, inside, d)[1], {})                                    # lines unchanged
    R.V.s = S3.load({"en_inv_rule": "model"})
    assert R.e4b_invalidation("area", band, inside, d)[0] == inside        # the what-if keeps the retest extreme


def test_en3_one_entry_per_cluster_per_visit_read_from_the_earlier_bar():
    V = _V()
    cl = {"id": "C1", "anchor": 7, "visit_id": "v1@2030-01-07", "n": 2}
    earlier = _entry("E2", "present", cluster=cl)
    armed = [{"area_id": 7, "cluster": cl, "visit_start": "2030-01-07 09:15:00", "role": "resistance", "lo": 98.0, "hi": 104.0,
              "object": "area", "models": {"E2": {"status": "fired_earlier", "bar": 3}}}]
    calls = []
    V.decide5 = lambda u: calls.append(u) or {"entries": [{k: v for k, v in earlier.items() if not k.startswith("_")}]}   # 5M path
    V.decide = lambda u: pytest.fail("the 5M path re-reads with decide5")
    r = V._models_eval(5, "DOWN", [], _read=_read([_entry("E3", "present", area_id=8, cluster=cl)], armed))
    assert not r["entries"] and r["watch"][0]["watch_why"].startswith("one entry per cluster per visit") and calls == [3]
    V.decide5 = lambda u: {"entries": []}                                 # the earlier firing was a WATCH ⇒ this one is the entry
    V.__dict__.pop("_en3_memo", None)
    r2 = V._models_eval(5, "DOWN", [], _read=_read([_entry("E3", "present", area_id=8, cluster=cl)], armed))
    assert [e["model"] for e in r2["entries"]] == ["E3"]
    two = [_entry("E2", "present", cluster=cl), _entry("E3", "present", area_id=8, cluster=cl)]   # two at one bar ⇒ the first
    V.__dict__.pop("_en3_memo", None)
    r3 = V._models_eval(5, "DOWN", [], _read=_read(two))
    assert [e["model"] for e in r3["entries"]] == ["E2"] and r3["watch"][0]["model"] == "E3"
