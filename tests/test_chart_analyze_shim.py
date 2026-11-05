"""M79 W5: the Analyze-a-chart provider that ATP's backend/app/chart_analyze/provider.py loads.

Checks the interface by attribute (as ATP's runtime Protocol check does), that the instructions carry the snapshot's
Method Pack as is (its own version check), and the reply parser. When ATP's backend is importable (ATP_BACKEND, a path
to ATP's backend/ folder), the loader and the output contract are checked against the real ATP code; otherwise those
tests skip with their reason.
"""
import json
import os
import re
import sys

import pytest

import atp_private.chart_analyze as CA
from atp_private.trade_engine.vision import method_pack as MP

W, H = 1280, 720


def test_provider_interface():
    p = CA.get_provider()
    assert CA.ENGINE_IMPORTED is True
    for attr in ("name", "version", "method_version"):
        assert isinstance(getattr(p, attr), str) and getattr(p, attr)
    assert callable(p.image_only_instructions) and callable(p.parse_image_only)
    assert callable(p.hybrid_instructions) and callable(p.parse_hybrid)    # owner 5 Nov: Advanced = code + AI


def test_instructions_hold_the_method_pack_as_is():
    pack, ver = MP.load()
    p = CA.get_provider()
    assert p.method_version == ver
    ins = p.image_only_instructions(width=W, height=H)
    assert ins.system.startswith(pack.rstrip())
    assert ins.system[len(pack.rstrip()):].lstrip("\n") == CA.FORMAT_TEXT.replace("WIDTH", str(W)).replace("HEIGHT", str(H))
    assert str(W) in ins.user and str(H) in ins.user
    assert ins.prompt_version == f"{CA.PROMPT_VERSION}+pack-{ver}"


def test_format_text_has_no_trade_call_words():
    rule = "never write buy, sell, target, stop-loss"
    text = (CA.FORMAT_TEXT + "\n" + CA.TASK_TEXT).lower()
    assert text.count(rule) == 1                                      # the only place the words appear: the rule against them
    rest = text.replace(rule, "")
    for word in ("buy", "sell", "target", "stop-loss", "stop loss"):       # whole words ("buyer" / "seller" are area sides)
        assert not re.search(rf"\b{word}\b", rest), word


@pytest.mark.parametrize("reply", [
    '{"story": ["a"]}',
    'Here it is:\n```json\n{"story": ["a"]}\n```\n',
    'prefix {not json} then {"story": ["a"]} tail',
])
def test_parse_finds_the_object(reply):
    assert CA.get_provider().parse_image_only(reply, width=W, height=H) == {"story": ["a"]}


@pytest.mark.parametrize("reply", ["", "no object here", "[1, 2]", None])
def test_parse_without_an_object_is_an_error(reply):
    with pytest.raises(ValueError):
        CA.get_provider().parse_image_only(reply, width=W, height=H)


def _atp():
    path = os.environ.get("ATP_BACKEND")
    if not path or not os.path.isdir(os.path.join(path, "app", "chart_analyze")):
        pytest.skip("ATP_BACKEND not set: ATP's loader / contract check needs ATP's backend folder")
    if path not in sys.path:
        sys.path.insert(0, path)


SAMPLE = {
    "recognised": {"symbol": "NIFTY", "exchange": "NSE", "timeframe": "15m", "first_bar": None, "last_bar": None},
    "story": ["Structure description."], "trend": {"side": "down", "text": "Lower highs."},
    "current_state": {"phase": "pullback", "text": "A pullback."}, "rsi": {"divergence": "none", "text": "No pane."},
    "setup": {"side": "bear_call", "label": "A", "status": "forming", "waiting_for": "A reaction at the area.",
              "trigger": {"text": "A commitment candle.", "price": None}, "invalidation": {"text": "A close above the area.", "price": None},
              "next_areas": []},
    "evidence": [{"name": "Trend", "present": True, "reason": "Lower highs."}],
    "scenarios": {"primary": "Rejection at the area.", "alternative": "A close above the area.",
                  "primary_invalidated_at": {"text": "A close above the area.", "price": None}},
    "what_to_wait_for": None, "htf_context": [], "key_levels": [],
    "annotations": {"swings": [{"label": "LH", "x": 100, "y": 200, "price": None}], "areas": [], "lines": [],
                    "rsi_divergence": None, "commitment_candle": None, "ltf_choch": None, "setup_lines": []},
}


def test_atp_loader_accepts_the_provider():
    _atp()
    from app.chart_analyze import provider as P
    P.reset_for_tests()
    try:
        eng = P.load()
        assert eng is not None, P.reason()
        assert P.describe(admin=True)["installed"] is True
        assert P.supports_hybrid(eng) is True
    finally:
        P.reset_for_tests()


