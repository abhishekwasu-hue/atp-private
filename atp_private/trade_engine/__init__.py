"""atp_private.trade_engine: the Trade signal engine / chart reader, run inside ATP (ATP order M66; was
`atp_private.reader` in the older plan, PRIVATE_PACKAGE.md section 9).

NOT YET IMPORTED. The Trade session copies the engine snapshot here per Trade order M65 (original module paths under
this package, unmodified apart from import paths). A shim in this file then adapts it to ATP's public provider
interface (`app/engine_provider/`, EN-1). Until both land, `get_provider()` raises `EngineNotImported`; ATP's loader
treats any exception from `get_provider()` as "engine unavailable" and never crashes.
"""
from atp_private import EngineNotImported

ENGINE_IMPORTED = False
#: The Trade snapshot tag this package was imported from (set by the M65 import PR).
SNAPSHOT_TAG = None


def get_provider():
    raise EngineNotImported(__name__)
