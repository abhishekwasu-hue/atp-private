"""M79 W3: real_days comparison (real_days/<INDEX>/<day>.json.gz: 10 days per index). This engine's layer 1 / 2 / 6 rows of the
index's case are written to a temporary folder, then Trade's own day selection and day file writer run on them: the chosen days
equal the MANIFEST and every day file equals the fixture's.

Same store rules as tests/test_parity_layer1.py (ATP_PRIVATE_FIXTURES; unset: visible skip; set but empty: failure).
"""
import pytest

from atp_private.parity import extras as X
from test_parity_layer1 import _root                               # tests/ is on sys.path (pytest, no __init__.py)


@pytest.mark.parametrize("index", ("NIFTY", "BANKNIFTY"))
def test_real_days_are_byte_equal(index):
    r = X.compare_real_days(_root(), index)
    bad = sorted(k for k, v in r.items() if not v)
    assert not bad, f"real_days {index}: not equal: {bad}"
