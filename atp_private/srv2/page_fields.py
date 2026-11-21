"""atp_private.srv2.page_fields - the owner's SRv2 settings page for ATP (SRV2 P2; owner "Pending job purn kr" 21 Nov).

The fields are the ones Trade's own dashboard page lets him edit for this bot (`page_bot_dynamic_sr_algo.py`, strategy `15m_dynamic_sr`:
the keys its Save writes in `new_settings`), with the same bounds as its widgets. Labels and help are English translations of Trade's
Marathi labels (meaning kept AS IS; no new trading wording).

Not here, on purpose:
- `trading_mode` / `broker_account_ids`: LIVE stays the owner's own separate switch (ATP B1); ATP stores PAPER only.

SRV2-Q8 (step 2): the engine's advanced keys that Trade's page saves through helper converters are fields too (`ADVANCED`): the swing
scale D1 / D2, the Daily pivot N, the method layer switches, the entry models E1-E4, model C and its settings, the band-warn rule and
the pre-open charts send mode. Their shown values and stored values go through Trade's OWN helpers in this package's snapshot
(`engine3_live`, `paper.engine_entry`, `decision3.settings`, `swings2.settings`, `bots_common.plain_text` / `preopen_crux` - identical
to Trade's, checked by the TRADE_SRC test), never re-written here. Where Trade's page silently resets an invalid pair (D2 not above
D1; a legacy visit rule without the legacy commitment volume) and stores the method, `validate` refuses the save with Trade's own
reason instead, so nothing he did not choose is stored.

Shown values come from the same functions the bot reads (`values_for_page`): `merged` (Trade's cloud_db defaults + the stored row),
and for the keys outside DEFAULTS Trade's own helpers (`level_gate_bot.entry_mode` / `gate_settings` / `conf_gate_enabled`,
`engine_signal.DEFAULTS`) or the page's own literal default. Nothing is filled in for him on save: `validate` checks only what he
sent, with the widgets' bounds, and returns the clean values or a sentence per key.

`strikes`: Trade shows the two strike-depth fields in strikes (+ = OTM, 0 = ATM, - = ITM) and stores points = -strikes x step
(`itm_depth_points = -itm_depth_strikes * strike_step`). The sign is therefore -1: shown = stored / (-step), stored = shown x (-step).
"""
from __future__ import annotations

F = dict


def _settings():
    """The Trade-verbatim settings module (imported late: settings.py re-exports this module, so a top-level import would loop)."""
    from . import settings
    return settings


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

APPROVED = "approved"                         # the swing scale's empty value = Abhi's approved calibration (D1 = 4, D2 = 6)
PROVISIONAL_N = None                          # set with the advanced fields (decision3 DEFAULTS daily_pivot_n)


