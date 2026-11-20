"""Stand-in for Trade's `classic_sr_reversal_trader` (a TRADE-ONLY bot): only `is_todays_expiry_day`, which the engine-entry glue uses,
verbatim (Trade L141-146) apart from the imports."""
__srv2_io__ = True


def is_todays_expiry_day(access_token, symbol):
    from atp_private.trade_engine.config import get_ist_now
    from atp_private.trade_engine.upstox_api import fetch_option_expiries
    expiries = fetch_option_expiries(access_token, symbol)
    if not expiries:
        return False
    return expiries[0] == get_ist_now().strftime("%Y-%m-%d")
