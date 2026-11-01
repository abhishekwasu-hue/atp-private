"""atp_private: ATP's private package (method / engine code lives only here, never in the public ATP repository).

The Trade engine snapshot engine-snapshot-v2 (Trade commit 813358b) is imported under `atp_private/trade_engine/`
(owner order M79, W1). Entry points for ATP's loaders:
- `atp_private.chart_analyze.get_provider()`: the Analyze-a-chart provider (M79 W5), built on the snapshot's Method Pack.
- `atp_private.trade_engine.get_provider()`: the signal-engine provider; its shim (EN-1) is not built yet, so it still
  fails closed with `EngineNotImported` and ATP's signal engine stays off.
"""
from typing import Dict

__version__ = "0.1.0"

#: True: the Trade engine snapshot (engine-snapshot-v2) is imported and the Analyze-a-chart shim is in place (M79 W5).
ENGINE_IMPORTED = True
STATUS_NOT_IMPORTED = "engine package present, engine not yet imported"


class EngineNotImported(RuntimeError):
    """Raised by an entry point whose shim is not built yet (today: `atp_private.trade_engine.get_provider()`)."""

    def __init__(self, module: str) -> None:
        super().__init__(f"{module}: {STATUS_NOT_IMPORTED}")
        self.module = module


def status() -> Dict[str, object]:
    """The package's state, for CI and the owner: version and whether an engine is imported (no engine text)."""
    return {
        "package": "atp_private",
        "version": __version__,
        "engine_imported": ENGINE_IMPORTED,
        "status": "engine imported" if ENGINE_IMPORTED else STATUS_NOT_IMPORTED,
    }