def test_a_reply_in_the_format_passes_atp_contract():
    _atp()
    from app.chart_analyze import contract
    raw = CA.get_provider().parse_image_only("```json\n" + json.dumps(SAMPLE) + "\n```", width=W, height=H)
    out = contract.validate(raw, mode="image_only", width=W, height=H)
    assert out["story"] and out["setup"]["side"] == "bear_call" and out["annotations"]["swings"]


def test_format_text_owner_review_rules():
    """Owner CA-D1 / CA-D2 (3 Nov GLENMARK review): story by structure, no calendar words; stock volume; no input
    words; lengths the server keeps."""
    import atp_private.chart_analyze as ca
    t = ca.FORMAT_TEXT
    assert ca.PROMPT_VERSION == "atp_chart_image_v3"
    assert '"choch"' in t and '"last_price"' in t and 'rsi_divergence.rsi' in t
    assert "Tell the story by STRUCTURE only" in t and "Never a month, date, weekday, session or clock word" in t
    assert "never mention FACTS, OHLC text" in t
    assert "for a single stock read the" in t and "stock's own volume bars" in t
    assert "<= 550 characters" in t and "<= 300" in t and "<= 40" in t


FACTS = {"symbol": "NIFTY 50", "timeframe": "1h", "as_of": "x", "last_close": 24101.0, "protected": 23980.0,
         "last_break": {"price": 24150.0, "kind": "bos"}, "areas": [{"where": "above", "low": 24300.0, "high": 24340.0},
                                                                     {"where": "below", "low": 23860.0, "high": 23900.0}],
         "levels": [{"kind": "swing high", "price": 24260.0}], "timeframes": [], "trigger_candle": None,
         "bars": [{"t": 1, "o": 1, "h": 2, "l": 0.5, "c": 1.5}] * 50, "chart": {"width": 960, "height": 540}}

HYBRID_REPLY = {"story": ["The up structure made a higher high, then a pullback."], "trend": {"side": "up", "text": "Up."},
                "current_state": {"phase": "pullback", "text": "Down - pullback toward the area below."},
                "rsi": {"divergence": "none", "text": ""},
                "setup": {"side": "bull_put", "label": "A", "status": "forming", "waiting_for": "a handover at the area",
                          "trigger": {"text": "commitment close above", "price": 24150.0},
                          "invalidation": {"text": "close below protected", "price": 23981.0},
                          "next_areas": [{"text": "made-up", "price": 25555.0}, {"text": "swing high", "price": 24260.0}]},
                "evidence": [{"name": "Trend", "present": True, "reason": "HH and HL"}],
                "scenarios": {"primary": "Pullback holds the area.", "alternative": "A close below the protected level.",
                              "primary_invalidated_at": {"text": "protected", "price": 12345.0}},
                "what_to_wait_for": {"condition": "price at the area", "alert": {"kind": "between", "low": 23860.0, "high": 23900.0}},
                "annotations": {"swings": []}}


def test_hybrid_instructions_carry_the_pack_and_the_reading_not_the_candles():
    p = CA.get_provider()
    ins = p.hybrid_instructions(width=960, height=540, facts=FACTS)
    assert ins.system.startswith(MP.load()[0].rstrip()[:200]) and "ANSWER FORMAT (ATP output contract, Advanced analysis)" in ins.system
    assert ins.prompt_version.startswith("atp_chart_hybrid_v1+pack-")
    assert '"last_close":24101.0' in ins.user and '"bars"' not in ins.user and "NIFTY 50" in ins.user
    assert "places no order" in CA.HYBRID_TASK_TEXT and "Never write buy, sell, target, stop-loss" in CA.HYBRID_FORMAT_TEXT


def test_parse_hybrid_keeps_only_the_readings_prices():
    out = CA.get_provider().parse_hybrid(json.dumps(HYBRID_REPLY), facts=FACTS)
    s = out["setup"]
    assert s["trigger"]["price"] == 24150.0 and s["invalidation"]["price"] == 23981.0          # within 0.05 % of 23,980
    assert [n["price"] for n in s["next_areas"]] == [None, 24260.0]                            # an invented price is removed
    assert out["scenarios"]["primary_invalidated_at"]["price"] is None
    assert out["what_to_wait_for"]["alert"] == {"kind": "between", "low": 23860.0, "high": 23900.0}
    assert "annotations" not in out and out["version"] and out["method_version"]


def test_a_hybrid_reply_passes_atp_contract():
    _atp()
    from app.chart_analyze import contract
    raw = CA.get_provider().parse_hybrid(json.dumps(HYBRID_REPLY), facts=FACTS)
    out = contract.validate(raw, mode="hybrid", width=960, height=540)
    assert out["story"] and out["setup"]["status"] == "forming" and out["coordinate_space"] == "time_price"
