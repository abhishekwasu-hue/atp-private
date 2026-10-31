"""The skeleton imports, reports its version, and fails closed: no engine is imported yet."""
import importlib
import re

import pytest

import atp_private


def test_version_and_not_imported_status():
    assert re.fullmatch(r"\d+\.\d+\.\d+", atp_private.__version__)
    state = atp_private.status()
    assert state["version"] == atp_private.__version__
    assert state["engine_imported"] is False
    assert state["status"] == "engine package present, engine not yet imported"


@pytest.mark.parametrize("module", ["atp_private.trade_engine", "atp_private.chart_analyze"])
def test_engine_entry_points_fail_closed(module):
    mod = importlib.import_module(module)
    assert mod.ENGINE_IMPORTED is False
    with pytest.raises(atp_private.EngineNotImported, match="not yet imported"):
        mod.get_provider()
