"""SRV2 P1 (owner 18 Nov, "Default yes"): the Trade bot "15M SRv2" engine-entry glue, copied AS IS, runs inside atp-private with
ATP's host adapters (`atp_private.srv2.host`) in place of Trade's IO modules.

The copied Trade code decides everything here (model / direction switches, cutoff, one position at a time, max_hits_per_zone, once per
visit per model, PAPER only, legs from the dashboard settings); the tests only hand it fake ATP adapters, a temporary engine store and a
fake gate, and check that the copied rules act exactly as in Trade. Synthetic data only.
"""
import json
import os
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from atp_private.srv2 import host
from atp_private.srv2 import settings as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "atp_private", "trade_engine")
BOT, SRC = "srv2_momentum_reversal", "srv2_momentum_reversal"
NOW = pd.Timestamp("2026-11-12 10:05")                                     # IST naive, before the 14:45 cutoff
BAR = "2026-11-12 10:00:00"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPER_DATA_DIR", str(tmp_path / "paper"))
    monkeypatch.setenv("ENGINE_SIGNAL_DB", str(tmp_path / "engine" / "engine_signals.db"))
    monkeypatch.setenv("PAPER_CONFIG", os.path.join(ENGINE, "config.yaml"))
    host.reset()
    host.install()
    state = NS(stored={}, opened=[], sent=[], open_now=False, symbols=None, live_ok=False)
    host.register(
        settings=lambda strategy, symbol: state.stored.get(symbol),
        signal_symbols=lambda: state.symbols,
        token=lambda: "tok",
        option_chain=lambda tok, sym, idx: (chain(), ""),
        option_expiries=lambda tok, sym: ["2026-11-18", "2026-11-25"],
        send=lambda msg, **kw: (state.sent.append(msg) or True),
        live_confirmed=lambda *a: state.live_ok,
    )
    yield state
    host.reset()
    host.uninstall()


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def chain(spot=24010.0):
    rows = []
    for k in range(23500, 24551, 50):
        def leg(kind, k=k):
            itm = (spot - k) if kind == "CE" else (k - spot)
            ltp = max(itm, 0) + 40.0 + abs(k - spot) * 0.02
            return {"instrument_key": f"NSE_FO|{kind}{k}", "market_data": {"ltp": round(ltp, 2)}, "option_greeks": {"pop": 0.5}}
        rows.append({"strike_price": k, "underlying_spot_price": spot, "call_options": leg("CE"), "put_options": leg("PE")})
    return rows


def store_row(entries, bar=BAR, symbol="NIFTY"):
    from atp_private.trade_engine import engine_signal as ES
    ES.save({"symbol": symbol, "bar_ts": bar, "computed_at": bar, "decision": "setup", "gate": "pass", "direction": 1,
             "level_lo": 23950.0, "level_hi": 23990.0, "entry": None, "invalidation": None, "target": None, "grade": None,
             "reason": None, "payload": json.dumps({"entries": entries})})


def entry(model="E2", direction=1, visit="v1", lo=23950.0, hi=23990.0):
    return {"model": model, "direction": direction, "visit_id": visit, "trigger_ts": BAR,
            "area": {"lo": lo, "hi": hi, "tf": "15M", "role": "buyer"}}


def gate(action="ENTER", lots=99, naked=99):
    calls = []

    def fn(bot, symbol, mode, direction, level, role, tf, bar, spot, lots_, naked_, tags=None, path=None):
        calls.append({"bot": bot, "symbol": symbol, "mode": mode, "direction": direction, "level": level, "role": role, "tf": tf,
                      "lots": lots_, "naked": naked_})
        return NS(action=action, lots=lots, naked_lots=naked, note=action.lower(), signal_id="sig1", final=True)
    fn.calls = calls
    return fn


