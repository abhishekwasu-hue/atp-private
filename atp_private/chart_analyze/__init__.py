"""atp_private.chart_analyze: the Analyze-a-chart engine that ATP's `backend/app/chart_analyze/provider.py` imports.

NOT YET IMPORTED. `get_provider()` raises `EngineNotImported`; ATP's loader then reports "the engine failed to start
(EngineNotImported)" and keeps the feature off (health: "chart analysis engine: MISSING ..."). No method text here.
"""
from atp_private import EngineNotImported

ENGINE_IMPORTED = False


def get_provider():
    raise EngineNotImported(__name__)
