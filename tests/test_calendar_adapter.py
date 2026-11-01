"""M79 W8: the engine config's NSE calendar from ATP's market calendar (atp_private/adapters/trade_config.py).

Made-up dates only. Covered: outside a read the names are absent and every engine call site falls back as before;
inside `use_calendar` the holidays (merged and per year, as Trade's config names them) and the early-close session are
there and the engine's own readers see them; the module is restored afterwards, also on an error.
"""
import datetime as dt
from types import SimpleNamespace

import pytest

from atp_private import adapters

adapters.install()

import atp_private.trade_engine.config as config                           # noqa: E402 - the adapter, by its snapshot name
from atp_private.adapters import trade_config as TC                         # noqa: E402
from atp_private.trade_engine import engine3_live as L                     # noqa: E402

H1, H2 = dt.date(2030, 1, 15), dt.date(2031, 3, 4)
EARLY = dt.date(2030, 1, 21)


def _cal():
    return SimpleNamespace(regular_open=dt.time(9, 15), regular_close=dt.time(15, 30), holidays=(H1, H2),
                           early_closes=(SimpleNamespace(day=EARLY, close=dt.time(13, 0)),))


def test_config_is_the_adapter():
    assert config is TC


def test_outside_a_read_nothing_is_listed_and_the_engine_falls_back():
    assert not [k for k in vars(config) if k.startswith("NSE_HOLIDAYS_")]
    with pytest.raises(LookupError):
        config.nse_holidays()
    assert L._holidays() == set()
    assert L._day_complete([[f"{EARLY.isoformat()}T15:15:00", 1, 1, 1, 1, 1, 0]], EARLY, "15minute") is True


def test_inside_a_read_the_calendar_is_there():
    with TC.use_calendar(_cal()):
        assert config.nse_holidays() == {H1, H2}
        assert config.NSE_HOLIDAYS_2030 == {H1} and config.NSE_HOLIDAYS_2031 == {H2}
        assert config.special_session(EARLY) == (dt.time(9, 15), dt.time(13, 0))
        assert config.special_session(dt.datetime.combine(EARLY, dt.time(10))) == (dt.time(9, 15), dt.time(13, 0))
        assert config.special_session(H1) is None
        assert L._holidays() == {H1, H2}
        # the early close: the day's last 15M bar is the 12:45 one
        assert L._day_complete([[f"{EARLY.isoformat()}T12:45:00", 1, 1, 1, 1, 1, 0]], EARLY, "15minute") is True
    assert not [k for k in vars(config) if k.startswith("NSE_HOLIDAYS_")]
    assert L._holidays() == set()


def test_engine_rollover_days_skip_a_listed_holiday():
    from atp_private.trade_engine.legs2 import volume as V
    expiry = dt.date(2030, 1, 17)                                           # a made-up Thursday expiry
    sessions = [dt.date(2030, 1, d) for d in (6, 7, 8, 9, 10)]               # data days end before the expiry week's days
    before = V.rollover_days([expiry], sessions)
    with TC.use_calendar(_cal()):
        during = V.rollover_days([expiry], sessions)
    import pandas as pd
    assert pd.Timestamp(H1) in before and pd.Timestamp(H1) not in during    # 15 Jan is a holiday only inside the read


def test_restored_after_an_error():
    with pytest.raises(RuntimeError):
        with TC.use_calendar(_cal()):
            raise RuntimeError("x")
    assert not [k for k in vars(config) if k.startswith("NSE_HOLIDAYS_")]
    with pytest.raises(LookupError):
        config.special_session(EARLY)
