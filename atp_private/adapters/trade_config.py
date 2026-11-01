"""Adapter for Trade's `config` module, as `atp_private.trade_engine.config` (owner order M79, C6).

The snapshot uses only these names from Trade's `config` (checked against every `config` import in
`atp_private/trade_engine/`):
- `get_ist_now()` / `get_ist_today()`: the IST clock. Same contract as Trade: a naive datetime / date in IST,
  computed from UTC (never the server's local time). India has no daylight saving, so IST = UTC + 5:30.
- `ENGINE_PROFILE_CHECK_EVERY_MIN`: an operational cache interval. 0 here = every profile check is real, which is the
  engine's own behaviour when the name is missing. The operational value becomes an ATP setting when the live feed is
  ported (M79 W8); no Trade default is assumed.

Deliberately NOT provided (every call site catches the error and falls back to weekdays only / the normal close):
`nse_holidays()`, `special_session()`, `NSE_HOLIDAYS_*`. ATP's own market calendar (backend/app/market_data/calendar.py)
is wired to them in W8, not here.
"""
import datetime

_IST_OFFSET = datetime.timedelta(hours=5, minutes=30)

ENGINE_PROFILE_CHECK_EVERY_MIN = 0


def get_ist_now() -> datetime.datetime:
    """The current IST time as a naive datetime (UTC + 5:30)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + _IST_OFFSET


def get_ist_today() -> datetime.date:
    """The current IST date."""
    return get_ist_now().date()
