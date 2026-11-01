"""atp_private.trade_engine: the Trade signal engine / chart reader, run inside ATP (ATP order M66; was
`atp_private.reader` in the older plan, PRIVATE_PACKAGE.md section 9).

The engine snapshot engine-snapshot-v2 (Trade commit 813358b) is imported here (owner order M79 W1; original module
paths under this package, unmodified apart from import paths). `get_provider()` returns the signal-engine shim (EN-1,
`provider.py`) that adapts the engine's live path to ATP's public provider interface (`app/engine_provider/`). It needs
ATP's backend on the import path (the host's backend process); without it the shim fails to start and ATP's loader
reports the engine as unavailable, never crashing. ATP's `trade_engine` flag stays OFF (owner's switch).
"""
#: True: the signal-engine shim (EN-1) is built on the imported snapshot (see SNAPSHOT_TAG).
ENGINE_IMPORTED = True
#: The Trade snapshot this package was imported from (verified by commit, owner order M79 C2; no git tag yet).
SNAPSHOT_TAG = "engine-snapshot-v2"
SNAPSHOT_COMMIT = "813358bc1064645fcf2ca005959d9658804633e3"
TAG = SNAPSHOT_TAG


def get_provider():
    from atp_private.trade_engine.provider import get_provider as _get
    return _get()
