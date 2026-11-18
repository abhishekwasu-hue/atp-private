"""Stand-in for Trade's `cloud_db` (Supabase) - owner order SRV2, 18 Nov. Trade 813358b cloud_db.py: the defaults and getters below are
copied verbatim (line numbers given); the row store is ATP's (`settings` adapter: (strategy_key, symbol) -> stored dict or None, the
same (strategy_name, symbol) rows as Trade's `strategy_settings` table). Functions the 15M SRv2 bot never reaches (OI snapshots, other
bots' market zones, broker accounts) say so and return what Trade returns when its database is unreachable."""
from atp_private.srv2 import host as _H
from atp_private.srv2 import settings as _S

__srv2_io__ = True

STRIKE_STEP = _S.STRIKE_STEP
STRATEGY_SETTINGS_DEFAULTS = {_S.STRATEGY_KEY: _S.DEFAULTS}
MARUBOZU_TRENDING_THRESHOLD = 0.8                                       # cloud_db L2168
clean_signal_symbols = _S.clean_signal_symbols
SIGNAL_SYMBOLS_DEFAULT = _S.SIGNAL_SYMBOLS_DEFAULT


def is_cloud_db_configured():
    """True: ATP's store stands in for Supabase."""
    return True


def _get_strategy_settings_ungated(strategy_name, symbol):
    """cloud_db._get_strategy_settings_ungated (L1054-1100): defaults (scaled by the strike step) + symbol_enabled default + the stored
    row (stored wins). The store unreachable => the defaults (Trade: the last good copy, else the defaults)."""
    defaults = _S.scale_strike_relative_defaults(dict(STRATEGY_SETTINGS_DEFAULTS.get(strategy_name, {})), symbol)
    defaults["symbol_enabled"] = (symbol == "NIFTY") if strategy_name != "classic_sr_reversal" else False
    try:
        stored = _H.need("settings")(strategy_name, symbol)
    except _H.HostNotReady:
        raise
    except Exception:                                                   # noqa: BLE001 - as Trade: DB error => defaults
        return defaults
    if not stored:
        return defaults
    merged = dict(defaults)
    merged.update(stored)
    return merged


def get_strategy_settings(strategy_name, symbol):
    """cloud_db.get_strategy_settings (L1041-1052): a stored LIVE / LIVE_PAPER is returned only with the owner's LIVE confirmation
    (`live_confirmed` adapter; Trade: live_confirm.effective_mode); otherwise trading_mode PAPER + live_unconfirmed."""
    merged = _get_strategy_settings_ungated(strategy_name, symbol)
    try:
        mode = merged.get("trading_mode") if isinstance(merged, dict) else None
        if str(mode or "").upper() in ("LIVE", "LIVE_PAPER"):
            ok = bool(_H.get("live_confirmed", lambda *a: False)(strategy_name, symbol, mode))
            if not ok:
                merged = {**merged, "trading_mode": "PAPER", "live_unconfirmed": mode}
    except Exception:                                                   # noqa: BLE001 - the check failed => PAPER
        merged = {**merged, "trading_mode": "PAPER", "live_unconfirmed": merged.get("trading_mode")}
    return merged


def get_signal_symbols():
    """cloud_db.get_signal_symbols (L1340-1346): the stored list (`signal_symbols` adapter) cleaned; none / bad => the default."""
    try:
        raw = _H.get("signal_symbols", lambda: None)()
        return clean_signal_symbols(raw) if raw else list(SIGNAL_SYMBOLS_DEFAULT)
    except Exception:                                                   # noqa: BLE001
        return list(SIGNAL_SYMBOLS_DEFAULT)


def get_effective_upstox_token(cli_token, account_id=None):
    """cloud_db.get_effective_upstox_token: an explicit token wins, else ATP's Upstox session token of the owner (None = no login)."""
    if cli_token:
        return cli_token
    return _H.need("token")()


