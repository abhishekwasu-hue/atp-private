"""Repository-level test setup for the copied Trade tests (owner order M79, W1 / C6).

The copied tests under `atp_private/trade_engine/tests/` are not edited. Their known failures in ATP come from Trade
dependencies the snapshot left out on purpose (ATP-GENERIC code, Trade scripts, repo market data). Each one is handled
here in one of two ways, never by a logic change:

1. an ATP adapter (atp_private/adapters/): installed before any test module is imported;
2. a visible skip whose reason names the left-out dependency. A skip applies only while that dependency is missing, so
   a test runs again by itself once the dependency is ported or the file is present.
"""
import importlib.util
from pathlib import Path

import pytest

from atp_private import adapters

adapters.install()

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "atp_private" / "trade_engine"
TESTS = "atp_private/trade_engine/tests/"

NOT_PORTED = "ATP adapter not ported yet"
BY_PATH = "Trade file read by path, not in the snapshot"
REPO_DATA = "repo data file not in the package (market data stays out of the repository)"


def _module_missing(name):
    try:
        return importlib.util.find_spec(name) is None
    except ModuleNotFoundError:                                          # a parent package is missing
        return True


def _file_missing(rel):
    return not (ENGINE / rel).exists()


# (need kind, need, reason). kind "module": module name(s) that must be importable; "file": a path under trade_engine/.
_CLOUD_DB = ("module", ("atp_private.trade_engine.cloud_db", "atp_private.trade_engine.upstox_api"),
             f"{NOT_PORTED}: cloud_db + upstox_api (Upstox token and instrument keys from ATP's own Upstox app, M79 W8)")

#: whole test modules that cannot be imported without the dependency (they error at collection otherwise).
SKIP_MODULES = {
    "test_golden_vision_check.py": ("module", "atp_private.trade_engine.scripts.golden_vision_check",
                                    "Trade script module not in the snapshot: scripts/golden_vision_check.py"),
    "test_index_candles_fetch.py": ("module", "research",
                                    "Trade research module not in the snapshot: research/ (imported as top-level `research`)"),
    "test_major_levels.py": ("file", "research/major_levels_eval.py", f"{BY_PATH}: research/major_levels_eval.py"),
    "test_verify_opportunity_data_availability.py": _CLOUD_DB,
}

#: single tests (module file, test name prefix) that need the dependency.
SKIP_TESTS = {
    ("test_decision3_daily_review.py", "test_view_script_logs_elliott_vs_dow"):
        ("file", "scripts/v22_daily_swings_view.py", f"{BY_PATH}: scripts/v22_daily_swings_view.py"),
    ("test_engine3_feed.py", "test_minute_history_includes_previous_trading_day"): _CLOUD_DB,
    ("test_engine3_feed.py", "test_gap_fill_fetches_missing_weekday_and_skips_holiday"): _CLOUD_DB,
    ("test_engine3_feed.py", "test_daily_history_still_ends_today"): _CLOUD_DB,
    ("test_m56_dp_builders.py", "test_every_builder_uses_the_one_helper"):
        ("file", "vision/worker.py", f"{BY_PATH}: vision/worker.py"),
    ("test_v6_cache.py", "test_timing_line_is_log_only"):
        ("file", "scripts/engine_signal_run.py", f"{BY_PATH}: scripts/engine_signal_run.py"),
    ("test_v6_cache.py", "test_vps_proof_block_is_read_only"):
        ("file", "scripts/v6_cache_proof_vps.sh", f"{BY_PATH}: scripts/v6_cache_proof_vps.sh"),
}

#: tests that use this fixture in these modules read Trade's repo parquet file.
SKIP_FIXTURE = ("nifty1m", {"test_elliott_counts.py", "test_elliott_swings.py"},
                ("file", "data/nifty50_1min.parquet", f"{REPO_DATA}: data/nifty50_1min.parquet"))


def _unmet(need):
    kind, what, reason = need
    names = what if isinstance(what, tuple) else (what,)
    missing = any(_module_missing(n) for n in names) if kind == "module" else _file_missing(what)
    return reason if missing else None


class _SkippedModule(pytest.Module):
    """A copied test module that is reported as skipped (with its reason) instead of being imported."""

    def collect(self):
        pytest.skip(self.config.stash[_REASONS][str(self.path)])


_REASONS = pytest.StashKey[dict]()


def pytest_configure(config):
    config.stash[_REASONS] = {}


def _in_copied_tests(path):
    return TESTS in Path(path).resolve().as_posix()


def pytest_pycollect_makemodule(module_path, parent):
    if not _in_copied_tests(module_path):
        return None
    need = SKIP_MODULES.get(Path(module_path).name)
    reason = _unmet(need) if need else None
    if reason is None:
        return None
    parent.config.stash[_REASONS][str(module_path)] = reason
    return _SkippedModule.from_parent(parent, path=Path(module_path))


def pytest_collection_modifyitems(config, items):
    fixture, fixture_modules, fixture_need = SKIP_FIXTURE
    for item in items:
        path = Path(str(item.fspath))
        if not _in_copied_tests(path):
            continue
        name = item.name.split("[")[0]
        need = SKIP_TESTS.get((path.name, name))
        if need is None and path.name in fixture_modules and fixture in getattr(item, "fixturenames", ()):
            need = fixture_need
        reason = _unmet(need) if need else None
        if reason:
            item.add_marker(pytest.mark.skip(reason=reason))