def _advanced_fields():
    """SRV2-Q8: the advanced engine fields, from Trade's own constants (labels as on Trade's page, in English)."""
    from atp_private.trade_engine import engine3_live as L3
    from atp_private.trade_engine import engine_signal as ES
    from atp_private.trade_engine.bots_common import plain_text as PT
    from atp_private.trade_engine.bots_common import preopen_crux as PC
    from atp_private.trade_engine.decision3 import settings as S3C
    from atp_private.trade_engine.paper import engine_entry as EE
    from atp_private.trade_engine.swings2 import settings as SW
    out = []
    for d in (1, 2):
        out.append(_f(f"engine3_swing_k_d{d}", f"Advanced: swing scale D{d} k (× σ)", "mode", "choice",
                      choices=(APPROVED, *(f"{k:g}" for k in SW.K_OPTIONS[d])),
                      help=f"approved = the approved scale (D1 = {SW.DEFAULTS['k'][1]:g}, D2 = {SW.DEFAULTS['k'][2]:g}); "
                           "D2 must be larger than D1. Only the engine's swings; charts / replay stay on the approved scale."))
    out.append(_f("engine3_daily_pivot_n", "Advanced: Daily swing size N (candles on each side)", "mode", "int", lo=1,
                  hi=L3.DAILY_PIVOT_N_MAX, help=f"{S3C.DEFAULTS['daily_pivot_n']} = provisional (the default)."))
    for key, (_v22, allowed, label) in L3.METHOD_SWITCHES.items():
        out.append(_f(key, f"Advanced: engine {label}", "mode", "choice", choices=allowed,
                      help=f"{allowed[0]} = the method (default); the others are legacy what-ifs."))
    for m in ("E1", "E2", "E3", "E4"):
        out.append(_f(EE.model_key(m, "on"), f"Entry model {m}: {ES.MODEL_NAMES[m]} (signals)", "mode", "bool"))
    out.append(_f(L3.MODEL_C_KEY, "Model C (counter-trend C leg), default off", "mode", "bool"))
    for x in S3C.MODEL_C_SUBS:
        out.append(_f(L3.model_c_sub_key(x), f"Model C: {x}", "mode", "bool"))
    out.append(_f("engine3_c_window", "Model C window", "mode", "choice", choices=S3C.C_WINDOWS))
    out.append(_f("engine3_c_a_nature", "Model C wave A nature", "mode", "choice", choices=("impulse", "any")))
    out.append(_f("engine3_c_projections", "Model C end-zone projections (ratios, display only)", "mode", "text"))
    out.append(_f(PT.BAND_WARN_RULE_KEY, "Approval: band width warning rule", "mode", "choice", choices=PT.BAND_WARN_RULES,
                  help="method = an engine area is one base: its width is shown as a fact, no warning line (default)."))
    out.append(_f(PC.CHARTS_SEND_KEY, "Pre-open charts on Telegram", "mode", "choice", choices=PC.CHARTS_SEND,
                  help="album = one silent album (default) · link = a dashboard link line · off = no charts."))
    return out


try:
    ADVANCED = _advanced_fields()
except ImportError:                                # the snapshot is not importable here: the page shows the plain fields only
    ADVANCED = []
FIELDS = FIELDS + ADVANCED
_ADVANCED_KEYS = {f["key"] for f in ADVANCED}
_BY_KEY = {f["key"]: f for f in FIELDS}
_CONFIRM_TF_DEFAULT = 15                     # page: {"15m_dynamic_sr": 15}; settings.get("confirm_tf_minutes") or default
_AREA_ALERT_CAP_DEFAULT = 10                 # page: int(settings.get("area_alert_daily_cap") or 10)


def values_for_page(symbol, stored=None):
    """The values the bot reads for this symbol, keyed as on the page (see the module docstring for where each comes from)."""
    from atp_private.trade_engine import engine_signal as ESD
    from atp_private.trade_engine.bots_common import level_gate_bot as LGB
    S = _settings()
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
    if ADVANCED:
        out.update(_advanced_values(vals))
    return {f["key"]: out.get(f["key"]) for f in FIELDS}


def _advanced_values(vals):
    """As Trade's page reads them (page_bot_dynamic_sr_algo.py, the 15M SRv2 engine block)."""
    from atp_private.trade_engine import engine3_live as L3
    from atp_private.trade_engine.bots_common import plain_text as PT
    from atp_private.trade_engine.bots_common import preopen_crux as PC
    from atp_private.trade_engine.decision3 import settings as S3C
    from atp_private.trade_engine.paper import engine_entry as EE
    from atp_private.trade_engine.swings2 import settings as SW
    out = {}
    for d in (1, 2):
        v = vals.get(f"engine3_swing_k_d{d}")
        try:
            k = float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            k = None
        out[f"engine3_swing_k_d{d}"] = f"{k:g}" if k is not None and k in SW.K_OPTIONS[d] else APPROVED
    out["engine3_daily_pivot_n"] = int(L3.pivot_n_choice(vals.get("engine3_daily_pivot_n"))[0])
    for key in L3.METHOD_SWITCHES:
        out[key] = L3.switch_choice(key, vals.get(key))[0]
    for m in ("E1", "E2", "E3", "E4"):
        out[EE.model_key(m, "on")] = EE.model_on(vals, m)
    out[L3.MODEL_C_KEY] = L3._truthy(vals.get(L3.MODEL_C_KEY), False)
    for x in S3C.MODEL_C_SUBS:
        out[L3.model_c_sub_key(x)] = L3._truthy(vals.get(L3.model_c_sub_key(x)), False)
    out["engine3_c_window"] = str(vals.get("engine3_c_window") or S3C.DEFAULTS["c_window"])
    out["engine3_c_a_nature"] = str(vals.get("engine3_c_a_nature") or S3C.DEFAULTS["c_a_nature"])
    out["engine3_c_projections"] = str(vals.get("engine3_c_projections") or ", ".join(f"{r:g}" for r in S3C.DEFAULTS["c_projections"]))
    out[PT.BAND_WARN_RULE_KEY] = PT.band_warn_rule(vals)
    out[PC.CHARTS_SEND_KEY] = PC.charts_send(vals.get(PC.CHARTS_SEND_KEY))
    return out


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


