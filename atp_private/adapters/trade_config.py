"""Adapter for Trade's `config` module, as `atp_private.trade_engine.config` (owner order M79, C6).

The snapshot uses only these names from Trade's `config` (checked against every `config` import in
`atp_private/trade_engine/`):
- `get_ist_now()` / `get_ist_today()`: the IST clock. Same contract as Trade: a naive datetime / date in IST,
  computed from UTC (never the server's local time). India has no daylight saving, so IST = UTC + 5:30.
- `ENGINE_PROFILE_CHECK_EVERY_MIN`: an operational cache interval. 0 here = every profile check is real, which is the
  engine's own behaviour when the name is missing. The operational value becomes an ATP setting when the live feed is
  ported (M79 W8); no Trade default is assumed.

- The NSE calendar (M79 W8), from ATP's market calendar handed in with each engine read (`EngineRequest.calendar`):
  `nse_holidays()` (every holiday listed), `NSE_HOLIDAYS_<year>` (the holidays of that year, as Trade's config names
  them), `special_session(day)` (the (open, close) of a day ATP lists as an early close, else None). They exist only
  while a read runs (`use_calendar`, entered by the signal-engine shim under its lock). Outside a read they are absent,
  exactly as before: every call site catches that and falls back to weekdays only / the normal close.
  Not provided: Trade's `NSE_HOLIDAYS_PROVISIONAL` (ATP's calendar has no provisional list) and `NSE_SPECIAL_SESSIONS`
  (no engine module reads it; `special_session` is the reader).
"""
import contextlib
import datetime
import sys

_IST_OFFSET = datetime.timedelta(hours=5, minutes=30)

ENGINE_PROFILE_CHECK_EVERY_MIN = 0


def get_ist_now() -> datetime.datetime:
    """The current IST time as a naive datetime (UTC + 5:30)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + _IST_OFFSET


def get_ist_today() -> datetime.date:
    """The current IST date."""
    return get_ist_now().date()


_PREFIX = "NSE_HOLIDAYS_"
_SPECIAL = {}


def _holidays_now():
    mod = sys.modules[__name__]
    return {k: v for k, v in vars(mod).items() if k.startswith(_PREFIX) and k[len(_PREFIX):].isdigit()}


def nse_holidays():
    """Every NSE_HOLIDAYS_<year> set of this module, merged (as Trade's config). Outside a read: no list (an error,
    which every call site turns into "weekdays only")."""
    found = _holidays_now()
    if not found:
        raise LookupError("no market calendar outside an engine read")
    return set().union(*[set(v) for v in found.values()])


def special_session(day):
    """(open, close) as datetime.time of the day's early-close session from ATP's calendar, or None (as Trade's
    config). Outside a read: an error (the call site then keeps the normal close)."""
    if not _holidays_now() and not _SPECIAL:
        raise LookupError("no market calendar outside an engine read")
    d = day.date() if isinstance(day, datetime.datetime) else day
    return _SPECIAL.get(d)


@contextlib.contextmanager
def use_calendar(calendar):
    """For one engine read: the holidays and early closes of ATP's `MarketCalendar` as Trade's config names. Restores
    the module afterwards (also on an error). Not re-entrant: the caller holds the engine's lock."""
    mod = sys.modules[__name__]
    by_year = {}
    for d in getattr(calendar, "holidays", ()) or ():
        by_year.setdefault(d.year, set()).add(d)
    special = {e.day: (calendar.regular_open, e.close) for e in getattr(calendar, "early_closes", ()) or ()}
    for k in list(_holidays_now()):
        delattr(mod, k)
    for year, days in by_year.items():
        setattr(mod, f"{_PREFIX}{year}", days)
    _SPECIAL.clear()
    _SPECIAL.update(special)
    try:
        yield
    finally:
        for k in list(_holidays_now()):
            delattr(mod, k)
        _SPECIAL.clear()


# --- SRV2 (owner 18 Nov, "Default yes"): the names the 15M SRv2 bot's copied Trade modules (trading_engine, database, trade_monitor,
# order_safety, entry_inflight, carry_guard, ...) read from Trade's config. Values and functions copied verbatim from Trade config.py
# (813358b); the engine never reads them. DATA_DIR is the bot's own state folder on ATP's data volume (SRV2_DATA_DIR), not created here.
import os  # noqa: E402

DATA_DIR = os.environ.get("SRV2_DATA_DIR") or "data"
if os.environ.get("SRV2_DATA_DIR"):                                       # Trade config creates its data folder at import
    os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "historical_data.db")
# M56 S1: a last known leg price this young may stand in for a missing LTP in the exit checks (operational setting, seconds)
EXIT_LTP_MAX_AGE_SEC = int(os.environ.get("EXIT_LTP_MAX_AGE_SEC", "60"))
EXIT_UNDECIDED_ALERT_EVERY_MIN = 10        # M56 S1: one "exit undecided" line per trade per this many minutes (operational)
WEBHOOK_REJECT_ALERT_EVERY_MIN = 30        # M56 S7: one "webhook rejected" line per this many minutes (operational)

NORMAL_SESSION = ("09:15", "15:30")


def _hm(x):
    h, m = str(x).split(":")
    return int(h) * 60 + int(m)



def calendar_gate_today():
    """N20: a script's own "is today a trading day?" gate (pre-open / end-of-day / chart reading). Env TRADE_CALENDAR_GATE=0 (tests)
    ⇒ always True; otherwise is_trading_day() for today (IST)."""
    import os
    return os.environ.get("TRADE_CALENDAR_GATE", "1") == "0" or is_trading_day()


