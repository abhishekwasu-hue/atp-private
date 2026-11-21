"""SRV2 P2 (owner "Pending job purn kr" 21 Nov): the owner's settings page fields for ATP (atp_private/srv2/page_fields.py).

- Every field is one Trade's dashboard page saves for this bot; with TRADE_SRC (a Trade checkout) the keys and the widgets' bounds
  are checked against `page_bot_dynamic_sr_algo.py` itself.
- The shown values come from the functions the bot reads; the strike depths are shown with Trade's sign (+ = OTM, - = ITM).
- `validate` checks only what was sent, with the widgets' bounds; it adds nothing; LIVE and the advanced engine keys are not fields."""
import os
from pathlib import Path

import pytest

from atp_private.srv2 import settings as S
from atp_private.srv2.page_fields import ADVANCED, FIELDS, validate, values_for_page


def test_fields_are_unique_typed_and_grouped():
    keys = [f["key"] for f in FIELDS]
    assert len(keys) == len(set(keys)) == 62 + len(ADVANCED) and len(ADVANCED) == 31   # SRV2-Q8: the advanced engine keys
    assert {f["group"] for f in FIELDS} == {"entry", "exit", "mode"}
    assert {f["type"] for f in FIELDS} <= {"bool", "int", "float", "choice", "multi", "text"}
    assert "trading_mode" not in keys and "broker_account_ids" not in keys          # LIVE stays the owner's own switch
    assert S.FIELDS is FIELDS and S.validate is validate


def test_page_values_are_what_the_bot_reads_with_trades_strike_sign():
    v = values_for_page("BANKNIFTY", {})
    assert set(v) == {f["key"] for f in FIELDS} and None not in v.values()
    merged = S.merged("BANKNIFTY", {})
    assert v["itm_depth_points"] == merged["itm_depth_points"]                       # stored points; ATP divides by -step
    assert v["entry_mode"] == "confirmation" and v["confirm_tf_minutes"] == "15"     # PAPER default, page default 15
    assert v["symbol_enabled"] is False and values_for_page("NIFTY", {})["symbol_enabled"] is True
    stored = {"entry_mode": "touch", "gate_max_armed_bars": 12, "area_alerts": "off", "lots": 4}
    v2 = values_for_page("NIFTY", stored)
    assert (v2["entry_mode"], v2["gate_max_armed_bars"], v2["area_alerts"], v2["lots"]) == ("touch", 12, False, 4)


def test_validate_checks_only_what_was_sent_with_the_widget_bounds():
    clean, errors = validate("NIFTY", {"lots": 3, "itm_depth_points": -100.0, "confirm_tf_minutes": "5", "active_timeframes": []})
    assert errors == {} and clean == {"lots": 3, "itm_depth_points": -100.0, "confirm_tf_minutes": 5, "active_timeframes": ["15M"]}
    clean, errors = validate("NIFTY", {"lots": 51, "pcr_bullish_min": 0.05, "trading_mode": "LIVE", "level_memory_enabled": 1,
                                       "itm_depth_points": 30, "entry_mode": "auto"})
    assert clean == {} and set(errors) == {"lots", "pcr_bullish_min", "trading_mode", "level_memory_enabled", "itm_depth_points",
                                           "entry_mode"}
    # Trade: points = -strikes x step, so strikes = -points / step (+ = OTM, - = ITM), bounds -10..5 strikes
    assert validate("NIFTY", {"itm_depth_points": 300.0})[0] == {"itm_depth_points": 300.0}     # -6 strikes = 6 ITM
    assert validate("NIFTY", {"itm_depth_points": 500.0})[0] == {"itm_depth_points": 500.0}     # -10 strikes, the ITM limit
    assert validate("NIFTY", {"itm_depth_points": -300.0})[1]                                  # +6 strikes OTM > 5
    assert validate("NIFTY", {})[0] == {}


def _trade_page():
    src = os.environ.get("TRADE_SRC")
    if not src:
        pytest.skip("TRADE_SRC (a Trade checkout) not set")
    return (Path(src) / "page_bot_dynamic_sr_algo.py").read_text(encoding="utf-8")


def _widgets(page):
    """{setting key: (min_value, max_value)} for every number widget on Trade's page (ast, not regex)."""
    import ast
    out = {}
    for node in ast.walk(ast.parse(page)):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name not in ("number_input", "_number_input", "safe_number_input"):
            continue
        kw = {k.arg: k.value for k in node.keywords}
        key = None
        if name == "_number_input" and len(node.args) >= 3 and isinstance(node.args[2], ast.Constant):
            key = node.args[2].value
        elif isinstance(kw.get("key"), ast.Call) and kw["key"].args and isinstance(kw["key"].args[-1], ast.Constant):
            key = kw["key"].args[-1].value
        if key is None:
            continue

        def num(n):
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) and isinstance(n.operand, ast.Constant):
                return -n.operand.value
            return None
        out[key] = (num(kw["min_value"]) if "min_value" in kw else None, num(kw["max_value"]) if "max_value" in kw else None)
    return out


# SRV2-Q8: the advanced keys Trade's Save writes through its helpers - each with the helper expression its Save uses
_HELPER_KEYS = {
    "engine3_swing_k_d": 'new_settings[f"engine3_swing_k_d{_d}"]',
    "engine3_daily_pivot_n": '"engine3_daily_pivot_n"',
    "engine3_model_": "_EE.model_key(_m, \"on\")",
    "engine3_model_c_on": "_L3C.MODEL_C_KEY",
    "engine3_c_": 'new_settings[f"engine3_{_k}"]',
    "approval_band_warn_rule": "_PT.BAND_WARN_RULE_KEY",
    "preopen_charts_send": "_PC.CHARTS_SEND_KEY",
}


