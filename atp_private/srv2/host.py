"""atp_private.srv2.host - ATP's adapters for the Trade IO modules the 15M SRv2 bot glue calls (owner order SRV2, 18 Nov).

The bot glue under `atp_private/trade_engine/` (paper/engine_entry.py, paper/bot_hooks.py, ...) is Trade's code AS IS; at run time it
imports Trade's IO modules by name (`cloud_db`, `database`, `upstox_api`, `trading_engine`, `notifications`,
`classic_sr_reversal_trader`). Those are ATP-GENERIC (Trade tools/trade_sync/engine_closure.py) and are NOT copied: `install()` puts small
modules with the same names and the same function signatures into `sys.modules`, and each function calls the callable ATP registered
(`register(...)`). Nothing here decides anything about a trade: every rule stays in the copied Trade code.

Fail-closed: a function whose callable ATP has not registered raises `HostNotReady`; the copied code already turns any error on the entry
path into "no entry" (engine_entry._alert / bot_hooks.pre_cycle). Exits never pass through this module.

    from atp_private.srv2 import host
    host.register(settings=..., token=..., option_chain=..., option_expiries=..., has_open=..., open_trade=..., send=...)
    host.install()
"""
from __future__ import annotations

import sys
import types

from . import settings as S

PREFIX = "atp_private.trade_engine"
NAMES = ("settings", "signal_symbols", "token", "option_chain", "option_expiries", "candles", "has_open", "open_trade", "send",
         "live_confirmed")


class HostNotReady(RuntimeError):
    """ATP has not registered the adapter a Trade IO call needs (the call fails; the copied code turns it into "no entry")."""


_IMPL: dict = {}


def register(**impls):
    """Register ATP's callables (any subset; `None` removes one). Unknown names raise (a typo never silently drops an adapter)."""
    bad = sorted(set(impls) - set(NAMES))
    if bad:
        raise TypeError(f"unknown host adapter(s): {bad}")
    for k, v in impls.items():
        if v is None:
            _IMPL.pop(k, None)
        else:
            _IMPL[k] = v


def reset():
    """Tests: forget every registered callable."""
    _IMPL.clear()


def _need(name):
    fn = _IMPL.get(name)
    if fn is None:
        raise HostNotReady(f"ATP adapter '{name}' is not registered")
    return fn


# --- cloud_db --------------------------------------------------------------------------------------------------------------------------
def get_strategy_settings(strategy_name, symbol):
    """cloud_db.get_strategy_settings for `15m_dynamic_sr`: the Trade defaults merged with the stored row (`settings` adapter returns
    the stored dict or None). A stored LIVE / LIVE_PAPER without the owner's LIVE confirmation (`live_confirmed` adapter; none
    registered = not confirmed) is returned as PAPER + `live_unconfirmed`, as Trade's cloud_db does with live_confirm. Signal symbols
    (`__signal_symbols__`) come from `get_signal_symbols`."""
    if strategy_name != S.STRATEGY_KEY:
        raise HostNotReady(f"settings of '{strategy_name}' are not part of this port")
    stored = _need("settings")(strategy_name, symbol)
    out = S.merged(symbol, stored)
    mode = str(out.get("trading_mode") or "").upper()
    if mode in ("LIVE", "LIVE_PAPER"):
        ok = False
        try:
            ok = bool(_IMPL.get("live_confirmed", lambda *_: False)(strategy_name, symbol, mode))
        except Exception:                                                   # noqa: BLE001 - the check failed => PAPER (never LIVE by accident)
            ok = False
        if not ok:
            out = {**out, "trading_mode": "PAPER", "live_unconfirmed": out.get("trading_mode")}
    return out


def get_signal_symbols():
    """cloud_db.get_signal_symbols: the stored list (`signal_symbols` adapter), cleaned; none / unreadable / bad => the default."""
    try:
        raw = _IMPL["signal_symbols"]() if "signal_symbols" in _IMPL else None
        return S.clean_signal_symbols(raw) if raw else list(S.SIGNAL_SYMBOLS_DEFAULT)
    except Exception:                                                       # noqa: BLE001
        return list(S.SIGNAL_SYMBOLS_DEFAULT)


def get_effective_upstox_token(cli_token, account_id=None):
    """cloud_db.get_effective_upstox_token: an explicit token wins, else ATP's Upstox session token for the owner (None = no login)."""
    if cli_token:
        return cli_token
    return _need("token")()


# --- upstox_api ------------------------------------------------------------------------------------------------------------------------
def fetch_upstox_option_chain(access_token, symbol, expiry_index=0):
    """upstox_api.fetch_upstox_option_chain: (chain rows in Upstox's own option-chain shape, reason) - ATP reads it through its broker
    budget."""
    return _need("option_chain")(access_token, symbol, expiry_index)


