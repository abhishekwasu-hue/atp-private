"""atp_private.srv2.page_fields - the owner's SRv2 settings page for ATP (SRV2 P2; owner "Pending job purn kr" 21 Nov).

The fields are the ones Trade's own dashboard page lets him edit for this bot (`page_bot_dynamic_sr_algo.py`, strategy `15m_dynamic_sr`:
the keys its Save writes in `new_settings`), with the same bounds as its widgets. Labels and help are English translations of Trade's
Marathi labels (meaning kept AS IS; no new trading wording).

Not here, on purpose:
- `trading_mode` / `broker_account_ids`: LIVE stays the owner's own separate switch (ATP B1); ATP stores PAPER only.
- The engine's advanced keys that Trade's page saves through helper converters (`engine3_swing_k_d*`, `engine3_daily_pivot_n`, the
  method switches, the entry-model / model-C switches, the band-warn rule, the pre-open charts send mode): there a blank value
  means "the method's own value" and some combinations are corrected by the helper. They keep their stored values until a second
  step ports those converters AS IS (ATP OPEN_QUESTIONS SRV2-Q8).

Shown values come from the same functions the bot reads (`values_for_page`): `merged` (Trade's cloud_db defaults + the stored row),
and for the keys outside DEFAULTS Trade's own helpers (`level_gate_bot.entry_mode` / `gate_settings` / `conf_gate_enabled`,
`engine_signal.DEFAULTS`) or the page's own literal default. Nothing is filled in for him on save: `validate` checks only what he
sent, with the widgets' bounds, and returns the clean values or a sentence per key.

`strikes`: Trade shows the two strike-depth fields in strikes (+ = OTM, 0 = ATM, - = ITM) and stores points = -strikes x step
(`itm_depth_points = -itm_depth_strikes * strike_step`). The sign is therefore -1: shown = stored / (-step), stored = shown x (-step).
"""
from __future__ import annotations

from . import settings as S

F = dict


def _f(key, label, group, type_, *, lo=None, hi=None, choices=None, unit=None, help=None, strikes=None):
    out = F(key=key, label=label, group=group, type=type_)
    if lo is not None:
        out["min"] = lo
    if hi is not None:
        out["max"] = hi
    if choices is not None:
        out["choices"] = list(choices)
    if unit:
        out["unit"] = unit
    if help:
        out["help"] = help
    if strikes is not None:
        out["strikes"] = strikes
    return out


