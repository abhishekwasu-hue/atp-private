"""The signal-engine shim (ATP order M66 EN-1; owner order M79): the imported Trade engine (engine-snapshot-v2, Trade
commit 813358b) behind ATP's public provider interface (`backend/app/engine_provider/contract.py`, interface 1).

New ATP-side code only. The engine's own live path runs AS IS: `engine3_live.v22_settings`, `build_inputs`, `load_m1`,
`h1_history_of` and `evaluate` (the steps of `engine3_live.compute`, in its order; `compute` itself is not called only
because its trigger-bar revision step needs the previous stored row, which ATP does not keep: with no previous row that
step does nothing). Nothing of the engine is edited. What this module adds:

- `RequestFeed`: the feed the live path reads (`index`, `futures`, `stored_bars`), served from the bars ATP handed in
  (`EngineRequest.frames`) instead of Upstox. Same windows as the live feed: `index(..., days)` = the bars of the last
  `days` calendar days up to the read time; `stored_bars(..., days, before)` = the bars before the date `before`, back
  `days`. No network, no broker, no disk store.
  - The futures volume ATP hands in is already the near-month contract's (contract.py), one value per 5-minute bar.
    Each row's `expiry` is set to its own day, so the engine's near-month filter keeps every row as one series; a bar
    with no futures volume is left out (the engine then reads "no FUT bar" there). Futures prices are not handed in by
    ATP and are left empty (the engine reads only the futures volume).
  - Daily bars are dated by their day (as Upstox's daily candles are).
- The read time: the bars ATP hands in are final (closed bars only), so the live path's "a bar is final only N seconds
  after its close" wait is already met; `now` = `as_of` + the engine's own final grace (setting
  `engine3_bar_final_grace_s`).
- The result: the decision row of the last closed trigger candle mapped to the interface's generic fields (below).

Mapping (generic fields only; a value the engine does not give stays empty):
- areas: the row's `active_levels` (side from the area's role: support = buyer, resistance = seller; state = the
  engine's own state, lower case; formed_at = the close of the area's birth bar).
- higher_side: the row's Daily side (`daily_trend`: UP = up, DOWN = down, RANGE = sideways, anything else = unclear).
- signals: one per fired entry model of the candle (`entries`): model id, the visited area as the entry zone, the
  internal invalidation reference, the evidence list (present / absent as the engine lists it; "not available" items
  are left out), the entry's key as the instance id. The card carries the trend the entry was read with, the side, the
  timeframe, the symbol and the area as a range only (no setup / step / evidence token: those need a public phrase
  table for the engine's words, an owner decision).
- swings: none yet (the interface needs HH / HL / LH / LL labels; the engine's pivots carry none).
- data_problems: the live path's own fail-closed errors as tokens (no signal then).

PAPER only; the `trade_engine` flag stays OFF. This module has no order, broker or execution import; nothing here
places, blocks or changes an order (ADR-0004 / ADR-0006). `read` holds a lock: the engine keeps process-wide state.
"""
import contextlib
import datetime as dt
import io
import threading
import warnings
from zoneinfo import ZoneInfo

import pandas as pd

from atp_private import adapters

adapters.install()

NAME = "atp-trade-engine"
TAG = "engine-snapshot-v2"
VERSION = "engine-snapshot-v2+813358b"
TIMEFRAMES = ("1m", "5m", "15m", "1d")
IST = ZoneInfo("Asia/Kolkata")
INTERVALS = {"1minute": "1m", "5minute": "5m", "15minute": "15m", "day": "1d"}
TF_KEYS = {"5M": "5m", "15M": "15m", "1H": "1h", "D": "1d", "W": "1w"}
AREA_SIDE = {"support": "buyer", "resistance": "seller"}
DAILY_SIDE = {"UP": "up", "DOWN": "down", "RANGE": "sideways"}
CARD_TREND = {"UP": "up", "DOWN": "down", "RANGE": "range"}
COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# data_problems tokens (the live path's fail-closed errors)
UNKNOWN_INSTRUMENT = "unknown_instrument"
INVALID_SETTINGS = "invalid_settings"
MISSING_FUTURES_VOLUME = "missing_futures_volume"
BAR_NOT_FINAL = "bar_not_final"
INSUFFICIENT_DATA = "insufficient_data"

_LOCK = threading.Lock()


