# 15M SRv2 port - design (owner order SRV2, 15 + 18 Nov "Default yes")

Audit: `docs/SRV2_PORT_AUDIT.md`. Rule: AS IS, so no change to the engine, the entry guards, the leg selection or the exits. The bot
reads the owner's own method, so it is owner-only (ATP DECISIONS 15 Nov, chart reader).

## Shape

| Part | Where | What |
|---|---|---|
| Engine | atp-private `trade_engine` (snapshot v2) | `engine3_live.compute` -> `engine_signal` store (SQLite file on ATP's data volume, `ENGINE_SIGNAL_DB`), run per 5M close, settings = the bot's `engine3_*` keys |
| Bot glue (P1) | atp-private `trade_engine/paper/*`, `strategy.py`, `bots_common/{gate_alert,error_once}.py` | copied AS IS (import rewrite only, `tools/trade_sync/bot_glue_import.py`); `paper.engine_entry.process` runs the engine path exactly as Trade's `srv2_momentum_reversal_strategy.process_symbol` -> `bot_hooks.pre_cycle` |
| ATP adapters (P1) | atp-private `srv2/host.py` | stand-ins for Trade's IO modules (`cloud_db`, `database`, `upstox_api`, `trading_engine`, `notifications`, `classic_sr_reversal_trader`) with the same signatures; each calls the callable ATP registers; none registered = the call fails = no entry |
| Settings (P1 + P2) | atp-private `srv2/settings.py` + ATP | Trade's 72 defaults verbatim + the stored row per symbol (ATP stores it, owner-only page under one button); signal symbols; a stored LIVE reads as PAPER until the owner's LIVE confirmation |
| Vision -> Telegram (P3) | atp-private copy of Trade `vision/{gate,hook,store,config,decide,notify,worker,chart,approval,tg,telegram_bot}` + ATP adapters | the gate holds the entry until the owner's ✅; card = chart photo + ✅ ❌ ✏️ 📎 📝 in one message; expiry states as Trade; Vision on the owner's own key |
| Entries (P4) | ATP `open_trade` adapter | `open_multi_leg_trade` signature -> ATP's own PAPER position (LTP fills) through the order path; LIVE through the same path, refused until the owner's words (B1, web approval for LIVE) |
| Exits (P4) | atp-private copy of Trade `trading_engine.manage_open_trades` srv2 branch as a pure exit decision + ATP position monitor | settings re-read at exit time; exits never blocked (ADR-0004); next-level exit for engine positions AS IS (finds no level, noted) |
| Parity (P5) | atp-private tests + trade-data replay | one Trade replay day: same signals, same gate calls, same legs, same exits; screenshots of the settings page and the card |

## P1 (this PR)

- Copied: `paper/{__init__,engine_entry,bot_hooks,config,lots,pause}.py`, `strategy.py`, `bots_common/{gate_alert,error_once}.py` and
  `config.yaml` (Trade's `paper:` section only). Trade's `config.py` is NOT copied: the existing `atp_private.adapters.trade_config`
  (ATP's calendar) stays the engine's clock.
- `srv2/host.py`: `register(...)`, `install()`, `uninstall()`; adapters `settings`, `signal_symbols`, `token`, `option_chain`,
  `option_expiries`, `candles`, `has_open`, `open_trade`, `send`, `live_confirmed`.
- Tests `tests/test_srv2_glue.py`: the copied rules act as in Trade (switches, cutoff, one position, max hits per zone, once per visit per
  model, PAPER only, signal symbols, legs = Trade's own `select_*` on the same chain); with `TRADE_SRC` set, every copied file equals
  Trade's after the same import rewrite, and the defaults equal Trade's.

## Next

P1b ATP: the owner-only "SRv2 bot" deployment, the adapters (Upstox chain / expiries through the broker budget, the owner's open
positions, the PAPER open, Telegram send), the runner (engine per 5M close, bot cycle every minute in the market hours, as Trade's
cron). P2 settings page. P3 Vision / Telegram. P4 exits. P5 parity + screenshots. Matplotlib / plotly / kaleido go into ATP's backend
image with P3 (the engine's charts).
