"""M79 W3 / T1: layer 1 (swings / structure, SW, step 1) of the imported engine is byte-equal to Trade's fixtures.

The fixtures are in the private fixtures store (ATP_PRIVATE_FIXTURES, on the host only; never in git). Not set: a
visible skip. Set but without the snapshot's folder: an error (a store that is named must be complete).
"""
import os

import pytest

from atp_private.parity import runner as R

CASES = ("NIFTY_real", "NIFTY_mirror", "BANKNIFTY_real", "BANKNIFTY_mirror", "BANKNIFTY_live_real",
         "BANKNIFTY_live_mirror", "SYNTH_real", "SYNTH_mirror")
STORE = os.environ.get("ATP_PRIVATE_FIXTURES")


def _root():
    if not STORE:
        pytest.skip("ATP_PRIVATE_FIXTURES not set: the parity fixtures store is on the host only")
    root = R.snapshot_root(STORE)
    if not os.path.isfile(os.path.join(root, "MANIFEST.json")):
        pytest.fail(f"ATP_PRIVATE_FIXTURES is set but {root}/MANIFEST.json is missing")
    return root


def test_store_holds_the_snapshot_cases():
    root = _root()
    assert tuple(R.cases(root)) == CASES
    import json
    assert json.load(open(os.path.join(root, "MANIFEST.json")))["commit"] == R.COMMIT


@pytest.mark.parametrize("case", CASES)
def test_layer1_is_byte_equal(case):
    r = R.compare_case(_root(), 1, case)
    assert r["settings_equal"], "the engine's reading settings differ from the fixture's settings.json"
    assert r["equal"], f"layer 1 {case}: first different line {r['first_diff']} ({r['expected']} expected, {r['produced']} produced)"
