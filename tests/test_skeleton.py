"""The package imports, reports its version and state; the signal-engine entry point still fails closed (EN-1 not built)."""
import re

import pytest

import atp_private
import atp_private.trade_engine as trade_engine


def test_version_and_imported_status():
    assert re.fullmatch(r"\d+\.\d+\.\d+", atp_private.__version__)
    state = atp_private.status()
    assert state["version"] == atp_private.__version__
    assert state["engine_imported"] is True
    assert state["status"] == "engine imported"


def test_signal_engine_entry_point_fails_closed_until_its_shim():
    assert trade_engine.ENGINE_IMPORTED is False
    assert trade_engine.SNAPSHOT_TAG == "engine-snapshot-v2"
    with pytest.raises(atp_private.EngineNotImported, match="not yet imported"):
        trade_engine.get_provider()
