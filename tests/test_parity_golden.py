"""M79 W3: golden comparison of the imported engine against Trade's fixtures (golden/golden.json: the NIFTY golden days read on 15M
and 5M; golden/chart_cases/<id>/market_state.jsonl.gz: market_state.read on every window bar / checkpoint).

Same store rules as tests/test_parity_layer1.py (ATP_PRIVATE_FIXTURES; unset: visible skip; set but empty: failure).
"""
import pytest

from atp_private.parity import extras as X
from test_parity_layer1 import _root                               # tests/ is on sys.path (pytest, no __init__.py)

CHART_CASES = ("2026-10-05_06_correction", "2026-10-07_bear_call_trendline")


def test_golden_json_is_byte_equal():
    assert X.compare_golden(_root())["golden.json"], "golden/golden.json differs"


def test_store_lists_the_chart_cases():
    assert tuple(X._manifest(_root())["golden_chart_cases"]) == CHART_CASES


@pytest.mark.parametrize("cid", CHART_CASES)
def test_chart_case_market_state_is_byte_equal(cid):
    r = X.compare_chart_case(_root(), cid)
    assert r["equal"], f"chart case {cid}: first different line {r['first_diff']} ({r['expected']} expected, {r['produced']} produced)"
