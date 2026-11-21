# 15M SRv2 port - audit (owner order 15 Nov, "audit first")

Two read-only audits merged into one file (owner rule A.11). Trade HEAD 813358b; ATP main ffa9f73e; atp-private main a306c7c.
Part A: the Trade bot. Part B: what ATP / atp-private already have. Owner live setting values are NOT known (not in any repo).

---

# Part A

# Audit: Trade bot "15M SRv2" (strategy_key `15m_dynamic_sr`) - inventory for an AS-IS port
## 1. Entry point and run loop

### 1.1 Processes (seen)
| Process | Started by | Cadence | File |
|---|---|---|---|
| Engine resident | cron `*/5 3-9 * * 1-5` UTC (08:30-15:25 IST), `flock /tmp/engine_resident.lock` (`scripts/install_engine_schedule.sh:71`) | at each 5M close + max(3 s, `engine3_bar_final_grace_s`), retries every 5 s up to 120 s, symbols in parallel; exits after the store window (`scripts/engine_resident.py:20-27`) | `scripts/engine_resident.py` (180) |
| Engine one-shot run | spawned by the resident per symbol (`--symbols SYM`, own lock `ENGINE_SIGNAL_LOCK_PATH`) | per 5M close (DECISIONS 37, `engine3_trigger_tf` default 5M); a 15M "what-if" mode exists | `scripts/engine_signal_run.py` (336) |
| Engine warm-up | cron `20 3 * * 1-5` UTC, `--dry-run --force` (`install_engine_schedule.sh:74`) | once a day, fills caches, writes nothing | same |
| 15M SRv2 bot | cron `45-59 3` and `* 4-10` UTC Mon-Fri, `sleep 30`, `--symbols NIFTY,BANKNIFTY,SENSEX` (`install_engine_schedule.sh:75-76`, deploy/README.md:228-229) | every minute 09:15:30-16:29:30 IST; one pass per run | `srv2_momentum_reversal_strategy.py` (783) `main` ~L748-783, `ProcessLock("srv2_momentum_reversal_strategy")` |
| Exits | cron every minute (deploy/README.md:16-17, 184) | internal loop: `--interval-seconds` 15, `--open-interval-seconds` 5 when a trade is open, `--tsl-interval-seconds` 5 (trade_monitor.py:23-56) | `trade_monitor.py` (257) -> `trading_engine.manage_open_trades` |
| Exits (optional, additive) | systemd `position_stream_monitor.service` | Upstox WebSocket ticks -> the same `manage_open_trades` | `position_stream_monitor.py` (218) |
| Vision worker | systemd `vision_worker.service` (`python3 -m vision.worker --loop-seconds 3600 --poll 2`) | polls QUEUED rows every 2 s | `vision/worker.py` (1329) |
| Telegram inbound | systemd `vision_telegram.service` (`python3 -m vision.telegram_bot`) | long-polling `getUpdates` | `vision/telegram_bot.py` (328) |
| Pre-open card | cron `30 3 * * 1-5` UTC (09:00 IST) (`install_engine_schedule.sh:77`) | once | `scripts/level_gate_preopen.py` (975) |
| EOD summary | cron `15 10 * * 1-5` UTC (15:45 IST) (`install_engine_schedule.sh:78`) | once | `scripts/paper_daily_summary.py` (387) |
| Dashboard | systemd `streamlit_dashboard.service` | on demand | `app.py` -> `page_bot_dynamic_sr_algo.py`, `page_dashboard.py` (bot_view), `page_vision_human_eye.py` |

The exact live crontab on the VPS was not read (not available here); the lines above are what the installer writes.

### 1.2 Data sources (seen)
- Broker / data: Upstox only (`upstox_api.fetch_candles`, `fetch_upstox_option_chain`, `fetch_option_expiries`; engine feed `engine3_live.UpstoxFeed` L250). Token from Supabase (`cloud_db.get_effective_upstox_token`, L2555) or `--token`.
- Engine inputs (`engine3_live.build_inputs` L652-726): 15M spot (`engine3_m15_days` 90), Daily spot (`engine3_daily_days` 3650), 5M spot LTF (`engine3_ltf_days` 10), near-month **FUT 5M** volume (`engine3_fut_days` 45; required for NIFTY / BANKNIFTY, `FUT_REQUIRED` L45 -> `FutVolumeMissing`), optional 1m spot (`engine3_use_1m`, `load_m1` L1025), 1H history from stored 15M (`h1_history_of` L1066, `engine3_h1_history_days` 1825). Spot for structure, FUT for volume. NIFTY rows pass `elliott.data_policy.filter_allowed(..., "annotation")` (holdout).
- Bot legacy path inputs: Supabase `market_zones` (`cloud_db.get_market_zones`), 15M/30M/60M candles (60M = resampled 30M, `_collect_touch_candidates` L150-189), today's 1m candles (L192-209), PCR (`oi_analysis.check_pcr_gate`).
- Entry execution: Upstox option chain (expiry index 1 on the expiry day, `paper/engine_entry.fetch_chain` L46-51), PAPER fill = LTP map (`upstox_api.execute_order_leg_set` L1024-1051, `paper_fills`).
- Lot size: Upstox instrument master (`paper/lots.py`), fallback `config.yaml paper.instruments.<SYM>.lot_size_fallback` (NIFTY 65, BANKNIFTY 30, SENSEX 20).

