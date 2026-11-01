# M79 W7-W10: design notes (discuss-then-build) and the shadow-run procedure

Private. Engine-snapshot-v2 (Trade 813358b). Nothing here goes to the public ATP repository.

## W7 (T8) Vision method checklist - built (private side), public hook next
- Built: `atp_private.method_pack.vision_checklist()` (the Method Pack as the cached system prefix, the snapshot's
  fixed V4 output schema and items 1-7) and `vision_validate()` (the snapshot's validator, fail-closed, against this
  pack's version). AS IS calls of `trade_engine/vision/checklist.py`; no API call.
- Next (public ATP, its own draft PR): `backend/app/ai/vision_audit.py` asks the private package for the checklist when
  it is installed (the loader pattern of `engine_provider/loader.py`), behind a new flag registered OFF; audit only
  (ADR-0006), mode human_confirm, the user's own key and budget. No paid call is made by a session.

## W8 (T9 / T10 / T11) - design first; adapters only
- Built: the engine config's calendar adapter (`adapters/trade_config.py`: `nse_holidays`, `NSE_HOLIDAYS_<year>`,
  `special_session`) from ATP's `EngineRequest.calendar`, entered per read under the shim's lock; ATP's runner hands in
  the calendar to the end of the next year and the per-timeframe data windows (ATP PR #863).
- T9 one-bot flow = an ATP deployment type on the existing EN-3 path: engine signal -> ATP signal row -> the existing
  approval (Telegram ✅ / ✏️ entry only / ❌ with a reason) -> PAPER fill -> exits. SL / target / lots / exits /
  approval window come ONLY from the user's dashboard settings (EXPORT_MANIFEST `dashboard_settings` gives the names;
  the values are the owner's, not known from the repo). Exits never blocked (ADR-0004). Needs the owner's word on the
  deployment-type shape before build (open point O-1 below).
- T10 MCX: its own deployment type on the same core, PAPER only; waits for T9.
- T11 level bots: rebuilt on the ported reader only after T6 is stable (owner order); not started.

## W9 (T12 / T14) `atp.sh import-trade` - design
- Input: Trade `docs/reader/EXPORT_MANIFEST.json` (103 items; the item checksum = sha256 of the sorted
  `path<TAB>sha256` lines). Every file is checked before anything is written; one mismatch stops the run.
- Destinations by kind: bars -> daily to `md_candles` (cross-check of the bhavcopy daily), intraday + FUT 5m volume to
  the owner tenant's `md_tenant_candles` through the HB0 importer (`app.market_lake.r2_import`); fixtures and owner
  charts -> the private fixtures store; records and review artefacts -> a private read-only archive on the host;
  `—` items are not moved.
- Steps: `--dry-run` (default) lists counts per destination and every checksum result; `--apply` writes, idempotent
  (a file already imported with the same sha256 is skipped). Never touches flags, secrets or another tenant.
- Note: the manifest at 813358b still names `engine-snapshot-v1` as its engine tag (its file list is the data side and
  is unchanged); the import records the manifest's own checksum, not the tag.
- Build: after the owner confirms O-2.

## W10 Shadow run - built
- ATP side (public PR #865): each bar's final run record is kept per day; `backend/scripts/trade_engine_export.py`
  writes one organisation's day (signals + run records) as JSON lines.
- Trade side: `tools/shadow/trade_export.py` (stdlib, read-only) writes Trade's `engine_signals` rows of one day.
- Compare: `python -m atp_private.shadow.diff --trade T --atp A --day D --out DIR` writes `shadow-D.md` / `.json` on the
  host (same / different with the fields / only Trade / only ATP with ATP's reason; ATP-minus-Trade write delay) and
  prints the counts only. A difference is a port bug to explain; never a fixture change. Switch-over and Trade's
  SUNSET only on the owner's own words.
- How the Trade file reaches the ATP host: default = the owner copies it (one block on each host, below). A daily
  push from the Trade VPS to trade-data is open point O-3.

### Daily blocks (after the flag `trade_engine` is ON and a trading day has passed; D = that day)
On the Trade VPS, as root:
```bash
# /tmp/trade_export.py = this repository's tools/shadow/trade_export.py, saved there once
D=YYYY-MM-DD
python3 /tmp/trade_export.py --db "${ENGINE_SIGNAL_DB:-/root/Trade/data/engine_signals.db}" --day "$D" > "/root/trade-shadow-$D.jsonl"
```
Then copy `/root/trade-shadow-$D.jsonl` to the ATP host as `/opt/atp/private_shadow/trade-$D.jsonl` (owner's own copy).
On the ATP host, as root:
```bash
D=YYYY-MM-DD; T=<organisation id>; mkdir -p /opt/atp/private_shadow && chown atp /opt/atp/private_shadow
su - atp -c "cd /opt/atp && nohup sh -c 'docker compose exec -T backend python scripts/trade_engine_export.py --tenant $T --day $D > /opt/atp/private_shadow/atp-$D.jsonl && PYTHONPATH=/opt/atp/private python3 -m atp_private.shadow.diff --trade /opt/atp/private_shadow/trade-$D.jsonl --atp /opt/atp/private_shadow/atp-$D.jsonl --day $D --out /opt/atp/private_shadow' > /tmp/atp-shadow.log 2>&1 &"
```
`tail -n 3 /tmp/atp-shadow.log` shows the counts (PASS / DIFF).

## Open points (defaults used)
- O-1 T9 shape: default = one deployment type "Signal engine (PAPER)" on the existing approval path, every trade
  value from the dashboard settings; no build until the owner says yes.
- O-2 import-trade: default = dry run first, owner tenant only, records archive read-only, nothing deleted in Trade.
- O-3 Trade file transfer: default = the owner copies it by hand; alternative = a daily VPS push to trade-data
  (a new Trade cron line, only on his word).
