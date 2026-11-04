"""atp_private.preopen: the pre-open charts (Daily / 1H / 15M) for ATP's own job (owner 4 Nov: "Default yes" to the four
pre-open chart answers - A: ATP's job sends them; the gap band; the official close; the phase in the title).

New ATP-side code only. The charts are the Trade pre-open's own (Trade 813358b, copied AS IS, import paths only):
`decision3.preopen_chart.render`, `scripts.level_gate_preopen.crux_facts` / `engine_watch_areas` / `weekly_trend`, and the
engine's own pre-open read `engine3_live.watched_levels` (its V22, its Daily side `engine_trend_ctx`, its watch list). The
bars are the ones ATP hands in (`EngineRequest.frames`, served by the provider's `RequestFeed`): no network, no broker.

What this module adds (owner-approved, display only - no reading rule, no number):
- `last` = the official close (the NSE index file's close of the last session) when ATP hands it in, else the Daily
  close of the bars; every distance on the chart is measured from that same close (the watch list keeps the reader's
  areas; only their distance to the shown close is re-measured, and the nearest area is the nearest to that close).
- `gap_band`: the last opening gap that is not filled (`decision3.gaps.opening_gaps`, the reader's own gap and fill
  words), drawn as a band.
- `phase`: the Daily fold's phase (impulse / correction / origin broken) beside the trend in the title, only when the
  fold's trend is the engine's Daily trend (otherwise the title shows the trend alone, as before).

PAPER only; this module has no order, broker or execution import (ADR-0004 / ADR-0006).
"""
import contextlib
import datetime as dt
import io
import warnings

import pandas as pd

PHASE_WORDS = {"impulse": "impulse", "correction": "correction", "origin_broken": "origin broken"}


def _dist(lo, hi, last):
    """Distance of a band from the close: 0 inside, else to the nearer edge (the reader's own measure, `chart_reading`)."""
    if lo <= last <= hi:
        return 0.0
    return float(lo - last) if lo > last else float(last - hi)


def remeasure(watch, last):
    """The engine's watch items with `dist` from `last` (copies; the reader's list is not changed), nearest first (stable)."""
    out = [{**x, "dist": _dist(float(x["lo"]), float(x["hi"]), float(last))} for x in watch]
    return sorted(out, key=lambda x: x["dist"])


def last_unfilled_gap(V):
    from atp_private.trade_engine.decision3 import gaps as GP
    if (getattr(V, "s", None) or {}).get("opening_gaps", "on") != "on":
        return None
    open_ = [g for g in GP.opening_gaps(V, len(V.m15) - 1) if g.get("fill") != "filled"]
    if not open_:
        return None
    g = open_[-1]
    lo, hi = sorted((float(g["zone"][0]), float(g["zone"][1])))
    return {"lo": lo, "hi": hi, "dir": g["dir"], "fill": g["fill"]}


def newest_close(daily, m15):
    """No official close handed in: the close of the newest bar ATP has (the Daily bar, or the last 15M bar when the bars
    reach a later session than the Daily bars) and its day - never an older close than the candles drawn."""
    d_day = pd.Timestamp(daily["timestamp"].iloc[-1]).date() if len(daily) else None
    m_day = pd.Timestamp(m15["timestamp"].iloc[-1]).date() if m15 is not None and len(m15) else None
    if m_day is not None and (d_day is None or m_day > d_day):
        return float(m15["close"].iloc[-1]), m_day
    return (float(daily["close"].iloc[-1]), d_day) if d_day is not None else (None, None)


def phase_of(V, ctx):
    st = V.daily[-1] if getattr(V, "daily", None) else None
    if st is None or not ctx or st.trend != ctx.get("trend"):
        return None
    return PHASE_WORDS.get(str(st.phase))


def build(request, official_close=None):
    """The pre-open charts of one index: {"symbol", "items": [(tf, png, caption)], "errors": [...], "facts": {...}} or
    {"symbol", "problem": <reason>} when the engine cannot read the bars. `official_close` = (price, date) or None."""
    import atp_private.trade_engine.engine3_live as L
    from atp_private.adapters import trade_config
    from atp_private.trade_engine import provider as PV
    from atp_private.trade_engine.decision3 import preopen_chart as PCH
    from atp_private.trade_engine.scripts import level_gate_preopen as LGP
    sym = PV.instrument_of(request.symbol)
    if sym is None:
        return {"symbol": str(request.symbol), "problem": PV.UNKNOWN_INSTRUMENT}
    s = dict(request.settings or {})
    keep = {}
    log = io.StringIO()
    with PV._LOCK, trade_config.use_calendar(request.calendar), warnings.catch_warnings(), contextlib.redirect_stdout(log):
        warnings.simplefilter("ignore")
        try:
            now = pd.Timestamp(PV._naive(request.as_of)) + L.final_grace(s)
            levels = L.watched_levels(sym, PV.RequestFeed(request), now, s, keep=keep)
        except L.SettingError:
            return {"symbol": sym, "problem": PV.INVALID_SETTINGS}
        except L.EngineDataError:
            return {"symbol": sym, "problem": PV.INSUFFICIENT_DATA}
        V, ctx = keep.get("V"), keep.get("trend")
        if V is None or not ctx:
            return {"symbol": sym, "problem": PV.INSUFFICIENT_DATA}
        d = V.daily_df
        own_close, own_day = newest_close(d, V.m15)
        last = float(official_close[0]) if official_close else own_close
        watch = LGP.engine_watch_areas(levels)
        per_bot = [("engine", "engine", None if watch is None else remeasure(watch, last), None)]
        f, line, _ar = LGP.crux_facts(sym, ctx, last, per_bot, levels, V)
        f["last_word"] = "NSE close" if official_close else "last close"
        f["gap_band"] = last_unfilled_gap(V)
        f["phase"] = phase_of(V, ctx)
        try:
            weekly = LGP.weekly_trend(d.reset_index(drop=True), pd.Timestamp(PV._naive(request.as_of)).normalize())
        except Exception:                                                  # noqa: BLE001 - the title says n/a
            weekly = None
        items, errors = PCH.render(V, sym, f, weekly, line)
    when = official_close[1] if official_close else own_day
    return {"symbol": sym, "items": items, "errors": errors,
            "facts": {"trend": ctx.get("trend"), "phase": f["phase"], "weekly": weekly, "close": last,
                      "close_day": when.isoformat() if isinstance(when, dt.date) else when, "official": bool(official_close),
                      "gap": f["gap_band"], "areas": len(f.get("watched") or [])}}
