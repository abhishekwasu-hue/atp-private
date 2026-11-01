"""M79 W3 / T5: layer 5 (RSI divergence (C: the RSI at the price-extreme bar; zone evidence only)) of the imported engine is byte-equal to Trade's fixtures.

Same store rules as tests/test_parity_layer1.py (ATP_PRIVATE_FIXTURES; unset: visible skip; set but empty: failure).
"""
import pytest

from atp_private.parity import runner as R
from test_parity_layer1 import CASES, _root                        # tests/ is on sys.path (pytest, no __init__.py)


@pytest.mark.parametrize("case", CASES)
def test_layer5_is_byte_equal(case):
    r = R.compare_case(_root(), 5, case)
    assert r["settings_equal"], "the engine's reading settings differ from the fixture's settings.json"
    assert r["equal"], f"layer 5 {case}: first different line {r['first_diff']} ({r['expected']} expected, {r['produced']} produced)"
