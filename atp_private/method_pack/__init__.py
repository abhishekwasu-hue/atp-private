"""atp_private.method_pack: the KB and the Method Pack as ATP keeps them (owner order M79 W6 / port map T7).

`knowledge/` (repository root) holds the KB, the method, the owner's notes, the PA standard and the generated Method
Pack, copied once from the snapshot (`atp_private/trade_engine/docs/knowledge/`, engine-snapshot-v2, Trade 813358b)
with the same text. From here on it is edited only in `knowledge/`, under the change control of TRADE_TAKEOVER section
8: KB diff -> owner approves -> code -> test.

The pack is never edited by hand: it is built from the KB by the snapshot's own builder (`vision.method_pack.build`,
called AS IS with these paths) and the stale-pack test fails when the committed pack differs. Its version is the
body's content hash (12 hex), the value recorded in Trade's STABLE row for the snapshot (`TAG_VERSION`).

No API call; text only. Nothing here reaches ATP's public repository.
"""
import os

from atp_private.trade_engine.vision import method_pack as _MP

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KNOWLEDGE = os.path.join(ROOT, "knowledge")
KB_PATH = os.path.join(KNOWLEDGE, "KNOWLEDGE_BASE.md")
NOTES_PATH = os.path.join(KNOWLEDGE, "ABHI_METHOD_NOTES.md")
PACK_PATH = os.path.join(KNOWLEDGE, "method_pack.md")
SNAPSHOT = os.path.join(ROOT, "atp_private", "trade_engine", "docs", "knowledge")

#: the Method Pack version of Trade's STABLE row for the snapshot (KB / Method Pack column), engine-snapshot-v2.
TAG = "engine-snapshot-v2"
TAG_VERSION = "1674732c62ba"

PackError = _MP.PackError


def build():
    """(pack text, version) built from `knowledge/` by the snapshot's builder."""
    return _MP.build_from_repo(KB_PATH, NOTES_PATH)


def load():
    """(pack text, version) of the committed pack, checked (header = body hash); PackError otherwise."""
    return _MP.load(PACK_PATH)


def version():
    return load()[1]


def write():
    """Rebuild `knowledge/method_pack.md` from the KB (after an approved KB change). Returns the version."""
    text, ver = build()
    with open(PACK_PATH, "w", encoding="utf-8") as fh:
        fh.write(text)
    return ver


# --- T8: the Vision method checklist (owner order M79 W7) -------------------------------------------------------------
# ATP's Vision is audit only (ADR-0006): the checklist never places, blocks, sizes or changes an order, and its mode is
# human_confirm. This is the METHOD part only, from the snapshot's own V4 checklist (`vision.checklist`, AS IS): the
# Method Pack as the cached system prefix, the fixed output schema and the validator (fail-closed: wrong shape, a
# verdict that contradicts its items, another pack version, or any price-like number not in the facts). The provider
# call, the key (BYOK), the budget and the delivery stay ATP's own (`backend/app/ai/vision_audit.py`).

def vision_checklist():
    """{"pack_version", "system_prefix" (the pack text), "schema_text", "items" {n: (key, name, question)}} for one
    audit prompt. Text only; no API call."""
    from atp_private.trade_engine.vision import checklist as CK
    text, ver = load()
    return {"pack_version": ver, "system_prefix": text, "schema_text": CK.SCHEMA_TEXT,
            "items": {n: tuple(v) for n, v in CK.ITEMS.items()}}


def vision_validate(raw, known_prices=None, anchors=None):
    """The model's answer checked by the snapshot's validator against this pack's version (see `vision.checklist`).
    Returns what the validator returns; a refused answer is never shown as a result."""
    from atp_private.trade_engine.vision import checklist as CK
    return CK.validate(raw, pack_version=version(), known_prices=known_prices, anchors=anchors)