def validate(symbol, values, stored=None):
    """(clean, errors): only the keys sent; each checked with Trade's widget type and bounds. Strike fields arrive in points (ATP
    converts); their bounds are checked in strikes as on Trade's page. Saved as Trade's Save writes them (float points for the depths,
    `active_timeframes` empty -> ["15M"], `confirm_tf_minutes` as int). Nothing else is added."""
    S = _settings()
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
    if not errors and ADVANCED:
        _advanced_to_save(symbol, values or {}, stored or {}, clean, errors)
    return ({} if errors else clean), errors


def _advanced_to_save(symbol, values, stored, clean, errors):
    """Trade's page Save for the advanced keys: the swing pair and the method switches checked as a whole (with what is stored),
    then each value in the form Trade stores it. Refused with Trade's reason where Trade would silently store the method."""
    from atp_private.trade_engine import engine3_live as L3
    from atp_private.trade_engine.bots_common import plain_text as PT
    from atp_private.trade_engine.bots_common import preopen_crux as PC
    from atp_private.trade_engine.swings2 import settings as SW
    sent = {k: clean[k] for k in clean if k in _ADVANCED_KEYS}
    if not sent:
        return
    swing = [f"engine3_swing_k_d{d}" for d in (1, 2)]
    if any(k in sent for k in swing):
        cur = values_for_page(symbol, stored)
        pick = {d: str(sent.get(f"engine3_swing_k_d{d}", cur[f"engine3_swing_k_d{d}"])) for d in (1, 2)}
        if pick[1] == APPROVED and pick[2] == APPROVED:
            clean["engine3_swing_k_d1"] = clean["engine3_swing_k_d2"] = ""          # advanced off on Trade's page
        else:
            k = {d: float(SW.DEFAULTS["k"][d]) if pick[d] == APPROVED else float(pick[d]) for d in (1, 2)}
            if not k[2] > k[1]:
                errors["engine3_swing_k_d2"] = "D2 must be larger than D1 (Trade would store the approved scale instead)."
                return
            clean["engine3_swing_k_d1"], clean["engine3_swing_k_d2"] = k[1], k[2]
    if "engine3_daily_pivot_n" in sent:
        clean["engine3_daily_pivot_n"] = L3.pivot_n_to_save(sent["engine3_daily_pivot_n"])
    if any(k in sent for k in L3.METHOD_SWITCHES):
        cur = values_for_page(symbol, stored)
        choices = {k: sent.get(k, cur[k]) for k in L3.METHOD_SWITCHES}
        to_save, err = L3.switches_to_save(choices)
        if err:
            errors["engine3_zone_visit_rule"] = f"These engine layers do not fit together: {err}"
            return
        for k in L3.METHOD_SWITCHES:
            if k in sent:
                clean[k] = to_save[k]
    if PT.BAND_WARN_RULE_KEY in sent:
        clean[PT.BAND_WARN_RULE_KEY] = PT.band_warn_rule(sent[PT.BAND_WARN_RULE_KEY])
    if PC.CHARTS_SEND_KEY in sent:
        clean[PC.CHARTS_SEND_KEY] = PC.charts_send(sent[PC.CHARTS_SEND_KEY])
    if "engine3_c_projections" in sent and str(sent["engine3_c_projections"]).strip() and \
            L3.c_projections_of(sent["engine3_c_projections"]) is None:
        errors["engine3_c_projections"] = "Model C end-zone projections: ratios separated by commas, e.g. 1, 1.618."
