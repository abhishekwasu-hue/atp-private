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