def fetch_option_expiries(access_token, symbol):
    """upstox_api.fetch_option_expiries: the expiry dates "YYYY-MM-DD", nearest first."""
    return _need("option_expiries")(access_token, symbol)


def fetch_candles(*args, **kwargs):
    """upstox_api.fetch_candles (engine_signal's older single-setup path)."""
    return _need("candles")(*args, **kwargs)


# --- database / trading_engine / notifications ----------------------------------------------------------------------------------------
def has_open_trade_from_source(symbol, source):
    """database.has_open_trade_from_source: an open position of this bot (`source`) on this symbol (the one-at-a-time rule)."""
    return bool(_need("has_open")(symbol, source))


def open_multi_leg_trade(access_token, symbol, strategy_result, lots, lot_size, sl_pct_of_max_loss, target_pct_of_max_profit, product_type,
                         trading_mode="LIVE", trading_style="INTRADAY", sl_pct_of_credit=None, source="MANUAL", adapter=None,
                         entry_level_price=None, entry_timeframe=None, entry_spot_price=None, entry_reason_tag=None, direction=None,
                         is_directional_trade=False):
    """trading_engine.open_multi_leg_trade (same signature): ATP opens the position through its own order path -> (ok, message)."""
    return _need("open_trade")(access_token, symbol, strategy_result, lots=lots, lot_size=lot_size,
                               sl_pct_of_max_loss=sl_pct_of_max_loss, target_pct_of_max_profit=target_pct_of_max_profit,
                               product_type=product_type, trading_mode=trading_mode, trading_style=trading_style,
                               sl_pct_of_credit=sl_pct_of_credit, source=source, entry_level_price=entry_level_price,
                               entry_timeframe=entry_timeframe, entry_spot_price=entry_spot_price, entry_reason_tag=entry_reason_tag,
                               direction=direction, is_directional_trade=is_directional_trade)


def send_telegram_message(message, timeout=10, silent=False, kind=None):
    """notifications.send_telegram_message: ATP sends it to the owner's linked Telegram chat -> bool."""
    return bool(_need("send")(message, silent=silent, kind=kind))


# --- classic_sr_reversal_trader -------------------------------------------------------------------------------------------------------
def is_todays_expiry_day(access_token, symbol):
    """classic_sr_reversal_trader.is_todays_expiry_day (Trade L141-146), verbatim apart from the imports."""
    from atp_private.trade_engine.config import get_ist_now
    expiries = fetch_option_expiries(access_token, symbol)
    if not expiries:
        return False
    return expiries[0] == get_ist_now().strftime("%Y-%m-%d")


_MODULES = {
    "cloud_db": {"get_strategy_settings": get_strategy_settings, "get_signal_symbols": get_signal_symbols,
                 "get_effective_upstox_token": get_effective_upstox_token, "STRIKE_STEP": S.STRIKE_STEP,
                 "clean_signal_symbols": S.clean_signal_symbols},
    "upstox_api": {"fetch_upstox_option_chain": fetch_upstox_option_chain, "fetch_option_expiries": fetch_option_expiries,
                   "fetch_candles": fetch_candles},
    "database": {"has_open_trade_from_source": has_open_trade_from_source},
    "trading_engine": {"open_multi_leg_trade": open_multi_leg_trade},
    "notifications": {"send_telegram_message": send_telegram_message},
    "classic_sr_reversal_trader": {"is_todays_expiry_day": is_todays_expiry_day},
}


def install():
    """Put the adapter modules into sys.modules under the names the copied code imports (`atp_private.trade_engine.<name>`). Idempotent;
    never replaces a real module of the snapshot."""
    import atp_private.trade_engine as pkg
    for name, attrs in _MODULES.items():
        full = f"{PREFIX}.{name}"
        mod = sys.modules.get(full)
        if mod is not None and not getattr(mod, "__srv2_host__", False):
            raise RuntimeError(f"{full} already exists as a real module - not replaced")
        mod = types.ModuleType(full, f"ATP adapter for Trade's {name} (atp_private.srv2.host)")
        mod.__srv2_host__ = True
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[full] = mod
        setattr(pkg, name, mod)


def uninstall():
    """Tests: remove the adapter modules install() added (a real module is never touched)."""
    import atp_private.trade_engine as pkg
    for name in _MODULES:
        full = f"{PREFIX}.{name}"
        mod = sys.modules.get(full)
        if mod is not None and getattr(mod, "__srv2_host__", False):
            del sys.modules[full]
            if getattr(pkg, name, None) is mod:
                delattr(pkg, name)