FIELDS = [
    # --- Entry (Trade tab "Entry Gate") ---------------------------------------------------------------------------------------------
    _f("symbol_enabled", "Bot on for this symbol (choose by your available capital)", "entry", "bool"),
    _f("entry_mode", "Entry mode", "entry", "choice", choices=("confirmation", "touch"),
       help="confirmation = the daily trend side + a closed candle's commitment at the level, then Vision, then your ✅. "
            "touch = the old way: a touch of the level is the entry."),
    _f("active_timeframes", "Touch timeframe", "entry", "multi", choices=("15M", "30M", "60M"), help="15M is the default; 30M / 60M optional."),
    _f("credit_spread_enabled", "Credit spread trade on", "entry", "bool"),
    _f("lots", "Lots", "entry", "int", lo=1, hi=50),
    _f("itm_depth_points", "Credit spread: strikes from ATM", "entry", "int", lo=-10, hi=5, unit="strikes", strikes=-1,
       help="+ = OTM, 0 = ATM, − = ITM."),
    _f("hedge_width_points", "Hedge width", "entry", "float", lo=25.0, hi=500.0, unit="points"),
    _f("naked_enabled", "Naked option trade on", "entry", "bool"),
    _f("naked_lots", "Naked option: lots (separate from the credit spread)", "entry", "int", lo=1, hi=50),
    _f("naked_hedge_enabled", "Naked option: add a hedge (debit spread)", "entry", "bool"),
    _f("naked_itm_depth_points", "Naked option: strikes from ATM", "entry", "int", lo=-10, hi=5, unit="strikes", strikes=-1,
       help="+ = OTM, 0 = ATM, − = ITM."),
    _f("naked_hedge_width_points", "Naked hedge width (only with the hedge on)", "entry", "float", lo=25.0, hi=500.0, unit="points"),
    _f("bullish_entry_enabled", "Bullish entries on", "entry", "bool",
       help="A side turned off takes no new trades; trades already open are not affected."),
    _f("bearish_entry_enabled", "Bearish entries on", "entry", "bool"),
    _f("entry_rsi_gate_enabled", "RSI gate on", "entry", "bool", help="Off: entry on the level touch only; RSI is not checked."),
    _f("rsi_support_max", "RSI support max (bullish below this)", "entry", "int", lo=5, hi=50),
    _f("rsi_resistance_min", "RSI resistance min (bearish above this)", "entry", "int", lo=50, hi=95),
    _f("entry_pcr_gate_enabled", "PCR gate on", "entry", "bool",
       help="Applies to both trade types. Off also turns off the pause when PCR data is missing or older than 15 minutes."),
    _f("pcr_bullish_min", "No bullish when PCR is below", "entry", "float", lo=0.10, hi=2.0),
    _f("pcr_bearish_max", "No bearish when PCR is above", "entry", "float", lo=0.10, hi=2.0),
    _f("gate_rr_gate_enabled", "R:R gate on", "entry", "bool", help="Default off: no skip, disarm or warning on R:R."),
    _f("gate_min_rr", "Minimum R:R (only with the R:R gate on)", "entry", "float", lo=1.0, hi=10.0),
    _f("gate_no_target_disarm_enabled", "No target area: no entry", "entry", "bool"),
    _f("gate_max_armed_bars", "Wait for the commitment", "entry", "int", lo=1, hi=40, unit="closed candles"),
    _f("confirm_tf_minutes", "Confirmation timeframe", "entry", "choice", choices=("5", "15"), unit="min"),
    _f("gate_wait_next_candle", "Entry only if the candle after the commitment does not close back inside the area", "entry", "bool"),
    _f("conf_rsi_gate_enabled", "Confirmation mode: RSI threshold gate", "entry", "bool"),
    _f("conf_pcr_gate_enabled", "Confirmation mode: PCR gate", "entry", "bool"),
    _f("max_hits_per_zone", "Max trades on the same zone / role", "entry", "int", lo=1, hi=10),
    _f("level_memory_enabled", "Level memory: keep important dynamic S/R levels at the same price", "entry", "bool"),
    _f("sl_tsl_cooldown_minutes", "SL / TSL cooldown on the same level", "entry", "int", lo=0, hi=120, unit="min"),
    _f("post_sl_cooldown_enabled", "Cooldown after an SL, whole symbol", "entry", "bool",
       help="Trade's own note: today this switch changes nothing (the SL time is not recorded)."),
    _f("post_sl_cooldown_minutes", "Cooldown after an SL, whole symbol", "entry", "int", lo=1, hi=240, unit="min"),
    _f("entry_min_hold_gate_enabled", "Minimum level-hold before entry on", "entry", "bool"),
    _f("entry_min_hold_minutes", "The level must hold for", "entry", "int", lo=1, hi=30, unit="min"),
    _f("entry_min_hold_first_trade_only", "Only for the first trade on a level", "entry", "bool"),
    # --- Exit (Trade tab "Exit Gate") ------------------------------------------------------------------------------------------------
    _f("spread_sl_spot_pct", "Credit spread: SL, spot %", "exit", "float", lo=0.01, hi=5.0),
    _f("spread_sl_premium_points", "Credit spread: SL, premium points", "exit", "float", lo=1.0, hi=200.0),
    _f("spread_tsl_spot_pct", "Credit spread: TSL activation, spot %", "exit", "float", lo=0.01, hi=5.0),
    _f("spread_tsl_premium_points", "Credit spread: TSL activation, premium points", "exit", "float", lo=1.0, hi=200.0),
    _f("spread_target_pct_of_premium", "Credit spread: target, % of net premium", "exit", "float", lo=1.0, hi=200.0),
    _f("carry_forward_min_profit_pct", "Carry-forward minimum profit %", "exit", "float", lo=1.0, hi=100.0),
    _f("naked_sl_spot_pct", "Naked option: SL, spot %", "exit", "float", lo=0.01, hi=5.0),
    _f("naked_sl_premium_points", "Naked option: SL, premium points", "exit", "float", lo=1.0, hi=200.0),
    _f("naked_tsl_spot_pct", "Naked option: TSL activation, spot %", "exit", "float", lo=0.01, hi=5.0),
    _f("naked_tsl_premium_points", "Naked option: TSL activation, premium points", "exit", "float", lo=1.0, hi=200.0),
    _f("naked_target_spot_pct", "Naked option: target, spot %", "exit", "float", lo=0.01, hi=5.0),
    _f("naked_target_premium_points", "Naked option: target, premium points", "exit", "float", lo=1.0, hi=200.0),
    _f("spread_trailing_sl_enabled", "Credit spread: trailing SL on", "exit", "bool"),
    _f("spread_trailing_distance_points", "Credit spread: trailing distance (premium points)", "exit", "float", lo=1.0, hi=200.0),
    _f("naked_trailing_sl_enabled", "Naked option: trailing SL on", "exit", "bool"),
    _f("naked_trailing_distance_points", "Naked option: trailing distance (premium points)", "exit", "float", lo=1.0, hi=200.0),
    _f("naked_eod_hour", "Naked option: end-of-day exit hour (24 h)", "exit", "int", lo=9, hi=15),
    _f("naked_eod_minute", "Naked option: end-of-day exit minute", "exit", "int", lo=0, hi=59),
    _f("broker_side_sl_enabled", "Broker-side SL (phase 2, Upstox only)", "exit", "bool"),
    # --- Engine and alerts (Trade's 15M SRv2 engine section) -------------------------------------------------------------------------
    _f("signal_source", "Signal source", "mode", "choice", choices=("own", "engine", "both"),
       help="own = the bot's own signal · engine = the engine's setup only · both = only when both point the same way."),
    _f("engine3_use_1m", "Engine: use 1m data (the high / low order inside a candle)", "mode", "bool",
       help="On (default) = the same pivots as the replay and RSI divergence. No 1m data: the engine runs without it."),
    _f("engine_max_age_min", "Card freshness window: an engine signal older than this gets no card", "mode", "int", lo=1, unit="min"),
    _f("area_alerts", "Area-visit alert (one message per visit on a trade-side area)", "mode", "bool"),
    _f("area_alert_daily_cap", "Area-visit alerts per day (cap)", "mode", "int", lo=1),
    _f("approval_band_warn_pts", "Approval: 'merged band - check' warning when the band is wider than", "mode", "float", lo=1.0, unit="pts",
       help="A warning in the Telegram message only; it changes no decision, gate or order."),
    _f("preopen_charts", "Pre-open: crux + charts (Daily / 1H / 15M)", "mode", "bool",
       help="On (default) = the main points and charts above the morning message. A chart that fails: the message goes as it is."),
]