def is_trading_day(now_dt=None):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — आज व्यापार-दिवस आहे का (सोमवार-शुक्रवार, NSE सुट्टी
    नाही) — फक्त दिवस तपासतो, वेळ नाही. eod_market_report.py सारख्या दुपारी ४ वाजता (बाजार बंद
    झाल्यानंतर) चालणाऱ्या scripts साठी उपयुक्त — is_market_open() तिथे नेहमी False देईल (वेळ जुळत
    नाही म्हणून), पण आजचा दिवस स्वतः व्यापार-दिवस होता की नाही हे वेगळंच, इथे तपासलं जातं.
    """
    now_dt = now_dt or get_ist_now()
    if special_session(now_dt):                                          # M56 O3: an owner-listed special session (even a weekend / holiday)
        return True
    if now_dt.weekday() >= 5:  # 5=शनिवार, 6=रविवार
        return False
    if now_dt.date() in nse_holidays():                                  # N20: every year's list (2026, 2027, …)
        return False
    return True


def is_mcx_market_open(now_dt=None, open_time=datetime.time(9, 0), close_time=datetime.time(23, 59, 59)):
    """🎓 MCX Futures साठी WebSocket stream monitor -- MCX सत्र सोमवार-शुक्रवार सकाळी ९:०० पासून रात्री ११:३०/११:५५ (हंगामानुसार)
    पर्यंत. exact बंद-वेळ/MCX सुट्ट्या इथे गृहीत धरल्या नाहीत (२३:५९ पर्यंत 'उघडा' समजतो) -- OPEN trade नसेल तर काहीच subscribe होत
    नाही, आणि feed ला ticks न आल्यास stream monitor काहीच करत नाही (REST monitor सुरक्षित fallback)."""
    now_dt = now_dt or get_ist_now()
    if now_dt.weekday() >= 5:
        return False
    return open_time <= now_dt.time() <= close_time


def is_market_open(now_dt=None, open_time=datetime.time(9, 15), close_time=datetime.time(15, 30)):
    """
    🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — NSE बाजार वेळेत आहे का (सोमवार ते शुक्रवार, डीफॉल्ट
    9:15 ते 15:30 IST, आणि आता NSE च्या अधिकृत सुट्टी-यादीनुसार सुट्टीचे दिवसही वगळले जातात).
    unattended scripts (oi_snapshot_collector.py, credit_spread_auto_trader.py,
    oi_signal_auto_trader.py) बाजार बंद असताना उगाच Option Chain fetch करू नयेत म्हणून.
    """
    now_dt = now_dt or get_ist_now()
    if not is_trading_day(now_dt):
        return False
    w = special_session(now_dt)
    if w:                                                                # M56 O3: the caller's window moves with the session's open / close
        sh = lambda t, base, new: datetime.time(*divmod(min(max(t.hour * 60 + t.minute + new - base, 0), 24 * 60 - 1), 60))  # noqa: E731
        o = sh(open_time, _hm(NORMAL_SESSION[0]), w[0].hour * 60 + w[0].minute)
        c = sh(close_time, _hm(NORMAL_SESSION[1]), w[1].hour * 60 + w[1].minute)
        return o <= now_dt.time() <= c
    return open_time <= now_dt.time() <= close_time


# M56 S2 (audit B4): a blocked LIVE exit (broker state unknown) — bounded read-only re-query in the same cycle, then a CRITICAL
# "close by hand" line every cycle once the block lasts longer than EXIT_BLOCK_MAX_SEC. Never a blind order (operational).
EXIT_REQUERY_COUNT = 3
EXIT_REQUERY_DELAY_SEC = 1.0
EXIT_BLOCK_MAX_SEC = 30
EXIT_BLOCK_ALERT_GAP_SEC = 10            # the stream monitor cycles every 1-2 s: at most one "close by hand" line per trade per this gap

# M56 S4 (audit B2): a per-bot LIVE / LIVE_PAPER mode needs a signed owner confirmation (live_confirm.py) that expires at this IST
# time (the first one after it was signed ⇒ signed again every day). Operational setting.
LIVE_CONFIRM_EXPIRES_IST = "15:30"

# M56 S5 (audit B6): a LIVE entry in-flight marker older than this is a leftover (crash between send and DB insert) ⇒ reconcile with
# the broker; an untracked leg ⇒ one CRITICAL line per marker per ENTRY_UNTRACKED_ALERT_EVERY_MIN (operational).
ENTRY_INFLIGHT_GRACE_SEC = 120
ENTRY_UNTRACKED_ALERT_EVERY_MIN = 10

# M56 S6 (audit B10): Fyers / Stocko / Shoonya adapters return no per-leg fill status ⇒ LIVE entries refused ("PAPER-only until fill
# verification") until the owner sets the broker True here after verifying fills. Exits are never refused by this.
ADAPTER_LIVE_FILL_VERIFIED = {"fyers": False, "stocko": False, "shoonya": False}
# M56 S6 (audit B7): SWING / carry-forward trades are squared off on the expiry day of their legs' contract at this IST time, and one
# daily position-check line lists every open carried trade with its expiry (operational).
EXPIRY_SQUAREOFF_IST = "15:10"
CARRY_CHECK_IST = "09:20"

# M56 S8 (audit B12, B13): the stream monitor runs a REST cycle (broker positions ⇒ reconciliation / MTM / entry markers) at least this
# often; a non-200 broker positions reply in the REST cycle ⇒ one CRITICAL line per POSITIONS_ALERT_EVERY_MIN (operational).
STREAM_REST_PASS_EVERY_MIN = 5
POSITIONS_ALERT_EVERY_MIN = 10

