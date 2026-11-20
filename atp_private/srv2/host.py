"""atp_private.srv2.host - ATP's adapters for the Trade IO modules the 15M SRv2 bot calls (owner order SRV2, 18 Nov).

The bot's code under `atp_private/trade_engine/` is Trade's AS IS (the engine-entry glue, and Trade's PAPER engine: trading_engine,
database, trade_monitor, ...). At run time it imports Trade's IO modules by name: `cloud_db` (Supabase), `upstox_api` (Upstox REST),
`notifications` (Telegram), `broker_factory` (other brokers, LIVE), `classic_sr_reversal_trader`, `signals`. Those are not copied: they
talk to Trade's own services. `install()` puts the modules of `atp_private.srv2.io` into `sys.modules` under those names; they keep
Trade's function names and signatures and call the callables ATP registers here (`register(...)`).

Fail-closed: a function whose callable is not registered raises `HostNotReady`; the copied code turns an error on the entry path into
"no entry" and logs an exit-path error without closing anything. LIVE is not wired here: a LIVE order through these adapters is refused
(the owner's LIVE goes through ATP's own order path when he says so - DECISIONS 18 Nov SRV2).
"""
from __future__ import annotations

import importlib
import importlib.util
import sys

PREFIX = "atp_private.trade_engine"
NAMES = (
    "settings",          # (strategy_key, symbol) -> the stored settings row (dict) or None
    "token",             # () -> the owner's Upstox access token or None
    "option_chain",      # (token, symbol, expiry_index) -> (Upstox /option/chain rows, reason)
    "option_expiries",   # (token, symbol) -> ["YYYY-MM-DD", ...] nearest first
    "candles",           # Trade upstox_api.fetch_candles(...) signature -> DataFrame
    "ltp",               # (token, instrument_keys) -> ({key: ltp}, error_detail or None)
    "option_greeks",     # (token, instrument_keys) -> {key: {delta, gamma, theta, vega, iv}}
    "funds",             # (token) -> {"available_margin": float, "used_margin": float} or None
    "send",              # (text, silent, kind) -> bool: Telegram to the owner's linked chat
    "live_confirmed",    # (strategy_key, symbol, mode) -> bool: the owner's LIVE confirmation
)
# Trade module name -> the adapter module standing in for it
MODULES = {
    "cloud_db": "atp_private.srv2.io.cloud_db",
    "upstox_api": "atp_private.srv2.io.upstox_api",
    "notifications": "atp_private.srv2.io.notifications",
    "broker_factory": "atp_private.srv2.io.broker_factory",
    "classic_sr_reversal_trader": "atp_private.srv2.io.classic_sr_reversal_trader",
    "signals": "atp_private.srv2.io.signals",
}


class HostNotReady(RuntimeError):
    """ATP has not registered the adapter a Trade IO call needs (the call fails; the copied code handles it as Trade does)."""


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


def has(name):
    return name in _IMPL


def need(name):
    fn = _IMPL.get(name)
    if fn is None:
        raise HostNotReady(f"ATP adapter '{name}' is not registered")
    return fn


def get(name, default=None):
    return _IMPL.get(name, default)


def install():
    """Put the adapter modules into sys.modules under the names the copied code imports (`atp_private.trade_engine.<name>`). Idempotent;
    never replaces a real module of the snapshot."""
    import atp_private.trade_engine as pkg
    for name, target in MODULES.items():
        full = f"{PREFIX}.{name}"
        mod = sys.modules.get(full)
        if mod is not None and getattr(mod, "__srv2_io__", False):
            continue
        if mod is not None or importlib.util.find_spec(full) is not None:
            raise RuntimeError(f"{full} exists as a real module - not replaced")
        mod = importlib.import_module(target)
        sys.modules[full] = mod
        setattr(pkg, name, mod)


def uninstall():
    """Tests: remove the adapter modules install() added (a real module is never touched)."""
    import atp_private.trade_engine as pkg
    for name in MODULES:
        full = f"{PREFIX}.{name}"
        mod = sys.modules.get(full)
        if mod is not None and getattr(mod, "__srv2_io__", False):
            del sys.modules[full]
            if getattr(pkg, name, None) is mod:
                delattr(pkg, name)