def instrument_of(symbol):
    """ATP's instrument key ("NSE_INDEX:Nifty 50") or an engine name ("NIFTY") ⇒ the engine's instrument name, or None."""
    import atp_private.trade_engine.instruments as INS
    s = str(symbol or "").strip()
    if s.upper() in INS.REGISTRY:
        return s.upper()
    key = _flat(s)
    return next((n for n, x in INS.REGISTRY.items() if _flat(x["key"]) == key), None)


def _flat(key):
    """An instrument key in one spelling: the broker's ("NSE_INDEX|Nifty 50"), ATP's broker form ("NSE_INDEX:Nifty 50")
    and ATP's lake key ("NSE_INDEX:NIFTY50", "NSE_INDEX:NIFTYBANK", "BSE_INDEX:SENSEX") are the same instrument."""
    prefix, _, name = str(key).replace(":", "|", 1).partition("|")
    return f"{prefix.upper()}|{name.replace(' ', '').upper()}"


def _naive(t):
    """A timezone-aware time ⇒ naive India time (the engine's frames are naive IST)."""
    return t.astimezone(IST).replace(tzinfo=None)


class RequestFeed:
    """The live path's feed, served from the request's bars (see the module text)."""

    def __init__(self, request):
        self.frames = request.frames
        self.today = _naive(request.as_of).date()

    def _rows(self, tf, since=None, before=None):
        frame = self.frames.get(tf)
        out = []
        for b in (frame.bars if frame is not None else ()):
            t = _naive(b.start)
            day = t.date()
            if (since is not None and day < since) or (before is not None and day >= before):
                continue
            out.append((pd.Timestamp(day) if tf == "1d" else pd.Timestamp(t), b))
        return out

    def _frame(self, rows):
        if not rows:
            return pd.DataFrame(columns=COLUMNS)
        df = pd.DataFrame([[t, b.open, b.high, b.low, b.close, 0.0 if b.volume is None else float(b.volume)] for t, b in rows],
                          columns=COLUMNS)
        df["timestamp"] = df["timestamp"].astype("datetime64[ns]")
        return df

    def index(self, symbol, interval, days):
        tf = INTERVALS[interval]
        return self._frame(self._rows(tf, since=self.today - dt.timedelta(days=int(days))))

    def futures(self, symbol, interval, days):
        tf = INTERVALS[interval]
        frame = self.frames.get(tf)
        vol = frame.futures_volume if frame is not None else None
        if vol is None:
            return pd.DataFrame(columns=COLUMNS + ["expiry"])
        since = self.today - dt.timedelta(days=int(days))
        rows = [(pd.Timestamp(_naive(b.start)), v) for b, v in zip(frame.bars, vol)
                if v is not None and _naive(b.start).date() >= since]
        nan = float("nan")
        df = pd.DataFrame([[t, nan, nan, nan, nan, float(v)] for t, v in rows], columns=COLUMNS)
        df["timestamp"] = df["timestamp"].astype("datetime64[ns]")
        df["expiry"] = df["timestamp"].dt.normalize()                      # near-month already (ATP); one series
        return df

    def stored_bars(self, symbol, interval, days, before, max_chunks=None):
        """Candles ([ts, o, h, l, c, v, oi]) of `interval` before the date `before`, back `days` (as UpstoxFeed.stored_bars)."""
        tf = INTERVALS[interval]
        rows = self._rows(tf, since=self.today - dt.timedelta(days=int(days)), before=before)
        return [[t.isoformat(), b.open, b.high, b.low, b.close, 0.0 if b.volume is None else float(b.volume), 0.0] for t, b in rows]


@contextlib.contextmanager
def _captured_v22():
    """The V22 object the live path builds (read for the areas' birth-bar times): `engine3_live.decide_live` is wrapped
    for the duration of one read and records the V it is given, then runs unchanged. The engine's classes are untouched
    (a V22 subclass changes the engine's behaviour, so it is not used)."""
    import atp_private.trade_engine.engine3_live as L
    orig, got = L.decide_live, []

    def decide_live(V, since=None):
        got.append(V)
        return orig(V, since)

    L.decide_live = decide_live
    try:
        yield got
    finally:
        L.decide_live = orig


def _ist(x):
    return pd.Timestamp(x).to_pydatetime().replace(tzinfo=IST)


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