_BY_KEY = {f["key"]: f for f in FIELDS}
_CONFIRM_TF_DEFAULT = 15                     # page: {"15m_dynamic_sr": 15}; settings.get("confirm_tf_minutes") or default
_AREA_ALERT_CAP_DEFAULT = 10                 # page: int(settings.get("area_alert_daily_cap") or 10)


def values_for_page(symbol, stored=None):
    """The values the bot reads for this symbol, keyed as on the page (see the module docstring for where each comes from)."""
    from atp_private.trade_engine import engine_signal as ESD
    from atp_private.trade_engine.bots_common import level_gate_bot as LGB
    vals = S.merged(symbol, stored)
    gs = LGB.gate_settings(vals)
    out = dict(vals)
    out["entry_mode"] = LGB.entry_mode(vals)
    for k in ("rr_gate_enabled", "min_rr", "no_target_disarm_enabled", "max_armed_bars", "wait_next_candle"):
        out[f"gate_{k}"] = gs[k]
    out["confirm_tf_minutes"] = str(int(vals.get("confirm_tf_minutes") or _CONFIRM_TF_DEFAULT))
    out["conf_rsi_gate_enabled"] = LGB.conf_gate_enabled(vals, "rsi")
    out["conf_pcr_gate_enabled"] = LGB.conf_gate_enabled(vals, "pcr")
    out["engine_max_age_min"] = int(vals.get("engine_max_age_min") or ESD.DEFAULTS["engine_max_age_min"])
    out["area_alerts"] = str(vals.get("area_alerts", True)).lower() not in ("false", "0", "off")
    out["area_alert_daily_cap"] = int(vals.get("area_alert_daily_cap") or _AREA_ALERT_CAP_DEFAULT)
    out["active_timeframes"] = list(vals.get("active_timeframes") or ["15M"])
    return {f["key"]: out.get(f["key"]) for f in FIELDS}


def _num(f, v):
    if isinstance(v, bool) or v is None or v == "":
        raise ValueError("a number")
    n = float(v)
    if f["type"] == "int":
        if n != int(n):
            raise ValueError("a whole number")
        n = int(n)
    if "min" in f and n < f["min"]:
        raise ValueError(f"at least {f['min']}")
    if "max" in f and n > f["max"]:
        raise ValueError(f"at most {f['max']}")
    return n


def validate(symbol, values):
    """(clean, errors): only the keys sent; each checked with Trade's widget type and bounds. Strike fields arrive in points (ATP
    converts); their bounds are checked in strikes as on Trade's page. Saved as Trade's Save writes them (float points for the depths,
    `active_timeframes` empty -> ["15M"], `confirm_tf_minutes` as int). Nothing else is added."""
    clean, errors = {}, {}
    step = S.STRIKE_STEP.get(symbol, S.STRIKE_STEP["NIFTY"])
    for key, v in (values or {}).items():
        f = _BY_KEY.get(key)
        if f is None:
            errors[key] = "This setting cannot be changed here."
            continue
        try:
            t = f["type"]
            if t == "bool":
                if not isinstance(v, bool):
                    raise ValueError("on or off")
                clean[key] = v
            elif t in ("int", "float"):
                if f.get("strikes"):
                    if isinstance(v, bool) or not isinstance(v, (int, float)):
                        raise ValueError("a whole number of strikes")
                    strikes = v / (f["strikes"] * step)
                    if strikes != int(strikes):
                        raise ValueError("a whole number of strikes")
                    _num(f, int(strikes))
                    clean[key] = float(v)
                else:
                    n = _num(f, v)
                    clean[key] = float(n) if t == "float" else int(n)
            elif t == "choice":
                if str(v) not in f["choices"]:
                    raise ValueError("one of " + ", ".join(f["choices"]))
                clean[key] = int(v) if key == "confirm_tf_minutes" else str(v)
            elif t == "multi":
                items = list(v) if isinstance(v, (list, tuple)) else None
                if items is None or any(str(x) not in f["choices"] for x in items):
                    raise ValueError("a list of " + ", ".join(f["choices"]))
                clean[key] = [str(x) for x in items] or ["15M"]
            else:
                clean[key] = str(v)
        except (TypeError, ValueError) as exc:
            errors[key] = f"{f['label']}: must be {exc}."
    return ({} if errors else clean), errors
