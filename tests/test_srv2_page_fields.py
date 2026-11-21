"""SRV2 P2 (owner "Pending job purn kr" 21 Nov): the owner's settings page fields for ATP (atp_private/srv2/page_fields.py).

- Every field is one Trade's dashboard page saves for this bot; with TRADE_SRC (a Trade checkout) the keys and the widgets' bounds
  are checked against `page_bot_dynamic_sr_algo.py` itself.
- The shown values come from the functions the bot reads; the strike depths are shown with Trade's sign (+ = OTM, - = ITM).
- `validate` checks only what was sent, with the widgets' bounds; it adds nothing; LIVE and the advanced engine keys are not fields."""
import os
from pathlib import Path

import pytest

from atp_private.srv2 import settings as S
from atp_private.srv2.page_fields import FIELDS, validate, values_for_page


def test_fields_are_unique_typed_and_grouped():
    keys = [f["key"] for f in FIELDS]
    assert len(keys) == len(set(keys)) == 62
    assert {f["group"] for f in FIELDS} == {"entry", "exit", "mode"}
    assert {f["type"] for f in FIELDS} <= {"bool", "int", "float", "choice", "multi"}
    assert "trading_mode" not in keys and "broker_account_ids" not in keys          # LIVE stays the owner's own switch
    assert not [k for k in keys if k.startswith("engine3_") and k != "engine3_use_1m"]  # advanced engine keys: step 2 (SRV2-Q8)
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


def test_every_field_is_saved_by_trades_page_with_the_same_bounds():
    page = _trade_page()
    save = page[page.index("new_settings = {"):page.index("ok = cloud_db.save_strategy_settings")]
    for f in FIELDS:
        assert f'"{f["key"]}"' in save, f["key"]
    widgets = _widgets(page)
    for f in FIELDS:
        if f["type"] not in ("int", "float"):
            continue
        wkey = {"itm_depth_points": "itm_depth_strikes_otm_pos", "naked_itm_depth_points": "naked_itm_depth_strikes_otm_pos"}.get(f["key"], f["key"])
        assert wkey in widgets, f["key"]
        lo, hi = widgets[wkey]
        assert lo == f.get("min") and hi == f.get("max"), (f["key"], lo, hi, f.get("min"), f.get("max"))
