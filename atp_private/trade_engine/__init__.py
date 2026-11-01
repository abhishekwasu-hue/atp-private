"""atp_private.trade_engine: the Trade signal engine / chart reader, run inside ATP (ATP order M66; was
`atp_private.reader` in the older plan, PRIVATE_PACKAGE.md section 9).

The engine snapshot engine-snapshot-v2 (Trade commit 813358b) is imported here (owner order M79 W1; original module
paths under this package, unmodified apart from import paths). The shim that adapts it to ATP's public provider
interface (`app/engine_provider/`, EN-1) is NOT built yet: `get_provider()` raises `EngineNotImported`, and ATP's
loader treats that as "engine unavailable" and never crashes.
"""
from atp_private import EngineNotImported

#: False until the signal-engine shim (EN-1) is built. The snapshot itself is imported (see SNAPSHOT_TAG).
ENGINE_IMPORTED = False
#: The Trade snapshot this package was imported from (verified by commit, owner order M79 C2; no git tag yet).
SNAPSHOT_TAG = "engine-snapshot-v2"
SNAPSHOT_COMMIT = "813358bc1064645fcf2ca005959d9658804633e3"


def get_provider():
    raise EngineNotImported(__name__)
