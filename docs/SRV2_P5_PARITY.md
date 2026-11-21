# SRV2 P5 - parity of the 15M SRv2 port with Trade (what is proven, what is not, how to close it)

Owner order SRV2 (P5: "one Trade replay day: same signals, same gate calls, same legs, same exits; screenshots"); owner
"Pending job purn kr" (21 Nov). Facts only: each line names its test or its data.

## Proven

| Part | Proof | Result (21 Nov) |
|---|---|---|
| Engine signals (same signals) | M79 parity layers 1-6, golden days, real days (`tests/test_parity_layer1..6.py`, `test_parity_golden.py`, `test_parity_real_days.py`): this engine's rows byte-equal to Trade's own for the fixture days | green in CI (fixture store) |
| The bot code is Trade's | `test_srv2_glue.py::test_the_copied_glue_is_trades_code_with_only_the_imports_rewritten`, `::test_the_defaults_are_trades_own` with `TRADE_SRC` = Trade at `b085de1` | 2 passed |
| Entry rules (same gate calls) | `test_srv2_glue.py`: approved entry opens the spread + naked leg from the dashboard settings; once per visit and model; one position at a time; cutoff; model / direction switches; max hits per zone; a turned-down card opens nothing, a waiting card waits; PAPER only; signal symbols; an adapter ATP has not registered = no entry | 12 passed |
| Legs and exits (same legs, same exits) | `test_srv2_engine.py`: an approved entry opens PAPER positions in Trade's own store; the spread closes at its premium target and stops out on the spot / premium rule with Trade's own exit code; nothing moves = nothing closes; LIVE refused | 5 passed |
| Settings page | `test_srv2_page_fields.py` with `TRADE_SRC`: every field is a key Trade's page saves, every number bound equals its widget | 4 passed |

## Not proven, and why

A whole recorded day replayed end to end (same signals -> same cards -> same legs -> same exits, side by side with Trade) needs, for
that day: the candles (stored), the engine store (stored: trade-data `review/vps_days/2026-10-29_1654`, day 2026-10-26), AND the
option chains and prices the bot saw at each entry / exit, plus Trade's own `live_trades` / `order_log` rows for the bot. No stored
day has the chains, the prices or the bot's trade rows (the VPS export `scripts/export_day_proof.py` writes candles and the engine /
Vision stores only). A replay without them would have to invent the legs' prices: not a proof.

## How to close it (ATP OPEN_QUESTIONS SRV2-Q9, default)

After the deploy, run both bots in PAPER on the same market day: Trade's 15M SRv2 on the VPS (as today) and ATP's port (flag
`srv2_bot` ON, agent mode "Ask me first"). Both read live chains from the broker at the same moments. After the close, export both
stores (Trade: `live_trades` + `order_log` + the Vision store for the bot; ATP: the same files under `SRV2_DATA_DIR`) and compare
row by row: signals, cards, legs (strikes, quantities), exits (time, reason). Differences are listed with their cause. Screenshots:
ATP's settings card and positions list (ATP `docs/design/srv2-p2/COMPARE.html`), the Telegram card from each bot.
