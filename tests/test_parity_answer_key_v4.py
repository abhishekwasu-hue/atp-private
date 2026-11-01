"""M79 W3: answer_key_v4 comparison (answer_key_v4/<id>/reading.json: the owner's object, its states and lifecycle events, the alive
areas, the Daily side and the decision row at the item's window end), built on each item's own fixture inputs.

Same store rules as tests/test_parity_layer1.py (ATP_PRIVATE_FIXTURES; unset: visible skip; set but empty: failure).
"""
import pytest

from atp_private.parity import extras as X
from test_parity_layer1 import _root                               # tests/ is on sys.path (pytest, no __init__.py)

ITEMS = ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08")


def test_store_lists_the_items():
    assert tuple(X._manifest(_root())["answer_key_v4"]) == ITEMS


@pytest.mark.parametrize("item_id", ITEMS)
def test_answer_key_reading_is_byte_equal(item_id):
    assert X.compare_answer_key(_root(), item_id), f"answer_key_v4/{item_id}/reading.json differs"
