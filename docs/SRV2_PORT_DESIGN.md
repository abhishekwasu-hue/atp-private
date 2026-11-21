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

## P1b (Trade's PAPER engine, OPEN_QUESTIONS SRV2-Q1 default A)

- Copied AS IS (same tool, group `srv2_engine`, 20 modules): `trading_engine`, `database`, `trade_monitor`, `order_safety`,
  `entry_inflight`, `carry_guard`, `exit_price_fallback`, `monitor_timing`, `charges`, `log_setup`, `process_lock`, `order_execution`,
  `engine_service`, `oi_analysis`, `paper/watch`, `paper/journal`, `mcx_contract_specs`, `mcx_quantity_check`, `notify_policy`,
  `read_cache`. The bot's positions live in Trade's own SQLite store (`live_trades`) under `SRV2_DATA_DIR` on ATP's data volume.
- `atp_private/adapters/trade_config.py`: Trade config's operational constants and market-hours functions added verbatim (the engine
  never reads them; the engine's own values are unchanged).
- `atp_private/srv2/io/`: stand-ins for Trade's IO modules - `cloud_db` (defaults + getters verbatim; rows from ATP), `upstox_api`
  (ATP's Upstox app through ATP's budget; PAPER fill verbatim; LIVE refused), `notifications` (Telegram through ATP; texts, policy,
  cool-down verbatim), `broker_factory` (none), `classic_sr_reversal_trader` / `signals` (the one function used, verbatim).
- What ATP must register: settings, signal_symbols, token, option_chain, option_expiries, ltp, funds (Trade's kill switch needs the
  capital, PAPER too), option_greeks, send, live_confirmed. `next level` finds no level for engine positions, as in Trade.
- Tests `tests/test_srv2_engine.py`: entry -> two PAPER positions in Trade's store; the spread closes at PREMIUM_TARGET; a spot fall
  stops it out (SL); nothing moves -> nothing closes; a LIVE order is refused. Exit clock fixed at 10:30 IST.

## P3 (Vision -> Telegram ✅, and the owner's agent modes: AGENT-MODES 20 Nov, ATP ADR-0029)

- Copied AS IS (WIP commit, tool group `srv2_vision`): `vision/{gate,hook,store,config,decide,notify,worker,chart,images,approval,tg,
  telegram_bot,card_summary,outcome,signal_audit}`, `paper/card_quote`, `vision_led/situation_map`. `srv2/io/notifications` sends through
  Trade's own Telegram code when the bot's credentials are in the worker's environment (names only: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
  TELEGRAM_APPROVER_IDS, VISION_CALLBACK_SECRET, ANTHROPIC_API_KEY; values only on the host).
- `srv2/runner.py`: `start_services()` runs Trade's two services in two daemon threads of ATP's worker, never inside `tick` (a Vision
  call or a Telegram long-poll never delays the exit monitor, ADR-0004): the vision worker (`vision_worker.service`: lock, stale rows
  expired, orphans re-queued, `run_once` every 2 s) and the Telegram ✅ poll (`vision_telegram.service`: needs the callback secret and the
  approver ids, open cards EXPIRED on start, `poll_once` every 0.5 s). Card expiry is Trade's own (`gate.resolve_due`,
  `worker.v1_housekeeping`: deadline = signal + `approve_window_min`; no ✅ = REJECTED = no entry; a late tap is refused).
- `srv2/modes.py`: the two agent modes as values of Trade's OWN Vision settings (no new rule): `human_confirm` (default for a new
  deployment) = `vision_mode human_confirm` + `approval_required` (only a `telegram:<id>` ✅ enters); `auto` + Vision on = `auto_veto`,
  no approval, `vision_fail_action skip`; `auto` + Vision off = `off`, no approval (the bot's own rules). Written through Trade's
  `VC.save` (its change history) and returned as an audit record for ATP. `auto` is refused unless ATP says it is the owner's own
  deployment; switching back to `human_confirm` is always allowed; an unreadable / hand-edited row reads as `human_confirm`.
- PAPER and LIVE: one code path. The engine entry stays PAPER only (Trade); a stored LIVE reads as PAPER until the owner's LIVE switch;
  the order edge refuses LIVE in both modes. Risk hierarchy / kill switch: Trade's `open_multi_leg_trade` checks, unchanged, both modes.
- Tests `tests/test_srv2_vision.py` (Trade's real gate, worker decision step and callback handler; only the network edges faked):
  default human_confirm; a switch audited (who, from -> to, Trade history); auto refused outside the owner's deployment; ✅ -> entry
  with the dashboard lots; an expired card places nothing (and a late tap is refused); someone else's tap / ❌ / a Vision-only approval
  place nothing; auto with Vision off / on (disagree and unavailable skip, agree enters); parity: auto places exactly the positions
  human_confirm places after ✅ for the same bars; LIVE refused unless the owner's switch, and the order edge refuses LIVE.
- Open: SRV2-Q5 (`auto` + Vision unavailable: default skip), SRV2-Q6 (`auto` + Vision gray: Trade's default `half` = advice only, enters
  at full lots), SRV2-Q7 (plotly + kaleido must be in ATP's backend image for the card's chart photo, as this design already says; the
  card without them is not tested here). Logged in ATP docs/OPEN_QUESTIONS.md by the ATP session.

## Next

P1b ATP: the owner-only "SRv2 bot" deployment, the adapters (Upstox chain / expiries through the broker budget, the owner's open
positions, the PAPER open, Telegram send), the runner (engine per 5M close, bot cycle every minute in the market hours, as Trade's
cron). P2 settings page (+ the agent-mode switch, ATP side). P4 exits. P5 parity + screenshots. Matplotlib / plotly / kaleido go into ATP's backend
image with P3 (the engine's charts).
