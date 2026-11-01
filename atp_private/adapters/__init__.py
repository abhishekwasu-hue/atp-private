"""atp_private.adapters: ATP-GENERIC stand-ins for Trade modules the engine snapshot left out (owner order M79, C6).

The snapshot under `atp_private/trade_engine/` is copied AS IS (import paths only). Some of its modules import Trade
modules that are not engine logic and were not copied (Trade's `config`, `cloud_db`, `upstox_api`, ...). An adapter here
gives the engine the same names, backed by ATP, with no method logic and no change to any copied file. An adapter is
only installed where the snapshot has no module of that name, so a real port always wins.

Installed today: `config` (the IST clock helpers). Not yet ported (the copied tests that need them are skipped with a
reason, see the repository's conftest.py): `cloud_db`, `upstox_api` (Upstox token and instrument keys from ATP's own
Upstox app, M79 W8), and Trade scripts / research files that are read by path.
"""
import importlib
import importlib.util
import sys
from typing import Dict, List

#: snapshot module name -> adapter module that stands in for it.
ADAPTERS: Dict[str, str] = {
    "atp_private.trade_engine.config": "atp_private.adapters.trade_config",
}


def install() -> List[str]:
    """Register each adapter under its snapshot name when the snapshot has no such module. Returns the names installed.
    Idempotent; never replaces a module the snapshot itself provides."""
    installed = []
    for name, adapter in ADAPTERS.items():
        if name in sys.modules:
            continue
        if importlib.util.find_spec(name) is not None:
            continue
        module = importlib.import_module(adapter)
        sys.modules[name] = module
        parent, _, child = name.rpartition(".")
        setattr(importlib.import_module(parent), child, module)
        installed.append(name)
    return installed
