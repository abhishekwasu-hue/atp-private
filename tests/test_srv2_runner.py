"""SRV2 P1c (owner 18 Nov): the bot's schedule inside ATP's worker (`atp_private.srv2.runner.tick`) keeps Trade's cron timing - the bot
every minute at :30 from 09:15 to 16:29 IST on weekdays, the exit monitor every 15 s (5 s while a trade is open), the engine once per
5M close after the final grace and retried every 5 s until the bar is stored or 120 s have passed."""
import pandas as pd
import pytest

from atp_private.srv2 import host
from atp_private.srv2 import runner as R


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(R, "_state", {"bot_minute": None, "monitor_last": None, "engine": {}})
    yield


def calls():
    seen = []
    return seen, {"engine": lambda now, cal: (seen.append(("engine", now)) or True),
                  "bot": lambda: seen.append(("bot", None)),
                  "exits": lambda: seen.append(("exits", None))}


def t(s):
    return pd.Timestamp(s)


def test_the_bot_runs_once_a_minute_at_thirty_seconds_in_market_hours():
    seen, run = calls()
    R.tick(t("2026-11-12 10:00:10"), run=run)
    assert ("bot", None) not in seen                                       # before :30
    R.tick(t("2026-11-12 10:00:31"), run=run)
    R.tick(t("2026-11-12 10:00:45"), run=run)
    assert seen.count(("bot", None)) == 1                                  # once in the minute
    R.tick(t("2026-11-12 10:01:30"), run=run)
    assert seen.count(("bot", None)) == 2


def test_nothing_runs_on_a_weekend_or_outside_the_window():
    seen, run = calls()
    R.tick(t("2026-11-14 10:00:40"), run=run)                              # a Saturday
    R.tick(t("2026-11-12 16:31:00"), run=run)                              # after 16:29
    R.tick(t("2026-11-12 09:14:40"), run=run)                              # before 09:15 (the engine window is open: only it runs)
    assert [k for k, _ in seen] == ["engine"]


def test_the_exit_monitor_runs_every_five_seconds_here():
    seen, run = calls()
    for sec in (0, 2, 5, 9, 10):
        R.tick(t(f"2026-11-12 11:00:{sec:02d}"), run=run)
    assert seen.count(("exits", None)) == 3                                # at 0, 5 and 10


def test_the_engine_is_tried_once_per_close_and_retried_every_five_seconds(monkeypatch):
    tries = []
    monkeypatch.setattr(R, "engine_close", lambda close, syms, cal=None: tries.append(close) or [])
    from atp_private.trade_engine.scripts import engine_resident as ER
    monkeypatch.setattr(R, "_private", lambda: (ER, None, None))
    monkeypatch.setattr(ER, "read_symbols", lambda prev=None: ["NIFTY"])
    grace = ER.start_after_s()
    close = t("2026-11-12 10:05:00")
    assert R.engine_due(close + pd.Timedelta(seconds=grace - 1)) is False  # the bar is not final yet
    assert R.engine_due(close + pd.Timedelta(seconds=grace)) is True
    assert R.engine_due(close + pd.Timedelta(seconds=grace + 2)) is False  # retry gap
    assert R.engine_due(close + pd.Timedelta(seconds=grace + 5)) is True
    assert R.engine_due(close + pd.Timedelta(seconds=ER.GIVE_UP_AFTER_S)) is False   # given up: the next close catches up
    assert tries == [close, close]


def test_a_failing_part_never_stops_the_others():
    seen = []

    def boom():
        raise RuntimeError("x")
    run = {"engine": lambda now, cal: False, "bot": boom, "exits": lambda: seen.append("exits")}
    assert R.tick(t("2026-11-12 10:00:40"), run=run) == ["exits"] and seen == ["exits"]


def test_the_bots_cycle_reads_each_symbols_switch(tmp_path, monkeypatch):
    from atp_private.trade_engine import config as C
    monkeypatch.setattr(C, "DB_PATH", str(tmp_path / "historical_data.db"))
    monkeypatch.setattr(C, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_DATA_DIR", str(tmp_path / "paper"))
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "engine_signals.db"))
    host.reset()
    host.register(settings=lambda strategy, symbol: None, token=lambda: None, send=lambda *a: True)
    host.install()
    monkeypatch.setattr(R, "_installed", False)
    from atp_private.trade_engine import database as DB
    from atp_private.trade_engine import process_lock as PL
    monkeypatch.setattr(DB, "DB_PATH", str(tmp_path / "historical_data.db"))
    monkeypatch.setattr(DB, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(PL, "DATA_DIR", str(tmp_path))
    try:
        assert R.bot_cycle() == ["no Upstox token"]                        # no login => nothing, one plain message
        host.register(token=lambda: "tok")
        out = R.bot_cycle()
        assert out[1].startswith("BANKNIFTY: बंद आहे") and out[2].startswith("SENSEX: बंद आहे")   # symbol_enabled default: NIFTY only
    finally:
        host.reset()
        host.uninstall()
