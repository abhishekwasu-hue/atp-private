"""atp_private: ATP's private package (method / engine code lives only here, never in the public ATP repository).

SKELETON. No engine has been imported yet: the Trade engine snapshot goes in under `atp_private/trade_engine/` (Trade
order M65), and the shim that adapts it to ATP's provider interface lands after that (ATP order M66, EN-1/EN-4).
Until then every engine entry point fails closed with `EngineNotImported`, so ATP's loaders report the engine as
unavailable instead of pretending to work.
"""
from typing import Dict

__version__ = "0.0.1"

#: False until the Trade engine snapshot (M65) and its shim are imported. Flip only in the PR that imports them.
ENGINE_IMPORTED = False
STATUS_NOT_IMPORTED = "engine package present, engine not yet imported"


class EngineNotImported(RuntimeError):
    """Raised by every `get_provider()` while the package is a skeleton (no engine code imported yet)."""

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
