"""N3 (30 Oct, DECISIONS 142) — the approval card's money line from the option chain at card time: the spread the PAPER entry would
take today (`strategy.select_credit_spread_itm` with the bot's own dashboard settings), its credit ₹ and max loss ₹ for the user's own
lots × the Upstox lot size. Display only: it reads the chain, never places / blocks / changes an order. Never raises; {} when unknown."""
import datetime as dt


def quote(bot, symbol, direction, settings_fn=None, token_fn=None, chain_fn=None, lot_size_fn=None):
    """{"strikes": "24,400/24,300 PE", "expiry": "06 Nov", "credit_rs": 3250.0, "max_loss_rs": 9750.0, "lots": 1} or {} / {"lots": n}."""
    from . import engine_entry as EE
    key = EE.BOT_SETTINGS_KEY.get(bot)
    if key is None or direction not in ("BULLISH", "BEARISH"):
        return {}
    try:
        import atp_private.trade_engine.cloud_db as cloud_db
        settings = (settings_fn or cloud_db.get_strategy_settings)(key, symbol)
        if not settings.get("credit_spread_enabled", True):
            return {}
        lots = int(settings["lots"])
        token = (token_fn or (lambda: cloud_db.get_effective_upstox_token(None)))()
        chain, _why = (chain_fn or EE.fetch_chain)(token, symbol)
        if not chain:
            return {"lots": lots}
        if lot_size_fn is None:
            from . import lots as PL
            lot_size_fn = lambda tok, sym: PL.lot_size(tok, sym)[0]      # noqa: E731
        size = lot_size_fn(token, symbol)
        from atp_private.trade_engine.strategy import select_credit_spread_itm
        spot = chain[0].get("underlying_spot_price")
        step = cloud_db.STRIKE_STEP.get(symbol, cloud_db.STRIKE_STEP["NIFTY"])
        sp = select_credit_spread_itm(chain, direction, round(spot / step) * step, step=step,
                                      itm_depth_points=settings["itm_depth_points"], hedge_width_points=settings["hedge_width_points"])
        if sp is None or not size:
            return {"lots": lots}
        s, l = sp["short_leg"], sp["long_leg"]
        out = {"strikes": f"{s['strike']:,.0f}/{l['strike']:,.0f} {s['option_type']}", "lots": lots,
               "credit_rs": float(sp["net_credit"]) * lots * size, "max_loss_rs": float(sp["max_loss"]) * lots * size}
        try:
            out["expiry"] = dt.date.fromisoformat(str(s.get("expiry"))[:10]).strftime("%d %b")
        except ValueError:
            pass
        return out
    except Exception as exc:                                             # noqa: BLE001 — display only
        print(f"⚠️ card quote {symbol}: {type(exc).__name__}: {str(exc)[:120]}")
        return {}