### 1.3 State kept (seen)
| Store | Where | Tables / files | Writer |
|---|---|---|---|
| Engine store (SQLite) | `ENGINE_SIGNAL_DB` or `data/engine_signals.db` (`engine_signal.py:60-75`) | `engine_signals`, `engine_consumed`, `engine_entry_consumed` (+ direction/lo/hi), `engine_entry_seen` (`engine_signal.py:41-56`) | engine run; engine_entry |
| Engine cache | `data/engine3_cache/` (`ENGINE3_CACHE_DIR`), pickles `hist_*`, `fold_*`, `profile_check.json` (`engine3_live.py` L201-645) | files | engine |
| Vision store (SQLite) | `VISION_DB_PATH` or `data/vision.db` (`vision/store.py:56-60`) | `vision_signals` (+ V1 columns L64-71), `vision_events`, `vision_usage`, `vision_settings`, `vision_settings_history`, `vision_kv`, `corrections` (L22-54) | gate, worker, telegram_bot |
| Trades (SQLite) | `data/historical_data.db` (`config.DB_PATH`) | `live_trades`, `order_log` (`database.py:77,158`) | `trading_engine.open_multi_leg_trade`, `manage_open_trades` |
| PAPER journal (SQLite) | `PAPER_JOURNAL_DB` or `data/paper_journal.db` | `paper_journal`, `paper_would_have` (`paper/journal.py:11-20`) | gate `_shadow`, watch |
| Supabase (Postgres) | `SUPABASE_DB_URL` | `strategy_settings` (JSONB per strategy+symbol, L209-216), `market_zones`, `signal_log`, srv2 state (`get_srv2_state` / `save_srv2_state` L945-987), upstox token, broker accounts, kill switch / pause / signal_symbols / live_confirm rows (special strategy keys) | dashboard, bots |
| Local files | `data/` (`PAPER_DATA_DIR`) | `paper_pause.json`, `paper_token_alert.json`, `paper_local.yaml` (instrument override), `engine_entry_<bot>_<SYM>.lock`, `one_bot_before.json`, heartbeats | paper/*, one_bot |

---------------------------------------------------------------------------------------------------------------------------------------
## 2. Signal logic - module chain (functions only)

### 2.1 Engine path (live path for signal_source = engine)
1. `scripts/engine_signal_run.py` - `signal_symbols()` (dashboard `__signal_symbols__`, default NIFTY / BANKNIFTY), `_settings(sym)` -> `engine_signal.engine3_settings` (L565; reads `15m_dynamic_sr` row keys starting `engine3_` + window keys), token check `engine_signal.token_check` -> `engine3_live.profile_check` (GET /v2/user/profile).
2. `engine_signal.run3(symbol, token, feed, path, now, s, dry_run)` L579-628 -> `L.UpstoxFeed`, `prev_trigger_bar`, `last_stored` (catch-up), then `engine3_live.compute`; rows via `engine3_live.row_from_v22` L1431; store window `in_window` / `window_bar` (L170-189, `engine_first_bar_end` 09:30, `engine_last_bar_end` 15:00); `keep_original` + `save`. Errors -> `save_error` "error" row + `alert_error` (fail-closed).
3. `engine3_live.compute(symbol, feed, now, s, since, prev_bar)` L1696: `v22_settings(s)` L960 (swing scale, `METHOD_SWITCHES` L856, pivot N, model C) -> `build_inputs` L652 (m15, daily, ltf5, fut5, note) -> `bar_revision` L764 -> `load_m1` L1025 -> `h1_history_of` L1066 -> `evaluate` L1117 -> `_evaluate` L1287 -> `decision3.engine.V22(m15, df1m, daily, sealed=, s=, ltf=, futures=, h1_history=)` inside `fold_cache` -> `decide_live(V, since)` L1155 (`V.decide5(j)` per 5M candle, or `V.decide(last)` for 15M) -> `attach_next_areas` L1219 (display only).
4. Output row columns (`engine_signals`): symbol, bar_ts, computed_at, decision ("setup" / "wait" / "error"), gate, direction (+1/-1), level_lo, level_hi, entry, invalidation, target, grade, reason, payload (JSON, capped `PAYLOAD_MAX` 20000 by `fit_payload` L1663). Payload keys used downstream: `entries` (list per model: model, name, direction, side, object, visit_id, trigger_ts, trigger_tf, trigger, entry_ref, invalidation, evidence, evidence_list, label, area{id,tf,role,lo,hi,state,object,broken_at,line}, cluster, refined_base, next_area, room, family, sub_model, story, model_c, pa_evidence), `reader`, `level`, `watch_list`, `trend_used` / `daily_trend` / `weekly_trend` / `daily_phase`, `commitment_form`, `bar_ohlc`, `bar_revision`, `m1`, `h1_history`, `volume_note` (`engine3_live.compact_entries` L1528, `ENTRY_KEYS` L1485, `AREA_KEYS` L1487).
5. The decision3 package itself (40 files, 21,436 lines) is the method; already copied as is to atp-private `atp_private/trade_engine/decision3/` (engine-snapshot-v2). Not restated here.

### 2.2 Engine signal -> entry (bot side)
`srv2_momentum_reversal_strategy.process_symbol` L232 -> `settings = cloud_db.get_strategy_settings("15m_dynamic_sr", symbol)` -> `symbol_enabled` check -> `paper.bot_hooks.pre_cycle("srv2_momentum_reversal", token, symbol, settings, lot_size, source="srv2_momentum_reversal")` (bot_hooks L60-100) -> `paper.engine_entry.process` L168 (entry_lock) -> `_process` L201:
- `ES.pending_entries(bot, symbol, settings, now, path, fresh_min=card_fresh_min(bot))` (engine_signal L769): fresh rows (`engine_max_age_min`), unconsumed (visit_id, model), stale marking (`card_fresh_min`, `engine_entry_seen`).
- with `entries` -> `_process_models` L491 -> `_one_entry` L516 per entry: model switches (`model_on` L288, `model_c_on` L302), cutoff, direction switches, stale, `has_open(symbol, source)`, `zone_full` L370 (`max_hits_per_zone` via `ES.zone_entries_today`), lots/naked from settings, `entry_level` L385, `fetch_chain`, `ES.mark_seen`, `vision.gate.entry_gate(bot, symbol, "PAPER", direction, level, role, "15M", bar_ts, spot, lots, naked, tags=entry_gate_tags(...))`, re-check zone, `ES.claim_entry`, `open_paper` L54, `ES.set_entry_status`, `ES.consume_siblings`, `vision.gate.note_execution`.
- rows without `entries` (older engine) -> single-setup path `ES.pending_entry` L687 / `mark_consumed` L710 (same gate + `open_paper`).
- Tags builders (display / dedupe only): `engine_gate_tags` L93, `engine_htf` L112, `engine_reader` L123, `engine_areas` L134, `entry_gate_tags` L397, `trigger_tags` L452, `object_tags` L462, `model_c_tags` L481, `model_tag` L312 (`live_trades.entry_reason_tag` "ENGINE_E1".. / "ENGINE_C_A_E2").
- Inputs read by this path: settings keys listed in 3.2 (marked E); engine store; Vision settings; config.yaml `paper.entry_cutoff`; option chain spot.

### 2.3 Bot's own (legacy) signal path - still runs, entries blocked when signal_source = engine
`process_symbol` L232-733: `post_sl_cooldown_minutes` L114 / `is_in_cooldown` L106 (srv2 state) -> `vision.gate.forced_levels` -> `LGB.entry_mode` / `LGB.conf_gate_enabled` -> `cloud_db.get_market_zones` -> `_collect_touch_candidates` L150 -> `_fetch_todays_1m_candles` L192 -> optional `LGB.cycle_gate("srv2", ...)` with `_gate_area` L75 -> per candidate: `dynamic_sr_instant_trader.check_level_crossed`, `determine_direction_with_hysteresis` L81, `_gate.result`, direction switches, cutoff 14:45 constant, `check_instant_rsi_filter`, `check_pcr_gate`, `cloud_db.get_zone_hits_today`, `get_last_sl_tsl_exit_time`, `count_consecutive_touch_minutes`, `has_open_trade_from_source`, **`_PBH.own_signal_ok`** (engine => False => logged skip), `LGB.LR.lot_multiplier`, `vision.gate.entry_gate`, option chain, `select_credit_spread_itm` / `select_naked_option_itm`, `_yield_open_5m_positions` L212, `execute_trade_on_all_accounts` (if `broker_account_ids`) or `open_multi_leg_trade`; every candidate -> `cloud_db.save_signal_log`; `cloud_db.save_srv2_state`; `send_telegram_message`.
This path is the only one that can run LIVE / LIVE_PAPER (pre_cycle and engine_entry refuse non-PAPER, see 4).

---------------------------------------------------------------------------------------------------------------------------------------
## 3. Settings

### 3.1 Storage and editing (seen)
- Per symbol row in Supabase `strategy_settings` (strategy_name `15m_dynamic_sr`, symbol NIFTY / BANKNIFTY / SENSEX). Read with `cloud_db.get_strategy_settings` L1041 = `STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]` (cloud_db L464-~535) scaled by strike step (`_scale_strike_relative_defaults` L761, `STRIKE_STEP` NIFTY 50 / BANKNIFTY 100 / SENSEX 100) + `symbol_enabled` default (True only for NIFTY) + stored row (stored wins). DB down -> last good copy in memory, else defaults. A stored LIVE / LIVE_PAPER is downgraded to PAPER unless `live_confirm.effective_mode` finds a valid signed record (L1041-1056).
- Written by the dashboard page `page_bot_dynamic_sr_algo.py` (save block L1593-1729, JSONB merge `save_strategy_settings` L1586) and by `scripts/set_one_bot_mode.py` / `bots_common/one_bot.py` (symbol_enabled, signal_source, trading_mode only).
- Vision settings: local SQLite `vision.db` `vision_settings` row bot `srv2_momentum_reversal` (+ `_global`), defaults `vision/config.py` BOT_DEFAULTS L44-97 / GLOBAL_DEFAULTS L109-123; edited on `page_vision_human_eye.py` and Telegram `/vision`.
- Global rows in `strategy_settings`: `__signal_symbols__` (default NIFTY, BANKNIFTY), `__global_kill_switch__`, `__global_trading_pause__`, `__portfolio_risk_cap__`, `__vix_spike_halt__`, `__live_confirm__`, `__telegram_policy__`.
- File settings: `config.yaml paper:` (L94-104) + `data/paper_local.yaml` override (`paper/config.py`).

### 3.2 Keys of `15m_dynamic_sr` (name - type - code default - read where - path). Path: E = engine entry path, L = legacy bot path, X = exits, G = engine (decision3) run, D = display only
| Key | Type | Default (code) | Read at | Path |
|---|---|---|---|---|
| symbol_enabled | bool | NIFTY True, others False (cloud_db L1069) | srv2 L237, engine_entry.enter_now L679 | E/L |
| signal_source | own/engine/both | "engine" (cloud_db, engine_signal L32) | engine_signal.source_of L88 | E/L |
| trading_mode | PAPER/LIVE/LIVE_PAPER | "PAPER" | bot_hooks L28, engine_entry L203, srv2 L~549 | all |
| broker_account_ids | list | [] | srv2 L~550 | L (multi-account) |
| lots | int | 1 | engine_entry L246/L555, srv2 L255 | E/L |
| naked_lots | int | 1 (falls back to lots) | same | E/L |
| credit_spread_enabled / naked_enabled | bool | True / True | engine_entry L73,L80,L246 | E/L |
| itm_depth_points / hedge_width_points | float | 100 / 150 (scaled) | engine_entry L74-75 | E/L |
| naked_itm_depth_points, naked_hedge_enabled, naked_hedge_width_points | float/bool/float | 100 / False / 150 | engine_entry L81-83 | E/L |
| spread_target_pct_of_premium | float | 80 | engine_entry L72 (entry target), trading_engine srv2 branch | E/X |
| bullish_entry_enabled / bearish_entry_enabled | bool | True | engine_entry L237/L536 | E/L |
| max_hits_per_zone | int | 2 | engine_entry.max_hits L365 | E/L |
| engine_max_age_min | int | 30 (engine_signal DEFAULTS) | pending_entries L783 | E |
| engine3_model_e1_on..e4_on | bool | True | engine_entry.model_on L288 | E (signal switch) |
| engine3_model_c_on + sub keys, engine3_c_window, engine3_c_a_nature, engine3_c_projections | bool/str | OFF / decision3 settings defaults | engine_entry L302, engine3_live.model_c_settings L924 | E/G |
| engine3_use_1m, engine3_swing_k_d1/d2, engine3_daily_pivot_n, engine3_trigger_tf, method switches (engine3_zone_visit_rule, commit_volume_rule, line_rule, div_degree_rule, verdict_rule, entry_gate, daily_leg_read, entry_cluster_rule, daily_range_rule, range_state_rule, visit_end_rule) | bool/float/str | "" = method default; use_1m True | engine3_live L793-1022 | G |
| engine3_m15_days, daily_days, ltf_days, fut_days, cache_keep_days, bar_grace_min, history_cache, bar_final_grace_s, h1_history_days, store_chunks_per_cycle | int/bool | engine3_live DEFAULTS L34-44 (not on the dashboard save list) | engine3_live | G |
| engine_first_bar_end / engine_last_bar_end | "HH:MM" | 09:30 / 15:00 | engine_signal.in_window | G (operational) |
| approval_band_warn_pts / approval_band_warn_rule | float / str | 150 / "method" | bots_common.plain_text | D |
| preopen_charts / preopen_charts_send | bool / str | True / "album" | scripts/level_gate_preopen.py | D |
| area_alerts / area_alert_daily_cap | bool / int | not in cloud_db defaults (page default) | engine area alerts | D |
| level_memory_enabled | bool | True | level_memory.py | L |
| active_timeframes | list | ["15M"] | srv2 L285, bot_view L42 | L/D |
| entry_rsi_gate_enabled, rsi_support_max, rsi_resistance_min | bool/int | True / 40 / 60 | srv2 L273-279 | L |
| entry_pcr_gate_enabled, pcr_bullish_min, pcr_bearish_max | bool/float | True / 0.80 / 1.10 | srv2 L280, L428 | L |
| entry_mode, conf_rsi_gate_enabled, conf_pcr_gate_enabled, gate_rr_gate_enabled, gate_min_rr, gate_no_target_disarm_enabled, gate_max_armed_bars, confirm_tf_minutes, gate_wait_next_candle, gate_area_pad_pct | mixed | in bots_common/level_gate_bot.py (not cloud_db defaults) | srv2 L284-287, LGB | L |
| entry_min_hold_gate_enabled / _minutes / _first_trade_only | bool/int/bool | False / 3 / True | srv2 L296-298 | L |
| sl_tsl_cooldown_minutes | int | 15 | srv2 L449 | L |
| post_sl_cooldown_enabled / _minutes | bool/int | False / 30 | srv2 L114 | L |
| spread_sl_spot_pct, spread_sl_premium_points, spread_tsl_spot_pct, spread_tsl_premium_points | float | 0.15 / 10 / 0.30 / 25 | trading_engine srv2 branch (~L2127-2131) | X |
| spread_trailing_sl_enabled / spread_trailing_distance_points | bool/float | False / 8 | same | X |
| carry_forward_min_profit_pct | float | 30 | trading_engine L1628, ~L2185 | X |
| naked_sl_spot_pct, naked_sl_premium_points, naked_tsl_spot_pct, naked_tsl_premium_points, naked_target_spot_pct, naked_target_premium_points | float | 0.05 / 10 / 0.10 / 20 / 0.40 / 50 | trading_engine ~L2090-2095 | X |
| naked_trailing_sl_enabled / naked_trailing_distance_points | bool/float | False / 15 | ~L2104-2105 | X |
| naked_eod_hour / naked_eod_minute | int | 15 / 0 | ~L2118, L1627 | X |
| broker_side_sl_enabled | bool | False | trading_engine._resolve_broker_side_sl_premium_points L765 | X (LIVE) |
Also read by the 5M bot from this row: none found; the 15M reads the 5M row (`1m_instant`: `defer_to_15m_enabled`, its trading_mode) in `_yield_open_5m_positions` L219 (legacy path).

Vision settings that act on this bot (bot `srv2_momentum_reversal`): vision_mode, approval_required (True), symbols, approve_window_min (10), card_fresh_min (5), exec_window_min (5), max_drift_mr (0.5), shadow_cooldown_min (30), reuse_window_min (15), vision_timeout_sec (20), second_audit_below_conf (0.6), vision_fail_action, timeout_action, vision_wait_for_bar_close, vision_engine_audit ("engine"), vision_engine_prompt ("trader_v1"), card_before_vision (True), approval_card_layout, chart flags; global: vision_daily_budget_usd (5.0), vision_monthly_budget_usd (150.0), signals_daily_reserve_usd, v4 caps.

config.yaml `paper:` - instruments NIFTY enabled true / BANKNIFTY false / SENSEX false (file default; VPS override `paper_local.yaml` written by one_bot), update_every_min 30, fill_details false, status_updates false, status_digest_times, near_alert_pct 80, entry_cutoff "14:45".

### 3.3 Owner live values vs code defaults
- The current live values were NOT readable here (Supabase and the VPS `vision.db` are not reachable from this session). Code defaults above are code defaults only.
- One stored VPS snapshot exists: /home/user/trade-data/review/diagnosis_today/2026-10-21/vps_run3/meta/settings.json (a diagnosis dump of that run, not current). It shows for `15m_dynamic_sr/NIFTY` e.g. signal_source engine, trading_mode PAPER, lots 50, naked_lots 15, itm_depth_points -50, hedge_width_points 150, max_hits_per_zone 2, entry_pcr_gate_enabled false, sl_tsl_cooldown_minutes 0, spread_sl_spot_pct 0.1, spread_sl_premium_points 5, spread_tsl_spot_pct 0.2, spread_tsl_premium_points 10, spread_target_pct_of_premium 80, naked_target_spot_pct 0.5, naked_target_premium_points 60; BANKNIFTY differs (hedge 500, itm 200, naked off, target 60). Vision: vision_mode veto_then_confirm, approval_required true, symbols NIFTY/BANKNIFTY. signal_symbols NIFTY/BANKNIFTY. DECISIONS 21 (22 Oct) later set max_hits_per_zone = 4, so this snapshot is known to be out of date on at least that key. A port must read the live rows (54 stored keys per symbol in that dump) at cut-over.

---------------------------------------------------------------------------------------------------------------------------------------
## 4. Modes, kill switches, guards

### 4.1 Mode values (seen)
- `trading_mode`: PAPER / LIVE / LIVE_PAPER (LIVE_PAPER = recursive LIVE + PAPER shadow inside `open_multi_leg_trade`, trading_engine L928-940).
- `signal_source`: own / engine / both (`engine_signal.SOURCES`).
- `entry_mode` (legacy path): touch / confirmation (`LGB.entry_mode`; dashboard saves "touch" for LIVE, page L1621).
- Vision `vision_mode`: off / shadow / notify / auto_veto / human_confirm / veto_then_confirm; `approval_required` True forces a human mode in every trading_mode (`vision/config.effective_mode` L196).
- `engine3_trigger_tf`: 5M (default) / 15M (what-if); env `ENGINE3_TRIGGER_TF` overrides (rollback line).

### 4.2 Where the mode changes behaviour (seen)
- `cloud_db.get_strategy_settings` L1041: stored LIVE without a valid signed `live_confirm` record => PAPER + `live_unconfirmed`.
- `paper/bot_hooks.pre_cycle` L60: non-PAPER => no instrument / token / lot-size checks, lot size 65 legacy, **no engine path**.
- `paper/engine_entry._process` L203 and `enter_now` L677: non-PAPER => "engine signals are PAPER only", no entry.
- `bot_hooks.own_signal_ok` L97: non-PAPER => True (legacy path may enter LIVE).
- `vision/gate._fail_skip` L78: a gate error never ENTERs outside PAPER; `vision/config.save` L241: V1 modes refused for a non-PAPER bot.
- `trading_engine.open_multi_leg_trade` L882-1237: LIVE-only margin check, adapter fill-verification gate (`_adapter_live_unverified`), `entry_inflight.mark`, broker-side SL, real orders; PAPER => LTP fills (`upstox_api.execute_order_leg_set` L1034-1051), trade_id prefix "PAPER_".
- `bots_common/one_bot.py` + `scripts/set_one_bot_mode.py`: never touches a LIVE combo (`_safe_mode` L166, `_steps` L244).
- Dashboard: LIVE saved only with the confirmation tick (page L1617) and `live_confirm.render`.

### 4.3 Kill switches / guards on a new entry (seen; exits are never blocked by any of them)
Engine path, in order: Supabase `symbol_enabled`; config.yaml / paper_local `paper.instruments.<SYM>.enabled`; Upstox token present (else one Telegram per day, `token_error`); lot size resolvable; `paper_pause.json` (Telegram /pause, unreadable => paused); `signal_symbols`; engine store freshness (`engine_max_age_min`) and N18 stale (`card_fresh_min`); model switches; `paper.entry_cutoff` 14:45; bullish/bearish switches; one open position per (symbol, source) (`database.has_open_trade_from_source`); `max_hits_per_zone` (checked before and after the tick); per (visit, model) idempotency (`claim_entry`); fcntl `entry_lock` per (bot, symbol); Vision gate (symbols list, approval, human tick only from `telegram:`, drift guard `max_drift_mr`, exec window, limit entry); inside `open_multi_leg_trade` (PAPER too): global trading pause, global kill switch, MCX kill switch (MCX only), portfolio open-risk cap, India VIX spike halt (bullish). Engine side fail-closed: error rows (data missing, FUT volume missing for NIFTY/BANKNIFTY, bar late, token rejected) => no setup + throttled Telegram.
Legacy path adds: post-SL cooldown, RSI / PCR gates, confirmation gate, SL/TSL cooldown on the level, min-hold, 5M yield, 14:45 constant, ProcessLock.

---------------------------------------------------------------------------------------------------------------------------------------
## 5. Vision -> Telegram -> entry flow (engine path)

1. **Signal submit**: `_one_entry` -> `vision.gate.entry_gate` L53 -> `_gate` L242: loads Vision settings, `find_open_decision` (per model + visit); none => `vision.hook._submit` inserts a QUEUED `vision_signals` row (setup_json carries the tags) and returns HOLD ("waiting for Vision / your decision").
2. **Worker** `vision/worker.py` `run_once` L1234 / `process_row` L1060: waits for the setup bar close (`bar_wait` L930), fetches 1m + daily (`default_fetch` L46) and FUT volume (`chart_volume` L100), renders the chart `vision/chart.render` L553 (plotly + kaleido PNG; `build_figure` L322, method bands / objects / evidence lines from tags), saves the image (`vision/images.save_exclusive`, `VISION_IMAGE_DIR`), early card first when `card_before_vision` (`early_card` L330).
3. **Vision call**: provider Anthropic (`vision/signal_audit.make_client` L574, `anthropic.Anthropic`, `client.messages.create` L622). Engine rows use `vision/engine_audit.py` (SYSTEM_PROMPT L68-134, `PROMPT_VERSION` "engine_check_v5", trader prompt `TRADER_VERSION` "trader_v2", METHOD_BLOCK L137; method pack `vision/method_pack.py`); level-bot rows use `vision/signal_audit.py` (SYSTEM_PROMPT L88-181, `PROMPT_VERSION` "signal_check_v3", `build_request` L373, prompt caching). Model name only from env `VISION_SIGNAL_MODEL` (+ `VISION_SIGNAL_EFFORT`, `VISION_SIGNAL_THINKING`, `VISION_SIGNAL_MAX_TOKENS`). Budget: `_budget_ok` L288 (daily / monthly from `vision_usage`, `SA.estimate_usd`), one warning per day; usage rows `VS.add_usage`. Reuse of a recent same-setup verdict (`find_reusable`, `reuse_window_min`).
4. **Decision**: `vision/decide.decide` -> `worker.v1_status` L378: human modes => PENDING_HUMAN with `deadline = signal time + approve_window_min` (`decide_by` L404, min 1 minute after the card); no approver configured => the no-reply rule at once.
5. **Telegram message**: `worker.v1_notify` L789 / `engine_caption` L574 / `card_summary.py` / `engine_card.py`; send via `notifications.send_telegram_photo` / `send_telegram_message` and `vision/tg.py` (buttons). Buttons `vision/approval.buttons` L46: ✅ approve, ❌ reject, ✏️ modify (entry only), 📎 details, 📝 correction; reject-reason buttons. Callback data `v1|signal_id|A/R|HMAC(VISION_CALLBACK_SECRET)` (`vision/decide.parse_callback`). Cards of the same visit are joined (`join_card` L767) and decided together (`telegram_bot.apply_to_members` L157).
6. **Callback**: `vision/telegram_bot.handle_callback` L61: approver check (`TELEGRAM_APPROVER_IDS`, both chat.id and from.id), HMAC, status must be PENDING_HUMAN and before the deadline, conditional transition to APPROVED / REJECTED (`decided_by = telegram:<id>`), outcome line appended to the card (`VN.post`, card never erased). On ✅ of an engine row: `_engine_enter_now` L140 -> `paper.engine_entry.enter_now` L664 runs the bot's engine cycle at once (same lock as cron). Restart: open PENDING_HUMAN => EXPIRED (`expire_on_restart` L36).
7. **Expiry (human_confirm)**: deadline passed => `gate.resolve_due` L159 applies `timeout_status` (REJECTED for human_confirm => no entry); QUEUED/RUNNING older than approve window => "unavailable, no reply" rule; APPROVED/REJECTED not executed within `exec_window_min` => EXPIRED + would-have record (`shadow_unreached` L219); APPROVED not by a human => SHADOWED, no entry; stale engine entries (N18) never get a card.
8. **Entry**: next `_gate` call finds APPROVED => drift guard (`VD.drift_guard`, `max_drift_mr`) => EXECUTED + `Gate("ENTER", dashboard lots)`; Vision never changes size (M56 V1). Then `open_paper` L54: `select_credit_spread_itm` (strategy.py) and/or `select_naked_option_itm`, `trading_engine.open_multi_leg_trade(..., trading_mode="PAPER", sl_pct_of_credit=100, target_pct_of_max_profit=spread_target_pct_of_premium (spread) / 100 (naked), source="srv2_momentum_reversal", entry_timeframe="ENGINE", entry_level_price=level, entry_reason_tag=model tag)`. PAPER fill = current LTP per leg. Row in `live_trades`; journal via `paper/journal.py` / `paper/watch.py`; fill line to Telegram ("⚡ PAPER entry ·" on the card).
9. **Exits**: `trade_monitor.run_monitor_cycle` -> `trading_engine.manage_open_trades` L1658, srv2 branch (~L2076-2195), settings re-read at exit time from `15m_dynamic_sr`: spread SL (spot % / premium points), TSL activation then locked, optional trailing, PREMIUM_TARGET (stored target level), NEXT_LEVEL_EXIT (`cloud_db.get_next_level_in_direction` with `(entry_timeframe,)`), carry-forward check at 15:10 (`carry_forward_min_profit_pct`); naked: SL / TSL / target by spot % / points, trailing, EOD at naked_eod_hour:minute. Manual override EOD rules `_manual_override_eod_exit` L1603. Telegram `/exit <id>` closes a PAPER trade (`close_trade_manually`). Exit price fallback `exit_price_fallback.py`; carry guard `carry_guard.py`.
   - Observation (seen, not a finding about intent): engine positions are opened with `entry_timeframe="ENGINE"`, so the next-level search asks for zone types `DYNAMIC_SR_SUPPORT_ENGINE` / `DYNAMIC_SR_RESISTANCE_ENGINE` (cloud_db L1659-1662); no writer of such zone types was found in the repo (grep `_ENGINE`), so for engine positions NEXT_LEVEL_EXIT finds no level. The port must keep this behaviour as is (AS IS) or the owner decides.
10. **Logging**: `live_trades` / `order_log` (SQLite), `paper_journal` + `paper_would_have`, `vision_signals` + `vision_events` (status trail), `engine_entry_consumed` statuses (SKIPPED_* / ENTERING / EXECUTED / OPEN_FAILED / NOT_ENTERED_*), Supabase `signal_log` (legacy path only), EOD summary `scripts/paper_daily_summary.py` with `engine_entry.models_summary_text` L649.

---------------------------------------------------------------------------------------------------------------------------------------
## 6. Dashboard / bot_view

- `page_bot_dynamic_sr_algo.py` (1729, Streamlit) - strategy + symbol pickers; banners: LIVE status, VIX halt alert; panels: Kill Switch (L80), Portfolio risk cap (L212), VIX spike halt (L271), Signal symbols (L326, save triggers `one_bot.apply_signal_symbols` L347); tabs (L487): Entry Gate, Exit Gate, Mode & Broker, Today's areas (gate) (`_render_level_gate_today` L397). 15M-relevant expanders: touch timeframe (active_timeframes), SL/TSL cooldown, post-SL cooldown, min level-hold, max trades on same zone, strike & size (credit spread), entry mode (confirmation gate keys), RSI gate, bullish / bearish entry, PCR gate, long with hedge (naked), SL / TSL / target (spread and naked), trailing SL, broker-side SL, Signal source block (L1434: signal_source, area alerts + cap, engine_max_age_min, engine3_use_1m, band warn pts / rule, pre-open charts + send mode, E1-E4 model switches, model C + sub-ways + c_window / c_a_nature / c_projections, swing scale d1/d2, daily pivot N, method switch fallbacks), trading mode + LIVE confirmation + broker accounts. One Save button (L1593) writes the keys listed in 3.2.
- `bot_view.py` (323, UI-free helpers used by `page_dashboard.py` L1244 "Bot view" select): for "15M SRv2" shows the bot's ACTIVE `market_zones` levels for `active_timeframes` (`zone_suffixes` L36, `level_lines` L77) with today's hits (max-hits faded), RSI threshold lines from rsi_support_max / rsi_resistance_min (`rsi_threshold_values` L50), RSI gate status line (`rsi_gate_line` L186); no Supertrend for this bot; optional overlays (rejection markers, legs, RSI divergence, trendlines). Display only. It shows the legacy level view, not the engine areas.
- `page_vision_human_eye.py` (306): Vision settings per bot, budget, signal list.
- Telegram commands (`vision/telegram_bot.handle_command` L210, `paper/commands.py`): /pending /today /vision /status /positions /pause /resume /paper /exit /correct /help.

---------------------------------------------------------------------------------------------------------------------------------------
## 7. External dependencies

- Python packages (requirements.txt): pandas~=3.0, numpy~=2.4, plotly~=7.0 + kaleido (Vision PNG), matplotlib~=3.11 (decision3 review charts), anthropic~=1.11 + brotli>=1.2, requests, psycopg2-binary (Supabase), pyyaml, pytz, streamlit (+ streamlit-autorefresh), Pillow, websocket-client (stream monitor), cryptography (broker credentials), google-api-python-client / google-auth (DB backup to Drive), pyarrow, flask (token webhook), pyotp.
- Services: Upstox REST (market data, option chain, expiries, instrument master, profile, orders), Upstox WebSocket feed (optional), Supabase Postgres, Telegram Bot API (send + getUpdates long-poll), Anthropic Messages API, Google Drive (backup), cloudflared + `upstox_token_webhook.py` (daily token), healthcheck ping.
- Secret / env NAMES only: SUPABASE_DB_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_APPROVER_IDS, VISION_CALLBACK_SECRET, ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN, LIVE_CONFIRM_SECRET, UPSTOX_CLIENT_ID, UPSTOX_CLIENT_SECRET, HEALTHCHECK_PING_URL; data/notification_config.json keys (supabase_db_url, live_confirm_secret). Non-secret env: VISION_SIGNAL_MODEL, VISION_LEVEL_MODEL, VISION_SIGNAL_EFFORT, VISION_*_THINKING, VISION_*_MAX_TOKENS, VISION_DB_PATH, VISION_IMAGE_DIR, ENGINE_SIGNAL_DB, ENGINE_SIGNAL_ENGINE, ENGINE_SIGNAL_LOCK(_PATH), ENGINE_TOKEN_CHECK, ENGINE_PROFILE_CHECK_EVERY_MIN, ENGINE3_TRIGGER_TF, ENGINE3_CACHE_DIR, PAPER_DATA_DIR, PAPER_CONFIG, PAPER_LOCAL_CONFIG, PAPER_JOURNAL_DB, EXIT_LTP_MAX_AGE_SEC, TRADE_CALENDAR_GATE, TRADE_DATA_DIR.

---------------------------------------------------------------------------------------------------------------------------------------
## 8. File list with line counts (what would move)

Existing classification: Trade `docs/reader/EXPORT_MANIFEST.md` L203+ ("Engine snapshot", static import closure of `engine_signal.py`, `engine3_live.py`, `scripts/engine_resident.py`, `paper/engine_entry.py`, `vision/engine_audit.py`, `vision/signal_audit.py`, `bots_common/level_gate_bot.py`): PORT 112 files / 38,010 lines, ATP-GENERIC 55 / 22,655, TRADE-ONLY 15 / 5,044 (counts recomputed at HEAD with wc). The PORT set is already in atp-private `atp_private/trade_engine/` (engine-snapshot-v2 = this HEAD, 113 modules incl. provider). Full per-file lists: scratchpad `cls_PORT.txt`, `cls_ATP-GENERIC.txt`, `cls_TRADE-ONLY.txt`.

### 8.1 Pure engine logic (PORT; already in atp-private)
decision3/ 40 files 21,436 · vision/ (PORT part: checklist 283, context 379, engine_audit 830, engine_card 364, engine_measure 150, gap_context 215, method_block 19, method_pack 145, v4 159, __init__ 9) 2,553 · elliott/ 10 files 2,140 · engine3_live.py 1,721 · bots_common (level_gate_bot 326, level_reaction 636, plain_text 237, __init__ 1) 1,200 · opportunity_engine/ 7 files 1,146 · engine_signal.py 920 · pivots/ 5 files 799 · rsi2/ 3 files 745 · swings2/ 5 files 712 · price_action/ 3 files 707 · market_state/ 2 files 656 · backtest_review (2 PORT files) 655 · legs2/ 5 files 558 · facts/ 2 files 534 · verify_opportunity_data_availability.py 430 · chart_reader/ 3 files 400 · patterns2/ 5 files 398 · vision_led (2) 258 · instruments.py 42. Plus KB / method pack (docs/knowledge/*, scripts/build_method_pack.py) and decision3/data/*.json.

### 8.2 IO glue (ATP-GENERIC per the manifest, plus the bot's own scripts not in that closure)
Bot / signal glue: srv2_momentum_reversal_strategy.py 783 · paper/engine_entry.py 697 · paper/bot_hooks.py 104 · paper/config.py 68 · paper/lots.py 87 · paper/pause.py 44 · paper/journal.py 116 · paper/watch.py 725 · paper/commands.py 184 · paper/manual.py 527 · paper/card_quote.py 44 · paper/__init__.py 2 · scripts/engine_resident.py 180 · scripts/engine_signal_run.py 336 · scripts/level_gate_preopen.py 975 · scripts/paper_daily_summary.py 387 · scripts/install_engine_schedule.sh 140 · scripts/set_one_bot_mode.py 88 · scripts/paper_status.py 197 · bots_common/one_bot.py 538 · bots_common/gate_alert.py 152 · bots_common/error_once.py 86 · dynamic_sr_instant_trader.py 1,629 (4 helpers used) · process_lock.py 49.
Vision / Telegram: vision/gate.py 395 · hook.py 51 · store.py 513 · config.py 345 · decide.py 136 · worker.py 1,329 · chart.py 834 · images.py 77 · signal_audit.py 690 · card_summary.py 767 · notify.py 242 · tg.py 223 · approval.py 475 · outcome.py 252 · telegram_bot.py 328 · notifications.py 328 · notify_policy.py 69.
Orders / exits / storage: trading_engine.py 2,918 · trade_monitor.py 257 · position_stream_monitor.py 218 · engine_service.py 146 (helpers for trade_monitor) · database.py 2,122 · cloud_db.py 2,728 · strategy.py 340 · upstox_api.py 1,332 · order_safety.py 777 · order_execution.py 187 · entry_inflight.py 236 · exit_price_fallback.py 84 · carry_guard.py 115 · charges.py 450 · live_confirm.py 214 · config.py 204 · log_setup.py 39 · monitor_timing.py 57 · broker_adapter.py 83 · broker_factory.py 115 · upstox_broker_adapter.py 54 (+ fyers / shoonya / stocko adapters and apis, LIVE multi-account only) · crypto_utils.py 89 · oi_analysis.py 838 (PCR, legacy path) · signals.py 1,110 (resample_to_1h, RSI) · config.yaml 107 (paper section L94-104).

### 8.3 UI
page_bot_dynamic_sr_algo.py 1,729 · bot_view.py 323 · page_dashboard.py 2,533 (bot view part ~L1244+) · page_vision_human_eye.py 306 · app.py 428 · safe_widgets.py 49 · ui_headers.py 51 · htf_alignment.py 106 (bot_view import).

---------------------------------------------------------------------------------------------------------------------------------------
## 9. Owner's own rules for this bot (docs/owner-orders, by grep; no new rules added)
- DECISIONS 4, 6, 7, 8: PAPER only; E1-E4 live in PAPER, independent, each once per visit; the engine only generates signals, execution = the existing dashboard settings, no new execution settings; Vision = human_confirm, never enters without the owner's tick, no reply => card expires, no entry.
- DECISIONS 21: max_hits_per_zone = 4, stays a dashboard setting. DECISIONS 37: trigger read on 5M for every model.
- INBOX T-6 (L238-270): this bot's real exits are the trading_engine srv2 branch from the `15m_dynamic_sr` settings; display fix only, no exit-logic change.
- `bots_common/one_bot.py` docstring (owner "one bot"): only 15M SRv2 ON, signal_source = engine, PAPER, signal symbols only; other entry bots OFF.
- INBOX L1645 (N11): the word "SRv2" and similar jargon must not appear to the user (UI wording).

## 10. Not found / not readable
- Live Supabase settings, live crontab, live vision.db: not readable here (only the dated 21 Oct snapshot in trade-data).
- No writer of `*_ENGINE` zone types (affects NEXT_LEVEL_EXIT for engine positions, 5.9).
- No LIVE path for engine signals (refused in three places); LIVE exists only on the legacy own-signal path.
- `area_alerts`, `area_alert_daily_cap`, `entry_mode` and the `gate_*` / `conf_*` keys have no defaults in `cloud_db.STRATEGY_SETTINGS_DEFAULTS["15m_dynamic_sr"]`; their defaults live in the page / level_gate_bot.


---

# Part B

# Audit: porting Trade bot "15M SRv2" (`15m_dynamic_sr`) into ATP — read-only

Refs read (fetched 18 Nov): ATP `origin/main` = ffa9f73e (#1100); atp-private `origin/main` = a306c7c (#17, 5 Nov).
NOTE: the local atp-private `origin/main` was stale (7b117b5, 2 Nov) until a full fetch; the remote main has 6 more PRs
(#12-#17: chart_reader, prompts v2/v3, preopen, lake keys shim, hybrid). Everything below is on a306c7c.
Trade source (for sizing only, /home/user/trade working copy): `bots_common/one_bot.py` 538 lines,
`srv2_momentum_reversal_strategy.py` 783, `dynamic_sr_instant_trader.py` 1629, `bot_view.py` 323,
`page_bot_dynamic_sr_algo.py` 1729, `paper/engine_entry.py` 697, `paper/bot_hooks.py` 104, `vision/worker.py` 1329,
`vision/chart.py` 834, `vision/approval.py` 475, `vision/telegram_bot.py` 328, `vision/tg.py` 223,
`scripts/engine_signal_run.py` 336.

Fact to flag: in Trade code, strategy_key `15m_dynamic_sr` belongs to `srv2_momentum_reversal_strategy.py`
(srv2:235 `cloud_db.get_strategy_settings("15m_dynamic_sr", symbol)`; `paper/engine_entry.py:19`
`BOT_SETTINGS_KEY = {"srv2_momentum_reversal": "15m_dynamic_sr"}`; `one_bot.py:30 ON_KEY = "15m_dynamic_sr"`).
`dynamic_sr_instant_trader.py` is the `1m_instant` bot (`paper/manual.py:30`). HANDOVER_NOW.md:13 names
`dynamic_sr_instant_trader.py` for this port - that file is a different bot. The bot's settings live in Trade's
Supabase `strategy_settings` per symbol (cloud_db); the owner's real values are not in any repo (not known).

---------------------------------------------------------------------------------------------------------------------
## 1. atp-private: Trade engine snapshot

### Exists
- `atp_private/trade_engine/` = Trade tag `engine-snapshot-v2`, commit 813358b, 113+ modules AS IS, import paths only
  (`IMPORT_MANIFEST.json`; `README.md:1-30`). Rewrite rule: `import decision3` => `import atp_private.trade_engine.decision3
  as decision3` (`tools/trade_sync/atp_import_rewrite.py`; driver `tools/trade_sync/export_to_atp_private.sh`; closure
  `tools/trade_sync/engine_closure.py`).
- Packages: backtest_review, bots_common (level_gate_bot, level_reaction, plain_text, preopen_crux), chart_reader
  (evidence, measures), decision3 (42 files incl. engine, entry_models, entry_models5, levels, method, settings,
  trigger_frame, charts, draw_render, preopen_chart), elliott, facts, legs2, market_state, opportunity_engine,
  patterns2, pivots, price_action, rsi2, swings2, vision (checklist, engine_card, engine_audit, method_pack, v4, ...),
  vision_led, scripts (build_method_pack, level_gate_preopen), top-level `engine3_live.py`, `engine_signal.py`,
  `instruments.py`, `provider.py`.
- `engine_signal.py` present (920 lines): `run3`, `pending_entries`, `own_allowed`, `mark_consumed`, `engine3_settings`
  (`ENGINE3_SETTINGS_KEY = "15m_dynamic_sr"`, line 562).
- `bots_common/level_gate_bot.py` present (`CONFIRM_TF = {..., "srv2": 15, ...}` line 20).
- Signal-engine shim `atp_private/trade_engine/provider.py` (`get_provider()`; `Provider.read` runs engine3_live's
  live path `v22_settings`/`build_inputs`/`load_m1`/`h1_history_of`/`evaluate` on a `RequestFeed` of ATP bars; maps to
  ATP interface 1; `request.settings` -> `L.v22_settings(s)` at provider.py ~200-206).
- Adapters for left-out Trade modules: `atp_private/adapters/__init__.py` (`install()`), `adapters/trade_config.py`
  (IST clock, NSE calendar from `EngineRequest.calendar`).
- Other ATP-facing entry points: `atp_private/chart_analyze` (Analyze a chart + hybrid), `atp_private/chart_reader`
  (book reader, M86), `atp_private/preopen` (pre-open Daily/1H/15M charts, `build(request, official_close)`),
  `atp_private/method_pack` (`vision_checklist()`, `vision_validate()`), `atp_private/parity` (layer runner),
  `atp_private/shadow/diff.py` (Trade vs ATP daily signal diff).
- CI: `.github/workflows/ci.yml` - checks out ATP at `ATP_VERSION` (fdbc2239...), installs ATP
  `backend/requirements.txt` + `.[test]`, `pytest -q -rfEs` over `tests/` (parity layers 1-6, golden, answer key v4,
  trigger_5m, real days, shim, preopen, chart_reader, shadow diff, calendar) and `atp_private/trade_engine/tests`
  (57 copied Trade tests). DECISIONS 2026-11-01: while billing blocks CI, PRs merge on local test evidence.
- Status docs: `docs/M79_WORKLIST.md` (W1-W10), `docs/M79_W7_W10_DESIGN.md` (T9 design + O-1).

### Partial
- `engine_signal.py` imports at call time modules that are NOT in the snapshot and have no adapter:
  `notifications` (lines 292, 339, 383, 441, 473, 526), `cloud_db` (570), `upstox_api` (138), `decision2` (121),
  `bots_common.error_once` (314, 549), `bots_common.gate_alert` (818), `scripts.decision_check` (123).
  `level_gate_bot.py` needs `paper.journal` (302), `upstox_api` (190, 232), `config` (adapter exists).
  So the engine READ path (provider shim) works; the bot-side functions of engine_signal (alerts, settings fetch,
  pending_entries' gate alert) fail if called without ATP adapters.
- Adapters README (`adapters/__init__.py:8-10`): only `config` installed; `cloud_db`, `upstox_api` "not yet ported".
- Shim maps cards without setup / step / evidence tokens and swings empty (WORKLIST status, 1 Nov: owner decision open).
- Chart rendering: `decision3/preopen_chart.py:11-14`, `decision3/charts.py`, `draw_render.py:284` use matplotlib;
  `pyproject.toml:18` lists matplotlib/plotly as TEST-only; ATP `backend/requirements.txt` has Pillow but NO matplotlib
  (atp-private README "Dependencies": a missing lib = an ATP PR). So any engine chart (Trade `vision/chart.py` uses
  `draw_plotly`) cannot render in ATP's image today.

### Missing (by design classified out of the snapshot, `engine_closure.py:20-41`)
- TRADE-ONLY (not copied): `srv2_momentum_reversal_strategy.py`, `dynamic_sr_instant_trader.py`, `bot_view.py`,
  `page_*` (incl. `page_bot_dynamic_sr_algo.py`), `strategies/`, `orchestrator.py`, `engine_service.py`.
- ATP-GENERIC (not copied; ATP must supply its own): `bots_common/one_bot.py`, `paper/` (engine_entry, bot_hooks,
  journal, watch), `vision/tg.py`, `vision/telegram_bot.py`, `vision/approval.py`, `vision/worker.py`,
  `vision/chart.py`, `vision/images.py`, `vision/notify.py`, `cloud_db.py`, `notifications.py`, `order_*`,
  `trading_engine.py`, `live_confirm.py`, `entry_inflight.py`, broker adapters.
- No dashboard-settings export (TRADE_PORT_MAP T9: "EXPORT_MANIFEST dashboard_settings gives the names; values are
  the owner's"). T9 build waits for owner O-1 (`M79_W7_W10_DESIGN.md:17-21, 64-66`).

---------------------------------------------------------------------------------------------------------------------
## 2. ATP boundary, runners, settings, PAPER/LIVE, orders, exits

### Exists
- Provider interface: `backend/app/engine_provider/contract.py` (`INTERFACE_VERSION = 1` :34; `EngineRequest` :128
  with `settings` = user's own engine settings; `Signal` :275 - model_id, entry_zone, invalidation (internal), card
  tokens; `EngineResult` :308; `TradeEngineProvider` Protocol :335).
- Loader: `backend/app/engine_provider/loader.py` (`MODULE = "atp_private.trade_engine"` :25; `load()` :84,
  `available()` :94, `reason()` :98, `describe()` :111, `set_for_tests()` :127). Same pattern:
  `app/chart_analyze/provider.py:27` (`atp_private.chart_analyze`), `app/chart_reader/loader.py:19`
  (`atp_private.chart_reader`), `app/workers/preopen_charts.py:42` (`atp_private.preopen`).
- Input frames: `engine_provider/frames.py` (calendar, bar rules, near-month FUT volume gaps), `sources.py` (lake +
  broker reads).
- Host install: `deploy/atp.sh:1070-1139` (read-only checkout at `ATP_PRIVATE_REF`, mounted on PYTHONPATH).
- Signal runner: `backend/app/workers/engine_runner.py` (M66 EN-3a, SIGNALS ONLY, header :1-40): flag
  `trade_engine` (:76, admin/owner, OFF default `controls.py:236`), settings row `platform_controls`
  `trade_engine_runner` (:79; `RunnerSettings` :219 incl. `engine_settings`, per-TF `windows`), writes
  `signal_history` (`strategy_id = "trade_engine"` :77) with dedupe in `runtime_counters`; spawned by
  `TradingWorker._spawn_engine_runner` (`trading_worker.py:2136`). Day export for shadow: `export_day` :428.
- Runner settings setter: CLI only `python -m app.workers.runner_settings show|set` (`workers/runner_settings.py:1-12`).
- Bots today: `strategy_deployments` (`db/models.py:601`; mode PAPER/LIVE :634, entry_mode, exit_rules, stop_source,
  target_rule, max_lots, option fields, management); evaluated in `TradingWorker._evaluate_deployment`
  (`trading_worker.py:2197`; strategy via `custom_strategies/resolver.py:90 resolve_strategy` = registry /
  `custom:` / `template:` ids); approval branch :2358 (`approval.required` -> `_propose_entry` :2457); else
  `execute_signal_for_user` (`execution/signal_execution.py:129`). Routes `/api/deployments`
  (`deployments/routes.py:67`, create :643). UI: `frontend/src/pages/DeploymentsPage.tsx`,
  `frontend/src/paperbot/PaperBotV2.tsx` (+ BotWhyV2, BotPositionsV2, ContractPreviewV2).
- PAPER/LIVE chain: ONE switch `live_trading` (`platform/live_switch.py:1-59`, `live_allowed` :42, `live_refusal`
  :50); `phase0_lock.py` derived lock + B1 owner-org only (:6-35; `locked` :104, `assert_paper` :146,
  `WORKER_NOT_EVALUATED` LIVE deployments skipped); `live_owner.py` (only `LIVE_OWNER_USER_ID`, `core/config.py:110`,
  default 1, may open LIVE; org grants :108-124). Layer 1 `platform.controls.entry_blocks`; layer 2 broker chokepoint
  `brokers/rate_budget.py:433-450` `RateLimitedBroker.place_order` (entry refused when locked; exits/modifies/cancels
  pass; GTT create :460). HANDOVER_NOW (15 Nov) says prod `live_trading ON (B1: owner org only)` - a doc statement,
  not read from the server here.
- Exits never blocked: ADR `docs/adr/0004-safety-rules-exits-never-blocked.md`; `trading/position_monitor.py:63, 194,
  602, 647, 795-814, 1199`; `rate_budget.py:446` (exits wait for a token, never refused); approval exits policy
  (`execution/approval.py:28-35`).
- Approval core: `execution/approval.py` (`propose_entry` :227, `gate_refusal` :149, re-quote, expiry, owner's
  Automation settings); intent queue `execution/core/dispatcher.py` (ADR-0014).

### Partial
- engine_runner produces signals only; "EN-3b adds the bot side" (`engine_runner.py:1`, :464) - EN-3b not on main.
- Approved entries are placed PAPER only: `approval.py:288` (`"mode": "PAPER", "requested_mode": ...`), :443, :456,
  :580. A LIVE deployment in approval mode cannot become a LIVE order through the approval path today.
- Shim's engine settings come from the admin runner row (`engine_settings`), not from a user-facing per-bot page.

### Missing
- An ATP deployment type for the engine signal flow (T9; `TRADE_TAKEOVER.md:144`; TRADE_PORT_MAP.md:269 "waiting").
  No strategy id `trade_engine` in the registry / deployments; frontend has no "Signal engine" bot or settings UI
  (grep `trade_engine` / "Signal engine" in frontend/src: none).
- Port of srv2's own order building (lots, strikes, SL/target from `15m_dynamic_sr` settings, credit spread / naked
  switches srv2:651/681, post-SL cooldown srv2:55) and of `one_bot.py` / `paper/engine_entry.py` - nowhere in ATP.
- The `15m_dynamic_sr` dashboard settings schema/values (Trade `page_bot_dynamic_sr_algo.py`) - no ATP model / page.

---------------------------------------------------------------------------------------------------------------------
## 3. Vision (BYOK background reviews)

### Exists
- `backend/app/ai/vision_audit.py` (885 lines; flow :1-36): `enqueue_for_proposal` :378 (after an ENTRY proposal),
  `enqueue_for_scan_alert` :423, daily review :504; `drain` run by worker (`_spawn_vision_drain`,
  `trading_worker.py:2177`); one call on the USER's own key (`byok`); answer parsed into 4 judgements; comment only
  (ADR-0006); Telegram delivery `send_photo` :545, `_deliver_telegram` :582 (linked private chat). Flags `vision_byok`
  (`flag_catalog.py:89` "ready"), `vision_byok_v3` (:90 "unfinished"). Prefs UI
  `frontend/src/settings/VisionReviewSwitchesV2.tsx`, `components/VisionByokCard.tsx`, `VisionReportPanel.tsx`.
  Migrations `e4c2a9b7d1f6_byok_v2_vision_reports.py`, `c9e1f3a5b7d2_byok_v3_vision_subjects.py`.
- Chart image: `backend/app/ai/chart_png.py` - stdlib PNG encoder (no matplotlib), bars + proposal levels; `render`
  :137. Bars from lake `lake_bars` (`vision_audit.py:313`).
- Hybrid AI card on ATP's rendered chart (M75 W-4, `tests/test_m75_w4_vision_card.py`).

### Partial
- Order differs from Trade: ATP raises the proposal (with its own Telegram buttons) first and the Vision report comes
  after as a separate photo; Trade's flow is signal chart -> Vision -> Telegram card with buttons (human_confirm).
- ATP's chart is its own simple PNG, not the engine's chart (Trade `vision/chart.py` / `draw_plotly`) - the engine
  chart needs matplotlib/plotly (see 1. Partial).

### Missing
- W7 public hook: `vision_audit.py` does not ask the private package for the Method Pack checklist
  (`method_pack.vision_checklist`/`vision_validate`); no `method_pack` reference in `backend/app`
  (`M79_W7_W10_DESIGN.md:5-11` "Next").

---------------------------------------------------------------------------------------------------------------------
## 4. Telegram

### Exists
- Org's own bot with inbound webhook: `backend/app/telegram_inbound/service.py` (891 lines; header :1-27),
  `routes.py` (`POST /api/telegram/webhook/{webhook_token}` :37, inbound settings :65-91; flag `telegram_inbound`).
  One-time nonce buttons (`p:<nonce>`, HMAC, expiry = proposal's) `keyboard_for` :288 (✅ Approve / ❌ Reject /
  ⏰ Snooze 1h); `decide_from_callback` :306; `send_proposal_buttons` :791 (used by `alerts/dispatcher.py:661`);
  buttons removed after decision (:844); `/exit` for PAPER. Message ids stored on `ai_actions`
  (`models.py:1634` telegram_chat_id/message_id). Migrations `c8d0e2f4a6b8_telegram_inbound.py`,
  `e9c1a3b5d7f9_pw4_proposal_telegram_message.py`.
- Per-user linking: `alerts/links.py` (`new_link_code` :42, `consume_start` :56, `linked_chat` :77),
  `alerts/links_routes.py` (`/api/alerts/telegram/link-code`, `/link`). Platform bot "Connect Telegram":
  `alerts/platform_bot.py` (`handle_update` :203), `platform_bot_routes.py`; UI `frontend/src/alerts/TelegramConnectV2.tsx`.
- Other senders: `daily_report/telegram.py`, `rhythm/deliver.py`, `option_chain/oi_alerts.py`, preopen charts
  (`preopen_charts.py:103`).

### Partial
- Telegram may decide an ENTRY proposal only when its mode is PAPER (`service.py:270-272`); LIVE proposals are
  "decided on the web with your authenticator, never over Telegram" (:283-285). Trade's flow allows Telegram ✅ for the
  bot's entry - conflicts with this standing ATP rule (owner decision).
- Buttons need the org's own bot with inbound on (`send_proposal_buttons`: `if not cfg.inbound_enabled: return False`);
  the platform bot (`platform_bot.handle_update` :203-240) handles only `/start` messages, no `callback_query` - a
  user on "Connect Telegram" gets no buttons.

### Missing
- Trade's ✏️ "change the entry only" and ❌ "reject with a reason" (TRADE_TAKEOVER.md:145-147) - no such callbacks.
- A chart photo WITH the decision buttons in one message (ATP sends text+buttons; photo separately).

---------------------------------------------------------------------------------------------------------------------
## 5. Chart image rendering in the ATP backend
- Exists: `app/ai/chart_png.py` (stdlib, Vision); `app/study/png.py:73 chart_png` (study snapshot PNG);
  `app/journal/entries.py:565 chart_png`; preopen charts drawn by the private package (`atp_private.preopen.build`).
- Partial/Missing: the private engine's charts (decision3 charts, preopen_chart, draw_render, Trade's
  `vision/chart.py`) need matplotlib (plotly for draw_plotly), absent from `backend/requirements.txt`; nothing in
  `backend/Dockerfile` adds it. So `atp_private.preopen` (and any engine chart for Vision/Telegram) will fail to import
  on the host until an ATP requirements PR adds it (not verified on the server).

---------------------------------------------------------------------------------------------------------------------
## 6. Existing docs on this port
- `docs/owner-orders/INBOX.md:431` (15 Nov, verbatim order: port 15M SRv2 AS IS with settings, button, PAPER+LIVE,
  Vision -> Telegram buttons -> entry, no change). `docs/HANDOVER_NOW.md:13` (same; "Audit first, then estimate, wait
  for owner ok"). Not yet in DECISIONS / ROADMAP as its own item (grep "SRv2|15m_dynamic_sr" in ROADMAP / DECISIONS /
  README: none; M79 row `ROADMAP.md:306` "in progress").
- `docs/TRADE_PORT_MAP.md:179` (srv2 = "missing: template"), :182 (level_gate_bot missing on main), :269 (T9 one-bot
  executor), :270 (T10 MCX), :271 (T11 level bots after T6).
- `docs/design/TRADE_TAKEOVER.md:41, 140-152` (section 9: T9 as a deployment type; Telegram ✅/✏️/❌; PAPER; Vision
  audit before approval).
- `docs/design/PRIVATE_PACKAGE.md` (boundary, install); atp-private `docs/M79_WORKLIST.md`,
  `docs/M79_W7_W10_DESIGN.md` (O-1 default: one deployment type "Signal engine (PAPER)", no build until owner yes).
- Open question archive: `docs/archive/OPEN_QUESTIONS_PROVISIONAL.md:1577` (M79Q-1 runner windows).

---------------------------------------------------------------------------------------------------------------------
## Conflicts with standing rules that need the owner's word (facts only)
1. LIVE via Telegram buttons: ATP rule = web + authenticator only (`telegram_inbound/service.py:283-285`); approval path
   executes PAPER only (`approval.py:288, 456, 580`). Order says "paper trade / live trade entry" from the buttons.
2. Trade srv2 settings carry SL / target / lots / strikes (user's own settings - allowed by CLAUDE.md §3) but some srv2
   rules (e.g. post-SL cooldown, approval band warn pts) are settings that must be ported as settings, not defaults.
3. Owner principle "build fully, same code path LIVE" vs ATP Phase 0 text "PAPER only" in engine_runner / flag text
   (`controls.py:236` "PAPER only, places no orders").
4. Which Trade file: `15m_dynamic_sr` = `srv2_momentum_reversal_strategy.py`, not `dynamic_sr_instant_trader.py`.