def _helper_expr(key):
    from atp_private.trade_engine import engine3_live as L3
    if key in L3.METHOD_SWITCHES:
        return "_L3.switches_to_save(engine3_switches)"
    if key.startswith("engine3_model_c_") and key != L3.MODEL_C_KEY:
        return "_L3C.model_c_sub_key(_x)"
    for prefix, expr in sorted(_HELPER_KEYS.items(), key=lambda kv: -len(kv[0])):
        if key.startswith(prefix):
            return expr
    return None


def test_every_field_is_saved_by_trades_page_with_the_same_bounds():
    page = _trade_page()
    save = page[page.index("new_settings = {"):page.index("ok = cloud_db.save_strategy_settings")]
    for f in FIELDS:
        if f in ADVANCED:
            expr = _helper_expr(f["key"])
            assert expr and expr in save, (f["key"], expr)
        else:
            assert f'"{f["key"]}"' in save, f["key"]
    widgets = _widgets(page)
    for f in FIELDS:
        if f["type"] not in ("int", "float"):
            continue
        wkey = {"itm_depth_points": "itm_depth_strikes_otm_pos", "naked_itm_depth_points": "naked_itm_depth_strikes_otm_pos"}.get(f["key"], f["key"])
        assert wkey in widgets, f["key"]
        lo, hi = widgets[wkey]
        if f["key"] == "engine3_daily_pivot_n":                                      # max_value=_L3.DAILY_PIVOT_N_MAX on Trade's page
            assert "max_value=_L3.DAILY_PIVOT_N_MAX" in page and lo == f["min"]
            continue
        assert lo == f.get("min") and hi == f.get("max"), (f["key"], lo, hi, f.get("min"), f.get("max"))


def test_srv2_q8_the_helpers_the_advanced_fields_call_are_trades_own():
    """The advanced fields call this package's copies of Trade's helper modules; with TRADE_SRC each equals Trade's file after the
    snapshot's import rewrite (no other line differs)."""
    import difflib
    src = os.environ.get("TRADE_SRC")
    if not src:
        pytest.skip("TRADE_SRC (a Trade checkout) not set")
    root = Path(__file__).resolve().parents[1] / "atp_private" / "trade_engine"
    norm = lambda t: [ln.strip() for ln in t.splitlines() if ln.strip() and "import" not in ln]
    for rel in ("engine3_live.py", "paper/engine_entry.py", "decision3/settings.py", "swings2/settings.py",
                "bots_common/plain_text.py", "bots_common/preopen_crux.py"):
        ours, theirs = norm((root / rel).read_text(encoding="utf-8")), norm((Path(src) / rel).read_text(encoding="utf-8"))
        diff = [x for x in difflib.unified_diff(theirs, ours, lineterm="", n=0) if x[:1] in "+-" and x[:3] not in ("+++", "---")]
        assert not [x for x in diff if "atp_private" not in x], (rel, diff[:6])


def test_srv2_q8_advanced_values_and_saves_follow_trades_page():
    v = values_for_page("NIFTY", {})
    assert (v["engine3_swing_k_d1"], v["engine3_daily_pivot_n"], v["engine3_entry_gate"], v["engine3_model_e1_on"],
            v["engine3_model_c_on"], v["approval_band_warn_rule"], v["preopen_charts_send"]) == (
        "approved", 2, "models", True, False, "method", "album")
    assert validate("NIFTY", {"engine3_swing_k_d1": "5", "engine3_swing_k_d2": "approved"}, {})[0] == {
        "engine3_swing_k_d1": 5.0, "engine3_swing_k_d2": 6.0}                       # advanced on: both values, as Trade's page
    assert validate("NIFTY", {"engine3_swing_k_d1": "approved", "engine3_swing_k_d2": "approved"}, {})[0] == {
        "engine3_swing_k_d1": "", "engine3_swing_k_d2": ""}                         # advanced off: empty = the approved scale
    assert validate("NIFTY", {"engine3_swing_k_d1": "5", "engine3_swing_k_d2": "4"}, {})[1]   # D2 not above D1: refused
    assert validate("NIFTY", {"engine3_swing_k_d2": "4"}, {"engine3_swing_k_d1": 5.0})[1]      # the stored D1 counts
    assert validate("NIFTY", {"engine3_zone_visit_rule": "close_away"}, {})[1]                # legacy visit alone: refused
    clean, errors = validate("NIFTY", {"engine3_zone_visit_rule": "close_away", "engine3_commit_volume_rule": "opposite",
                                       "engine3_entry_gate": "models", "engine3_daily_pivot_n": 2}, {})
    assert errors == {} and clean == {"engine3_zone_visit_rule": "close_away", "engine3_commit_volume_rule": "opposite",
                                      "engine3_entry_gate": "", "engine3_daily_pivot_n": ""}    # the method / provisional = empty
    assert validate("NIFTY", {"engine3_model_e2_on": False, "engine3_model_c_on": True, "engine3_c_window": "c_pullbacks",
                              "preopen_charts_send": "link"}, {})[0] == {
        "engine3_model_e2_on": False, "engine3_model_c_on": True, "engine3_c_window": "c_pullbacks", "preopen_charts_send": "link"}
    assert validate("NIFTY", {"engine3_c_projections": "abc"}, {})[1] and validate("NIFTY", {"engine3_daily_pivot_n": 6}, {})[1]