def run(state, gate_fn, now=NOW, symbol="NIFTY", lot_size=65):
    from atp_private.trade_engine import cloud_db
    from atp_private.trade_engine.paper import engine_entry as EE
    st = cloud_db.get_strategy_settings(S.STRATEGY_KEY, symbol)
    return EE.process(BOT, "tok", symbol, st, lot_size, SRC, now=now, gate_fn=gate_fn,
                      has_open=lambda sym, src: state.open_now,          # Trade's database / trading_engine stand-ins (the PAPER engine
                      open_fn=lambda tok, sym, sr, **kw: (state.opened.append({"symbol": sym, "legs": sr, **kw}) or (True, "opened")))


def test_settings_are_trades_defaults_merged_with_the_stored_row(env):
    from atp_private.trade_engine import cloud_db
    env.stored["NIFTY"] = {"lots": 3}
    s = cloud_db.get_strategy_settings(S.STRATEGY_KEY, "NIFTY")
    assert s["lots"] == 3 and s["signal_source"] == "engine" and s["trading_mode"] == "PAPER" and s["symbol_enabled"] is True
    b = cloud_db.get_strategy_settings(S.STRATEGY_KEY, "BANKNIFTY")
    assert b["symbol_enabled"] is False and b["itm_depth_points"] == 2 * S.DEFAULTS["itm_depth_points"]   # strike step 100 vs 50


def test_a_stored_live_mode_without_the_owners_confirmation_reads_as_paper(env):
    from atp_private.trade_engine import cloud_db
    env.stored["NIFTY"] = {"trading_mode": "LIVE"}
    s = cloud_db.get_strategy_settings(S.STRATEGY_KEY, "NIFTY")
    assert s["trading_mode"] == "PAPER" and s["live_unconfirmed"] == "LIVE"
    env.live_ok = True
    assert cloud_db.get_strategy_settings(S.STRATEGY_KEY, "NIFTY")["trading_mode"] == "LIVE"


def test_an_approved_entry_opens_the_spread_and_the_naked_leg_from_the_dashboard_settings(env):
    env.stored["NIFTY"] = {"lots": 2, "naked_lots": 1}
    store_row([entry("E2")])
    g = gate()
    msg = run(env, g)
    assert g.calls and g.calls[0]["mode"] == "PAPER" and g.calls[0]["lots"] == 2 and g.calls[0]["naked"] == 1
    assert g.calls[0]["level"] == pytest.approx(23970.0) and g.calls[0]["role"] == "Support"
    assert len(env.opened) == 2, msg                                       # credit spread + naked, as the settings say
    spread, naked = env.opened
    assert spread["lots"] == 2 and naked["lots"] == 1 and spread["trading_mode"] == "PAPER" and spread["lot_size"] == 65
    assert spread["entry_reason_tag"] == "ENGINE_E2" and spread["entry_timeframe"] == "ENGINE" and spread["source"] == SRC
    assert spread["target_pct_of_max_profit"] == float(S.DEFAULTS["spread_target_pct_of_premium"])
    from atp_private.trade_engine.strategy import (
        select_credit_spread_itm,
        select_naked_option_itm,
    )
    st = S.merged("NIFTY", {"lots": 2, "naked_lots": 1})
    atm = round(24010.0 / 50) * 50
    assert spread["legs"] == select_credit_spread_itm(chain(), "BULLISH", atm, step=50, itm_depth_points=st["itm_depth_points"],
                                                      hedge_width_points=st["hedge_width_points"])
    assert spread["legs"]["strategy"] == "BULL_PUT_SPREAD"
    assert naked["legs"] == select_naked_option_itm(chain(), "BULLISH", atm, itm_depth_points=st["naked_itm_depth_points"], step=50,
                                                    hedge_enabled=st["naked_hedge_enabled"],
                                                    hedge_width_points=st["naked_hedge_width_points"])


def test_the_same_visit_and_model_never_opens_a_second_position(env):
    store_row([entry("E2")])
    run(env, gate())
    n = len(env.opened)
    run(env, gate())
    assert len(env.opened) == n


def test_one_position_at_a_time(env):
    env.open_now = True
    store_row([entry("E1")])
    g = gate()
    assert "one at a time" in run(env, g) and not env.opened and not g.calls