KILL_SWITCH_STRATEGY_KEY = "__global_kill_switch__"
KILL_SWITCH_SYMBOL_KEY = "ALL"
# 🎓 वापरकर्त्याने मागितलेली सुधारणा ("Kill switch मध्ये loss limit पाहिजे का discuss" -> "ekun
# capital chya respected te asayla pahije both loss and profit, certain profit book jhalyanantr,
# automatic trading stop karne awashyak") — आधी max_daily_loss एक स्थिर ₹ आकडा होता (₹10,000,
# capital वाढलं/कमी झालं तरी न बदलणारा). आता दोन्ही मर्यादा (तोटा आणि नफा दोन्ही) **एकूण capital
# च्या %** म्हणून साठवल्या जातात — प्रत्यक्ष ₹ रक्कम trading_engine.check_kill_switch() मध्ये,
# त्या क्षणीच्या upstox_api.get_total_capital() वरून काढली जाते. max_daily_profit_pct — नवीन —
# आजचा नफा इतका % गाठला की उरलेल्या दिवसासाठी नवीन LIVE trades आपोआप थांबतात (नफा दिला जाऊ नये
# म्हणून, तोट्याप्रमाणेच एक सुरक्षा-मर्यादा).
KILL_SWITCH_DEFAULTS = {
    "enabled": True,
    "max_daily_loss_pct": 2.0,
    "max_daily_profit_pct": 3.0,
    "max_trades_per_day": 15,
    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा ("1 trade profit मध्ये exit जाला, दुसरा उघडा असेल,
    # तर काही नफा नेहमी लॉक व्हावा, जेणेकरून नफ्यातून तोटा होणार नाही") — max_daily_profit_pct (वरचं)
    # एक स्थिर, ठराविक लक्ष्य आहे — profit_lock हे त्याहून वेगळं, गतिशील (ratchet): दिवसभरात कधीही
    # गाठलेला सर्वोच्च नफा (peak, वरचं लक्ष्य गाठण्याआधीही) घेऊन, त्यातला profit_lock_pct% कायमचा
    # "मजला" (floor) म्हणून लॉक — सद्य एकूण नफा त्या मजल्याखाली घसरला की नवीन LIVE trades थांबतात
    # (आधीच उघडे trades मात्र त्यांच्याच SL/Target नुसार चालू राहतात — established pattern, इतर सर्व
    # kill switches प्रमाणेच). डीफॉल्ट बंद — जुनं वर्तन (फक्त max_daily_profit_pct) कायम राहतं.
    "profit_lock_enabled": False,
    "profit_lock_pct": 50.0,
    # 🎓 वापरकर्त्याने सापडवलेली त्रुटी ("Kill switch ne trade band kele nahi", आजचा तोटा ₹-45,061 तरी
    # Kill Switch 'OK — LIVE P&L ₹0') — दोन कारणं: (१) फक्त LIVE trades मोजले जायचे, (२) % चा आधार फक्त Upstox
    # खात्यातलं भांडवल (~₹97,400) होता. वापरकर्त्याचे निर्णय: (१) LIVE + PAPER (shadow वगळून), प्रत्येक mode
    # स्वतंत्र तपासला जातो; (२) % हा "trade साठी वापरलेल्या margin" (आजचा सर्वोच्च एकाच वेळी वापरलेला margin) वर.
    "count_paper_pnl": True,
    "capital_from_margin_used": True,
    # किमान भांडवल (₹) — सुरुवातीला margin कमी असताना मर्यादा अति-कमी होऊ नये म्हणून ऐच्छिक मजला. 0 = मजला नाही.
    "min_capital_floor": 0.0,
}


def get_kill_switch_settings():
    """आजचा एकत्रित (सर्व symbols/strategies मिळून) LIVE Kill Switch — enabled/max_daily_loss_pct/
    max_daily_profit_pct/max_trades_per_day/profit_lock_enabled/profit_lock_pct. Supabase न
    मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट."""
    settings = get_strategy_settings(KILL_SWITCH_STRATEGY_KEY, KILL_SWITCH_SYMBOL_KEY)
    return {
        "enabled": bool(settings.get("enabled", KILL_SWITCH_DEFAULTS["enabled"])),
        "max_daily_loss_pct": settings.get("max_daily_loss_pct", KILL_SWITCH_DEFAULTS["max_daily_loss_pct"]),
        "max_daily_profit_pct": settings.get("max_daily_profit_pct", KILL_SWITCH_DEFAULTS["max_daily_profit_pct"]),
        "max_trades_per_day": settings.get("max_trades_per_day", KILL_SWITCH_DEFAULTS["max_trades_per_day"]),
        "profit_lock_enabled": bool(settings.get("profit_lock_enabled", KILL_SWITCH_DEFAULTS["profit_lock_enabled"])),
        "profit_lock_pct": settings.get("profit_lock_pct", KILL_SWITCH_DEFAULTS["profit_lock_pct"]),
        "count_paper_pnl": bool(settings.get("count_paper_pnl", KILL_SWITCH_DEFAULTS["count_paper_pnl"])),
        "capital_from_margin_used": bool(settings.get("capital_from_margin_used", KILL_SWITCH_DEFAULTS["capital_from_margin_used"])),
        "min_capital_floor": float(settings.get("min_capital_floor", KILL_SWITCH_DEFAULTS["min_capital_floor"]) or 0.0),
    }


MCX_KILL_SWITCH_STRATEGY_KEY = "__mcx_kill_switch__"
MCX_KILL_SWITCH_SYMBOL_KEY = "ALL"
MCX_KILL_SWITCH_DEFAULTS = {
    "enabled": True,
    "max_daily_loss_pct": 1.0,
    "max_open_positions": 2,
    # 🎓 ग्लोबल KILL_SWITCH_DEFAULTS च्या profit_lock_enabled/profit_lock_pct सारखंच, पण फक्त MCX
    # (source='mcx_futures') पुरतं — बघा तिथली टिप्पणी. डीफॉल्ट बंद.
    "profit_lock_enabled": False,
    "profit_lock_pct": 50.0,
}


def get_mcx_kill_switch_settings():
    """MCX-विशिष्ट (5 commodities मिळून) Kill Switch — enabled/max_daily_loss_pct/max_open_positions/
    profit_lock_enabled/profit_lock_pct. Supabase न मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट
    (ग्लोबलपेक्षा जाणीवपूर्वक कडक — 1% loss cap, कमाल 2 positions एकाच वेळी, brand-new रणनीतीसाठी)."""
    settings = get_strategy_settings(MCX_KILL_SWITCH_STRATEGY_KEY, MCX_KILL_SWITCH_SYMBOL_KEY)
    return {
        "enabled": bool(settings.get("enabled", MCX_KILL_SWITCH_DEFAULTS["enabled"])),
        "max_daily_loss_pct": settings.get("max_daily_loss_pct", MCX_KILL_SWITCH_DEFAULTS["max_daily_loss_pct"]),
        "max_open_positions": settings.get("max_open_positions", MCX_KILL_SWITCH_DEFAULTS["max_open_positions"]),
        "profit_lock_enabled": bool(settings.get("profit_lock_enabled", MCX_KILL_SWITCH_DEFAULTS["profit_lock_enabled"])),
        "profit_lock_pct": settings.get("profit_lock_pct", MCX_KILL_SWITCH_DEFAULTS["profit_lock_pct"]),
    }


PORTFOLIO_RISK_CAP_STRATEGY_KEY = "__portfolio_risk_cap__"
PORTFOLIO_RISK_CAP_SYMBOL_KEY = "ALL"
PORTFOLIO_RISK_CAP_DEFAULTS = {
    "enabled": False,
    "max_portfolio_risk_pct_index": 6.0,
    "max_portfolio_risk_pct_mcx": 6.0,
}


def get_portfolio_risk_cap_settings():
    """Portfolio-wide Open-Risk Cap — enabled/max_portfolio_risk_pct_index/max_portfolio_risk_pct_mcx.
    Supabase न मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट (enabled=False — गेट बंदच राहतो)."""
    settings = get_strategy_settings(PORTFOLIO_RISK_CAP_STRATEGY_KEY, PORTFOLIO_RISK_CAP_SYMBOL_KEY)
    return {
        "enabled": bool(settings.get("enabled", PORTFOLIO_RISK_CAP_DEFAULTS["enabled"])),
        "max_portfolio_risk_pct_index": settings.get(
            "max_portfolio_risk_pct_index", PORTFOLIO_RISK_CAP_DEFAULTS["max_portfolio_risk_pct_index"]),
        "max_portfolio_risk_pct_mcx": settings.get(
            "max_portfolio_risk_pct_mcx", PORTFOLIO_RISK_CAP_DEFAULTS["max_portfolio_risk_pct_mcx"]),
    }




TRADING_PAUSE_STRATEGY_KEY = "__global_trading_pause__"
TRADING_PAUSE_SYMBOL_KEY = "ALL"


def get_trading_pause_settings():
    """सर्व symbols/strategies/PAPER+LIVE साठी एकत्रित — मॅन्युअल 'नवीन Trades थांबवा' स्थिती.
    Supabase न मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट — paused=False (चालू)."""
    settings = get_strategy_settings(TRADING_PAUSE_STRATEGY_KEY, TRADING_PAUSE_SYMBOL_KEY)
    return {
        "paused": bool(settings.get("paused", False)),
        "reason": settings.get("reason", ""),
        "paused_at": settings.get("paused_at"),
    }


VIX_SPIKE_HALT_STRATEGY_KEY = "__vix_spike_halt__"
VIX_SPIKE_HALT_SYMBOL_KEY = "NIFTY"
VIX_SPIKE_HALT_DEFAULTS = {"enabled": True, "threshold_pct": 5.0}


def get_vix_spike_halt_settings():
    """NIFTY-विशिष्ट VIX Spike Halt — enabled/threshold_pct (वापरकर्ता-निवडलेले, Dashboard वरून
    बदलता येण्याजोगे), अधिक आजच्या दिवसाची स्थिती (halted/trade_date/prev_close/current_vix/
    pct_change/checked_at — check_vix_spike_halt.py ने सकाळी साठवलेली, अजून तपासणी न झालेली असेल तर
    सर्व None/False). Supabase न मिळाल्यास (किंवा अजून कधीच जतन न केलेलं) डीफॉल्ट."""
    settings = get_strategy_settings(VIX_SPIKE_HALT_STRATEGY_KEY, VIX_SPIKE_HALT_SYMBOL_KEY)
    return {
        "enabled": bool(settings.get("enabled", VIX_SPIKE_HALT_DEFAULTS["enabled"])),
        "threshold_pct": settings.get("threshold_pct", VIX_SPIKE_HALT_DEFAULTS["threshold_pct"]),
        "halted": bool(settings.get("halted", False)),
        "trade_date": settings.get("trade_date"),
        "prev_close": settings.get("prev_close"),
        "current_vix": settings.get("current_vix"),
        "pct_change": settings.get("pct_change"),
        "checked_at": settings.get("checked_at"),
    }


def get_telegram_policy(raw_fn=None):
    """cloud_db.get_telegram_policy (L1467-1481) with clean_telegram_policy (L1446-1464), verbatim."""
    import atp_private.trade_engine.notify_policy as NP
    out = NP.defaults()
    try:
        stored = (raw_fn or get_strategy_settings)(TELEGRAM_POLICY_STRATEGY_KEY, TELEGRAM_POLICY_SYMBOL_KEY) or {}
    except Exception:                                                     # noqa: BLE001
        stored = {}
    for k in list(out):
        if k in stored:
            try:
                out.update(clean_telegram_policy({k: stored[k]}))
            except ValueError:
                pass
    return out


TELEGRAM_POLICY_STRATEGY_KEY = "__telegram_policy__"
TELEGRAM_POLICY_SYMBOL_KEY = "ALL"


def clean_telegram_policy(changes):
    import atp_private.trade_engine.notify_policy as NP
    out = {}
    for k, v in dict(changes or {}).items():
        v = str(v).strip().lower()
        if k == "quiet_mode":
            if v not in ("on", "off"):
                raise ValueError(f"quiet_mode = {v!r} — on / off")
        elif k in NP.LOCKED:
            continue
        elif k in NP.TYPES:
            if v not in NP.MODES:
                raise ValueError(f"{k} = {v!r} — {NP.MODES}")
        else:
            raise ValueError(f"unknown Telegram message type: {k}")
        out[k] = v
    return out


def get_next_level_in_direction(symbol, entry_level_price, direction_bullish, timeframe_suffixes=("15M", "30M", "60M")):
    """cloud_db.get_next_level_in_direction (L1647-1680) reads Trade's `market_zones` table (the legacy level bots' zones), which is not
    ported. For the engine's positions (entry_timeframe "ENGINE") Trade asks for zone types *_ENGINE, of which no writer exists, so Trade
    finds no level either: None here is Trade's own result (owner 18 Nov: kept AS IS, noted)."""
    return


def get_all_broker_accounts(active_only=True):
    """cloud_db.get_all_broker_accounts (L890-908): other brokers' accounts for multi-account LIVE - not ported (LIVE is not wired);
    None = Trade's result when its database is unreachable."""
    return


def _not_ported(name):
    def fn(*args, **kwargs):
        raise _H.HostNotReady(f"cloud_db.{name}: OI snapshots of Trade's other bots are not part of this port")
    fn.__name__ = name
    return fn


for _n in ("get_iv_change_from_average", "get_latest_oi_signal_cloud", "get_latest_oi_snapshot_cloud", "get_oi_history_cloud",
           "get_previous_day_oi_cloud", "get_recent_oi_snapshots_cloud", "save_oi_snapshot_cloud", "save_strike_oi_snapshot",
           "save_signal_log", "get_market_zones", "get_srv2_state", "save_srv2_state"):
    globals()[_n] = _not_ported(_n)
