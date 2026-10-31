"""M50 A1 (owner: rebuild the fixture so it keeps its intent under SW, swing / trend data realistic): the synthetic 15M fixtures carry
~30 sessions, so the Daily the engine cuts from them (`pivots.charts.daily_from_15m`) holds two external swings and SW3 reads UNKNOWN —
while the live engine always gets the full stored Daily history (engine3_live: years of Upstox Daily bars). This puts a realistic
Daily history in front of the fixture's own window, as live does: a staircase in the direction the fixture opens with (its first
sessions — never its end, so a replay cut at any bar sees the same history), external swings well beyond the window, ending at the
window's first open. The 15M window, its bars and every assert stay exactly as they are."""
import contextlib

import numpy as np
import pandas as pd

LEGS, LEG, BACK, DAYS_PER_LEG, OPENING = 8, 0.07, 0.035, 7, 10    # fixture shape (test data, not a reading rule)
SYNTHETIC_FROM = pd.Timestamp("2030-01-01")                     # the tests' synthetic fixtures are dated 2030+; real data never is


def history(d):
    """Daily bars before the window `d` (same columns): LEGS impulse legs of LEG and pullbacks of BACK in the opening direction."""
    k = min(OPENING, len(d)) - 1
    sgn = 1 if d["close"].iloc[k] > d["open"].iloc[0] else -1      # the direction the fixture opens with (first sessions only)
    p0 = float(d["open"].iloc[0])
    path = [p0]
    for _ in range(LEGS):                                          # walk back from the window: each earlier leg starts further against it
        path.append(path[-1] * (1 - sgn * LEG))
        path.append(path[-1] * (1 + sgn * BACK))
    path = path[::-1]
    c = np.concatenate([np.linspace(a, b, DAYS_PER_LEG + 1)[1:] for a, b in zip(path[:-1], path[1:])])
    o = np.r_[path[0], c[:-1]]
    pad = np.abs(c - o) * 0.3 + p0 * 0.0012
    days = pd.bdate_range(end=pd.Timestamp(d["timestamp"].iloc[0]).normalize() - pd.Timedelta(days=1), periods=len(c))
    out = pd.DataFrame({"timestamp": days, "open": o, "high": np.maximum(o, c) + pad, "low": np.minimum(o, c) - pad, "close": c})
    if "bar_end" in d.columns:
        out["bar_end"] = out["timestamp"] + (pd.Timestamp(d["bar_end"].iloc[0]) - pd.Timestamp(d["timestamp"].iloc[0]))
    for col in d.columns:
        if col not in out.columns:
            out[col] = d[col].iloc[0]
    return out[list(d.columns)]


def with_history(d):
    """History in front of a SYNTHETIC window only — a real-data window (owner real-day tests) is returned as it is."""
    d = d.reset_index(drop=True)
    if not len(d) or pd.Timestamp(d["timestamp"].iloc[0]) < SYNTHETIC_FROM:
        return d
    return pd.concat([history(d), d], ignore_index=True)


@contextlib.contextmanager
def unpatched():
    """The window-only Daily inside a module that sits on the history — for a test whose pinned digests were taken without it."""
    from atp_private.trade_engine.pivots import charts as PC
    mp = __import__("pytest").MonkeyPatch()
    mp.setattr(PC, "daily_from_15m", getattr(PC.daily_from_15m, "window_only", PC.daily_from_15m))
    try:
        yield
    finally:
        mp.undo()


@contextlib.contextmanager
def patched():
    """V22 (no daily_df given) ⇒ the window's Daily with the history in front, for the duration of the block."""
    from atp_private.trade_engine.pivots import charts as PC
    orig = PC.daily_from_15m
    mp = __import__("pytest").MonkeyPatch()
    def daily(m15, end):
        return with_history(orig(m15, end))
    daily.window_only = orig
    mp.setattr(PC, "daily_from_15m", daily)
    try:
        yield
    finally:
        mp.undo()
