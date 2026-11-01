"""M79 W3 / T6: layer 6 (output / verdict (EN, D+E: entry models E1-E4 on the 5M trigger, required set, WATCH, invalidation)) of the imported engine is byte-equal to Trade's fixtures.

Same store rules as tests/test_parity_layer1.py (ATP_PRIVATE_FIXTURES; unset: visible skip; set but empty: failure).
"""
import pytest

from atp_private.parity import runner as R
from test_parity_layer1 import CASES, _root                        # tests/ is on sys.path (pytest, no __init__.py)


@pytest.mark.parametrize("case", CASES)
def test_layer6_is_byte_equal(case):
    r = R.compare_case(_root(), 6, case)
    assert r["settings_equal"], "the engine's reading settings differ from the fixture's settings.json"
    assert r["equal"], f"layer 6 {case}: first different line {r['first_diff']} ({r['expected']} expected, {r['produced']} produced)"
