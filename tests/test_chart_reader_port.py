"""Offline tests for chart_read.py (no API call), ported from trade-data books/ai/tests/test_chart_read.py (6dd8bf4).

Port changes only: the import, charts as (label, bytes, media_type) instead of a file path, and REAL pointing to the
package's strategies/ folder. The assertions are unchanged.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from atp_private.chart_reader import chart_read as cr

PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
SPEC = {"id": "TEST_BOOK_1900", "book": "Test Book", "author": "A. Author", "edition": "1900, Test Co.",
        "summary": "Buys pullbacks to old tops.",
        "conditions": [{"id": "S1", "text": "Higher swing lows", "needs": "price", "source": "p.10"},
                       {"id": "S2", "text": "Other average confirms", "needs": "two charts", "source": "p.11"}],
        "trigger": {"text": "Close back above the old top", "source": "p.12"},
        "invalidation": [{"text": "Close below the last swing low", "source": "p.13"}],
        "not_coded": ["time cycles"]}


def _chart(tmp_path, name="c.png"):
    return PNG, "image/png"


@pytest.fixture
def strat_dir(tmp_path, monkeypatch):
    d = tmp_path / "strategies"
    d.mkdir()
    (d / "_TEMPLATE.md").write_text("template", encoding="utf-8")
    (d / "README.md").write_text("index", encoding="utf-8")
    (d / "TEST_BOOK_1900.md").write_text("# x\n## 7. Not coded\n- y\n## 8. Machine spec\n```json\n" + json.dumps(SPEC) + "\n```\n",
                                         encoding="utf-8")
    monkeypatch.setattr(cr, "STRATEGY_DIR", d)
    return d


def test_abhi_prompt_is_pure_method(tmp_path):
    system, user = cr.build_prompts("NIFTY", [("1H", *_chart(tmp_path))], "swing low 22,400")
    assert "Commitment candle" in system and "Never frame the read by day" in system
    assert "book" not in (system + user).lower()  # no book material in Abhi's method
    assert "NIFTY" in user and "1) 1H" in user and "swing low 22,400" in user


def test_book_prompt_is_labelled_and_independent(tmp_path, strat_dir):
    system, user = cr.build_prompts("NIFTY", [("1H", *_chart(tmp_path))], "", "TEST_BOOK_1900")
    assert "Test Book" in system and "NOT Abhi's own method" in system
    assert '"Test Book strategy:"' in user and "[S1] Higher swing lows" in user
    assert "Close back above the old top" in user


def test_request_shape_and_schema_per_mode(tmp_path, strat_dir):
    charts = [("1H", *_chart(tmp_path)), ("15M", *_chart(tmp_path, "d.png"))]
    req = cr.build_request("NIFTY", charts, "")
    assert req["model"] == "claude-opus-5-5" and req["thinking"] == {"type": "adaptive"}
    assert req["output_config"]["format"]["schema"] is cr.ABHI_SCHEMA
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]
    assert [b["type"] for b in req["messages"][0]["content"]] == ["text", "image", "text", "image", "text"]
    assert cr.build_request("NIFTY", charts, "", "TEST_BOOK_1900")["output_config"]["format"]["schema"] is cr.BOOK_SCHEMA


@pytest.mark.parametrize("schema", [cr.ABHI_SCHEMA, cr.BOOK_SCHEMA])
def test_schemas_are_closed(schema):
    def walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(schema)


def test_list_and_bad_spec(strat_dir):
    assert [s["id"] for s in cr.list_strategies()] == ["TEST_BOOK_1900"]
    (strat_dir / "BAD_1.md").write_text("## 8. Machine spec\n```json\n{\"id\": \"BAD_1\"}\n```\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cr.load_strategy("BAD_1")
    with pytest.raises(FileNotFoundError):
        cr.load_strategy("NOPE")


def test_sanitize_strips_trade_parameters_and_flags_time():
    data = {"watch_next": "Watch for a strong close away from 22,400. Place a stop-loss at 22,300. Buy 2 lots here.",
            "areas": [{"evidence": "Base left with force; sellers absorbed on Monday."}],
            "trend": {"evidence": "Higher lows stay; the buyer area was defended twice."}}
    out = cr.sanitize(data)
    assert out.data["watch_next"] == "Watch for a strong close away from 22,400."
    assert len(out.removed) == 2
    assert out.data["trend"]["evidence"].startswith("Higher lows")  # 'buyer' is not 'buy'
    assert out.time_flags and "Monday" in out.time_flags[0]


def test_read_charts_book_strategy_with_fake_client(tmp_path, strat_dir):
    payload = {"conditions": [{"id": "S1", "status": "met", "evidence": "Higher lows."}], "levels": [],
               "trigger_seen": {"status": "no", "evidence": ""}, "invalidated": {"status": "no", "evidence": ""},
               "statement": "Test Book strategy: trigger not yet visible. Set target 22,900.", "cannot_read": None}
    resp = SimpleNamespace(stop_reason="end_turn", stop_details=None, model="claude-opus-5-5",
                           usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0),
                           content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=json.dumps(payload))])
    calls = []
    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: calls.append(kw) or resp)))
    out = cr.read_charts("NIFTY", [("1H", *_chart(tmp_path))], strategy="TEST_BOOK_1900", client=fake)
    assert out["status"] == "ok" and calls
    assert out["strategy"]["name"].startswith("Test Book") and out["strategy"]["independent_book_strategy"]
    assert out["read"]["statement"] == "Test Book strategy: trigger not yet visible."
    assert out["removed"]


def test_book_name_is_not_time_framing():
    book = "The Reminiscences of a Stock Operator (Saturday Evening Post serial)"
    out = cr.sanitize({"statement": f"{book} strategy: range broke down and came back in."}, ignore=(book,))
    assert out.time_flags == [] and out.removed == []
    assert cr.sanitize({"statement": "Watch it on Saturday."}, ignore=(book,)).time_flags


def test_date_check_does_not_match_ordinary_words():
    assert cr.sanitize({"e": "Price 84 declined to the base."}).time_flags == []
    assert cr.sanitize({"e": "The low of 12 December stayed."}).time_flags
    assert cr.sanitize({"e": "The low of 12 Dec stayed."}).time_flags


def test_p1_p2_p3_schema_fields():
    props = cr.BOOK_SCHEMA["properties"]
    assert props["side_scored"]["enum"] == ["long", "short"]
    assert "bar" in props["trigger_seen"]["properties"] and "bar" in props["trigger_seen"]["required"]


def test_p1_to_p6_in_book_prompt(tmp_path, strat_dir):
    system, user = cr.build_prompts("NIFTY", [("1H", *_chart(tmp_path))], "", "TEST_BOOK_1900")
    for needle in ("side_scored", "trigger_seen.bar", "one bar decide", "more than one chart is attached"):
        assert needle in system, needle
    assert "side_scored: long or short" in user and "for the side_scored read" in user


def test_p4_in_abhi_prompt(tmp_path):
    system, _ = cr.build_prompts("NIFTY", [("1H", *_chart(tmp_path))], "")
    assert "Never let one bar decide" in system


def test_p6_second_chart_flag(tmp_path, strat_dir):
    assert cr.needs_two_charts(cr.load_strategy("TEST_BOOK_1900")) == ["S2"]
    payload = {"side_scored": "long", "conditions": [], "levels": [],
               "trigger_seen": {"status": "no", "bar": None, "evidence": ""}, "invalidated": {"status": "no", "evidence": ""},
               "statement": "Test Book strategy: nothing yet.", "cannot_read": None}
    resp = SimpleNamespace(stop_reason="end_turn", stop_details=None, model="claude-opus-5-5",
                           usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0),
                           content=[SimpleNamespace(type="text", text=json.dumps(payload))])
    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: resp)))
    one = cr.read_charts("NIFTY", [("NIFTY", *_chart(tmp_path))], strategy="TEST_BOOK_1900", client=fake)
    two = cr.read_charts("NIFTY", [("NIFTY", *_chart(tmp_path)), ("BANKNIFTY", *_chart(tmp_path, "b.png"))],
                         strategy="TEST_BOOK_1900", client=fake)
    assert one["second_chart_missing"] is True and two["second_chart_missing"] is False
    assert one["two_chart_conditions"] == ["S2"]


def test_sanitize_removes_every_buy_sell_hold_form_but_keeps_buyer_seller():
    for s in ("The buy-the-break trigger is not visible.", "The sell-off was rallied.", "Price held the area.",
              "Selling grew on the drop.", "Hold the position."):
        assert cr.sanitize({"e": s}).removed, s
    out = cr.sanitize({"e": "Buyers defended 11835. Sellers capped 12100."})
    assert out.removed == [] and out.data["e"] == "Buyers defended 11835. Sellers capped 12100."


def test_prompts_ban_buy_sell_hold_words(tmp_path, strat_dir):
    for sid in (cr.ABHI, "TEST_BOOK_1900"):
        system, _ = cr.build_prompts("NIFTY", [("1H", *_chart(tmp_path))], "", sid)
        assert "Never use the words buy, sell or hold in any form" in system


# ---- regression guards on the real strategy specs (review 2026-11-03)
REAL = Path(cr.__file__).resolve().parent / "strategies"


def _real_ids():
    return [s["id"] for s in cr.list_strategies(REAL) if "error" not in s]


def test_real_specs_prompt_text_has_no_forbidden_words():
    assert len(_real_ids()) >= 17
    for sid in _real_ids():
        txt = cr.format_spec(cr.load_strategy(sid, REAL))
        bad = [m.group(0) for m in cr.FORBIDDEN.finditer(txt)]
        assert not bad, (sid, bad)
        assert "Sides the book states:" in txt


def test_real_specs_two_chart_conditions_are_marked():
    for sid in _real_ids():
        spec = cr.load_strategy(sid, REAL)
        two = set(cr.needs_two_charts(spec))
        for c in spec["conditions"]:
            t = c["text"].lower()
            if "second chart" in t or "both charts" in t or "general market" in t or "group leader" in t:
                assert c["id"] in two, (sid, c["id"])
        assert set(spec.get("sides", [])) <= {"long", "short"} and spec.get("sides")