def test_no_new_entry_after_the_cutoff(env):
    store_row([entry("E1")], bar="2026-11-12 14:45:00")
    msg = run(env, gate(), now=pd.Timestamp("2026-11-12 14:50"))
    assert "no new entry after 14:45" in msg and not env.opened


def test_a_model_switched_off_and_a_direction_switched_off_skip(env):
    env.stored["NIFTY"] = {"engine3_model_e3_on": False, "bearish_entry_enabled": False}
    store_row([entry("E3", visit="a"), entry("E1", direction=-1, visit="b")])
    msg = run(env, gate())
    assert "model OFF" in msg and "entries in that direction are off" in msg and not env.opened


def test_max_hits_per_zone_stops_entries_on_a_full_zone(env):
    env.stored["NIFTY"] = {"max_hits_per_zone": 1}
    store_row([entry("E1", visit="a")], bar="2026-11-12 09:45:00")
    run(env, gate(), now=pd.Timestamp("2026-11-12 09:50"))
    assert len(env.opened) == 2
    env.opened.clear()
    store_row([entry("E2", visit="b")])
    msg = run(env, gate())
    assert "max_hits_per_zone" in msg and not env.opened


def test_a_turned_down_card_opens_nothing_and_a_waiting_card_waits(env):
    store_row([entry("E1", visit="a")])
    assert "turned down" in run(env, gate("REJECT")) and not env.opened
    store_row([entry("E2", visit="b")])
    held = gate("HOLD")
    held_fn = lambda *a, **k: NS(**{**vars(held(*a, **k)), "final": False})
    assert "waiting for Vision" in run(env, held_fn) and not env.opened


def test_engine_entries_are_paper_only(env):
    env.stored["NIFTY"] = {"trading_mode": "LIVE"}
    env.live_ok = True
    store_row([entry("E1")])
    msg = run(env, gate())
    assert "PAPER only" in msg and not env.opened


def test_a_symbol_outside_the_signal_symbols_gets_no_entry(env):
    env.symbols = ["BANKNIFTY"]
    store_row([entry("E1")])
    assert "not in signal_symbols" in run(env, gate()) and not env.opened


def test_an_adapter_atp_has_not_registered_means_no_entry_never_a_crash(env):
    host.register(option_chain=None)
    store_row([entry("E1")])
    msg = run(env, gate())
    assert "no entry" in msg and not env.opened


def test_the_copied_glue_is_trades_code_with_only_the_imports_rewritten():
    """Runs where a Trade checkout at the snapshot commit is given (TRADE_SRC); CI has none."""
    src = os.environ.get("TRADE_SRC")
    if not src:
        pytest.skip("TRADE_SRC (a Trade checkout at the snapshot commit) not set")
    import sys
    sys.path[:0] = [src, os.path.join(src, "scripts")]
    import atp_import_rewrite as AIR
    from scripts import engine_closure as EC
    man = json.loads(_read(os.path.join(ENGINE, "IMPORT_MANIFEST.json")))
    tops = EC.top_modules(src)
    for rel in man["added_later"]["srv2_glue"]["modules"] + man["added_later"]["srv2_engine"]["modules"]:
        want = AIR.rewrite(_read(os.path.join(src, rel)), tops, src)
        assert _read(os.path.join(ENGINE, rel)) == want, rel


def test_the_defaults_are_trades_own():
    """Runs where TRADE_SRC is given: settings.DEFAULTS == Trade cloud_db.STRATEGY_SETTINGS_DEFAULTS['15m_dynamic_sr']."""
    src = os.environ.get("TRADE_SRC")
    if not src:
        pytest.skip("TRADE_SRC (a Trade checkout at the snapshot commit) not set")
    import ast
    tree = ast.parse(_read(os.path.join(src, "cloud_db.py")))
    for n in tree.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "STRATEGY_SETTINGS_DEFAULTS":
            d = dict(zip([ast.literal_eval(k) for k in n.value.keys], n.value.values))
            assert ast.literal_eval(d[S.STRATEGY_KEY]) == S.DEFAULTS
            return
    pytest.fail("STRATEGY_SETTINGS_DEFAULTS not found")
