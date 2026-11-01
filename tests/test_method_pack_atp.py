"""M79 W6 (T7): ATP's own KB / Method Pack under knowledge/ - stale-pack test, the tag version, the snapshot copy.

Text only, no API call. The copied Trade test (atp_private/trade_engine/tests/test_method_pack.py) keeps checking
the snapshot's own copy; this file checks the copy ATP edits from now on.
"""
import filecmp
import os
import re

from atp_private import method_pack as P
from atp_private.trade_engine.vision import method_pack as MP


def test_committed_pack_equals_regenerated_from_kb():
    text, ver = P.build()
    with open(P.PACK_PATH, encoding="utf-8") as fh:
        assert fh.read() == text, "knowledge/method_pack.md stale: rebuild it (atp_private.method_pack.write) and commit"
    assert P.load() == (text, ver)


def test_version_header_is_the_body_hash():
    with open(P.PACK_PATH, encoding="utf-8") as fh:
        ver, body = MP.split(fh.read())
    assert re.fullmatch(r"[0-9a-f]{12}", ver) and ver == MP.version_of(body)


def test_pack_rules_hold():
    text, _ = P.build()
    assert MP.banned_hits(text) == []
    assert MP.TOKENS_MIN <= MP.tokens_estimate(text) <= MP.TOKENS_MAX


def _files(root):
    return sorted(os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs
                  if "__pycache__" not in d)


def test_unchanged_kb_is_the_snapshot_copy_at_the_tag_version():
    """While the pack version is the tag's, knowledge/ is byte for byte the snapshot's text (an edit without a new
    version is caught; an approved KB change moves the version and this check no longer applies)."""
    if P.version() != P.TAG_VERSION:
        return
    assert _files(P.KNOWLEDGE) == _files(P.SNAPSHOT)
    _, mismatch, errors = filecmp.cmpfiles(P.KNOWLEDGE, P.SNAPSHOT, _files(P.SNAPSHOT), shallow=False)
    assert mismatch == [] and errors == []


def test_snapshot_pack_version_is_the_stable_row():
    assert MP.load()[1] == P.TAG_VERSION


# --- W7 / T8: the Vision method checklist (audit only) -----------------------------------------------------------------

def _answer(ver, verdict="agree", status="pass"):
    return {"pack_version": ver, "verdict": verdict,
            "items": [{"n": n, "status": status, "evidence": "structure as listed"} for n in range(1, 8)]}


def test_vision_checklist_carries_the_pack_as_prefix():
    c = P.vision_checklist()
    text, ver = P.load()
    assert c["pack_version"] == ver and c["system_prefix"] == text
    assert sorted(c["items"]) == list(range(1, 8)) and "audit only" in c["schema_text"]


def test_vision_answer_is_checked_against_this_pack():
    ver = P.version()
    ok, why = P.vision_validate(_answer(ver))
    assert why is None and ok["verdict"] == "agree"
    assert P.vision_validate(_answer("0" * 12))[0] is None                 # another pack version: refused
    assert P.vision_validate(_answer(ver, status="fail"))[0] is None       # agree with a failed item: refused
    assert P.vision_validate(_answer(ver), known_prices=set())[0] is not None
