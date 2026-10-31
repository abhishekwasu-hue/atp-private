"""V6 (owner 26 Oct evening): the Levels._obj_start cache changes speed only — the memo answers exactly what the uncached search
answers for every object; the cycle-time line is log only; the VPS proof block is read-only (dry-run, cron lock, live tree untouched)."""
import os
import subprocess

import numpy as np
import pandas as pd

from atp_private.trade_engine.decision3 import engine as E3
from atp_private.trade_engine.tests import oct12_fixture as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _uncached(lv, L):
    if L.base_ts is not None:
        return int(np.searchsorted(lv.ts.to_numpy(), np.datetime64(pd.Timestamp(L.base_ts)), side="left")) - (
            1 if pd.Timestamp(L.base_ts) < lv.ts.iloc[0] else 0)
    return int(L.base_bar) if L.base_bar is not None else int(L.born_bar)


def test_obj_start_memo_equals_the_uncached_search_for_every_object():
    for mirror in (False, True):
        m15, fut, ltf = F.build(mirror=mirror)
        lv = E3.V22(m15, ltf=ltf, futures=fut).levels
        assert lv.L and any(L.base_ts is not None for L in lv.L)
        for _ in range(2):                                               # second pass = served from the memo
            assert [lv._obj_start(L) for L in lv.L] == [_uncached(lv, L) for L in lv.L]


def test_timing_line_is_log_only():
    import importlib.util
    spec = importlib.util.spec_from_file_location("esr", os.path.join(ROOT, "scripts", "engine_signal_run.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    line = m._timing_line("NIFTY", "decision3", 12.34)
    assert line.startswith("⏱️ NIFTY [decision3] cycle 12.3 s · peak RSS ") and line.endswith((" MB", "NA"))


def test_vps_proof_block_is_read_only():
    p = os.path.join(ROOT, "scripts", "v6_cache_proof_vps.sh")
    assert subprocess.run(["bash", "-n", p]).returncode == 0
    src = open(p, encoding="utf-8").read()
    assert "--dry-run --force" in src and "flock /tmp/engine_signal_run.lock" in src and "--revert" in src
    assert "ENGINE3_CACHE_DIR=" in src and "git worktree add" in src
    assert 'export ENGINE_SIGNAL_DB="$W/engine_signals.db"' in src and "mode=ro" in src   # the dry-run opens a COPY of the store
    assert "replay_day.py" in src and "--window all --dry-run" not in src                 # no approval PNG path inside the parity JSON
    for never in ("save_settings", "systemctl", "git checkout", "git reset", "crontab", "LIVE"):
        assert never not in src
