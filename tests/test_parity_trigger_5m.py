"""M79 W3: trigger_5m comparison (trigger_5m/cases.json: 20 5M candles; V22 built on inputs/<case>/, then V.decide5(bar5) ==
decide5, as the fixture's `how` says; ts, kind and models read the same).

Same store rules as tests/test_parity_layer1.py (ATP_PRIVATE_FIXTURES; unset: visible skip; set but empty: failure).
"""
import functools

import pytest

from atp_private.parity import extras as X
from atp_private.parity import runner as R
from test_parity_layer1 import _root                               # tests/ is on sys.path (pytest, no __init__.py)

N = 20


@functools.lru_cache(maxsize=1)
def _build(cname):
    return R.build_case(_root(), cname)                            # one build in memory; the cases are grouped by case below


def _case(n):
    return next(c for c in X.trigger_cases(_root()) if c["n"] == n)


def test_store_holds_the_trigger_cases():
    assert [c["n"] for c in X.trigger_cases(_root())] == list(range(1, N + 1))


@pytest.mark.parametrize("n", range(1, N + 1))
def test_trigger_case_decide5_is_equal(n):
    c = _case(n)
    r = X.compare_trigger(_build(c["case"]), c)
    assert all(r.values()), f"trigger_5m #{n} ({c['case']} 5M candle {c['bar5']}): {r}"