class Provider:
    """ATP's TradeEngineProvider (interface 1) on the imported engine's live path."""

    name = NAME
    version = VERSION
    tag = TAG
    interface = 1                                                          # the interface number this shim implements
    timeframes = TIMEFRAMES

    def __init__(self):
        from app.engine_provider import contract as C                      # ATP's backend (on the host: the same process)
        from app.signals.language import SignalStructure
        self.C, self.Card = C, SignalStructure

    def _problem(self, token):
        return self.C.EngineResult(interface=self.interface, version=VERSION, data_problems=(token,))

    def read(self, request):
        import atp_private.trade_engine.engine3_live as L
        symbol = instrument_of(request.symbol)
        if symbol is None:
            return self._problem(UNKNOWN_INSTRUMENT)
        s = dict(request.settings or {})
        from atp_private.adapters import trade_config
        with _LOCK, trade_config.use_calendar(request.calendar), warnings.catch_warnings(), \
                contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            try:
                s3 = L.v22_settings(s)
                now = pd.Timestamp(_naive(request.as_of)) + L.final_grace(s)
                feed = RequestFeed(request)
                m15, daily, ltf, fut, note = L.build_inputs(feed, symbol, now, s)
                m1, m1_info = L.load_m1(feed, symbol, m15, now, s)
                h1h, _h1_info = L.h1_history_of(feed, symbol, m15, now, s)
                with _captured_v22() as built:
                    r = L.evaluate(symbol, m15, daily, ltf, fut, s3=s3, m1=m1, m1_info=m1_info, since=None, h1_history=h1h)
            except L.SettingError:
                return self._problem(INVALID_SETTINGS)
            except L.FutVolumeMissing:
                return self._problem(MISSING_FUTURES_VOLUME)
            except L.BarLate:
                return self._problem(BAR_NOT_FINAL)
            except L.EngineDataError:
                return self._problem(INSUFFICIENT_DATA)
        V = built[-1] if built else None
        return self._result(symbol, r, V)

    def _area(self, a, V):
        C = self.C
        side = AREA_SIDE.get(str(a.get("role")))
        lo, hi = _num(a.get("lo")), _num(a.get("hi"))
        born = a.get("born_bar")
        if side is None or lo is None or hi is None or V is None or born is None or not 0 <= int(born) < len(V.m15):
            return None
        return C.Area(area_id=str(a.get("uid") or a.get("id")), side=side, state=str(a.get("state") or "").lower(),
                      band=C.PriceRange(min(lo, hi), max(lo, hi)), timeframe=TF_KEYS.get(str(a.get("tf")), str(a.get("tf"))),
                      formed_at=_ist(V.m15["bar_end"].iloc[int(born)]))

    def _signal(self, symbol, r, e):
        C = self.C
        a = e.get("area") or {}
        side = AREA_SIDE.get(str(a.get("role"))) or {1: "buyer", -1: "seller"}.get(e.get("direction"))
        lo, hi = _num(a.get("lo")), _num(a.get("hi"))
        if side is None or lo is None or hi is None:
            return None
        lo, hi = min(lo, hi), max(lo, hi)
        tf = TF_KEYS.get(str(e.get("trigger_tf") or r.get("trigger_tf")), "15m")
        ev = []
        for group in ("confirming", "context"):
            for k, v in sorted(((e.get("evidence_list") or {}).get(group) or {}).items()):
                if v in ("present", "absent"):
                    ev.append(C.Evidence(token=str(k), present=v == "present"))
        card = self.Card(trend=CARD_TREND.get(str(r.get("trend_used"))), side=side, timeframe=tf, symbol=symbol,
                         area_range=(lo, hi))
        return C.Signal(model_id=str(e.get("model")), timeframe=tf, bar_end=_ist(r["bar_end"]), side=side,
                        entry_zone=C.PriceRange(lo, hi), card=card,
                        area_id=None if a.get("uid") is None and a.get("id") is None else str(a.get("uid") or a.get("id")),
                        invalidation=_num(e.get("invalidation")), evidence=tuple(ev),
                        instance_id=None if e.get("key") is None else str(e.get("key")))

    def _result(self, symbol, r, V):
        C = self.C
        areas = tuple(x for x in (self._area(a, V) for a in r.get("active_levels") or []) if x is not None)
        ds = r.get("daily_trend")
        higher = None if ds is None else C.HigherTimeframeSide(side=DAILY_SIDE.get(str(ds), "unclear"), timeframe="1d")
        signals = tuple(x for x in (self._signal(symbol, r, e) for e in r.get("entries") or []) if x is not None)
        return C.EngineResult(interface=self.interface, version=VERSION, areas=areas, swings=(), higher_side=higher,
                              signals=signals)


def get_provider():
    return Provider()
