"""The package imports and reports its version and state; the signal-engine entry point is the EN-1 shim."""
import re

import atp_private
import atp_private.trade_engine as trade_engine


def test_version_and_imported_status():
    assert re.fullmatch(r"\d+\.\d+\.\d+", atp_private.__version__)
    state = atp_private.status()
    assert state["version"] == atp_private.__version__
    assert state["engine_imported"] is True
    assert state["status"] == "engine imported"


def test_signal_engine_entry_point_is_the_shim():
    assert trade_engine.ENGINE_IMPORTED is True
    assert trade_engine.SNAPSHOT_TAG == "engine-snapshot-v2"
    assert trade_engine.TAG == "engine-snapshot-v2"
    assert callable(trade_engine.get_provider)
