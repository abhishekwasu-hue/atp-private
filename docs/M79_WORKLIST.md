# M79 work list - engine takeover on engine-snapshot-v2 (T1-T14, corrections C1-C6 applied)

Source: owner order M79 (ATP `docs/owner-orders/ATP_ORDER_M79.md`) and the Trade-side handover in trade-data, branch
`claude/fix-proof-gallery`: `handover/2026-10-31_ATP_takeover/ATP_SESSION_PROMPT.md`, `PLAN.md`, `M65_REPORT.md`.
The handover prompt was written for v1; every v1 reference below is replaced per C1-C6. Everything else in it stands.

## Corrections applied everywhere
- **C1** Snapshot = `engine-snapshot-v2` = Trade commit `813358bc1064645fcf2ca005959d9658804633e3` (Trade main). v1
  (`79feb62`) is superseded: branch `import/engine-snapshot-v1` is never merged.
- **C2** Verify by commit, not by tag: `atp_private/trade_engine/IMPORT_MANIFEST.json` commit = 813358b..., trade-data
  `parity/engine-snapshot-v2/MANIFEST.json` commit = 813358b... (its `source_commit` 8e2b079 has the identical tree).
  If the tag appears on Trade later, record it in the port map; nothing else changes.
- **C3** Fixtures = trade-data `parity/engine-snapshot-v2/` (188 files + MANIFEST.json), on trade-data branch
  `claude/fix-proof-gallery` (or `main` once merged). `parity/engine-snapshot-v1/` and `parity/layer1..4/` are superseded.
- **C4** ATP work already built against v1 (M66 EN-4 parity CI text, `chart_analyze` provider, `docs/TRADE_PORT_MAP.md`
  3a "Stable tag") is re-pointed to v2 in the same PRs; never two snapshots in one layer.
- **C5** atp-private PR #1 (`claude/overseer-method-kit`, docs only) is reviewed and merged first.
- **C6** The known failures of the copied tests (515 pass / 10 fail / 17 errors in Trade's run) are left-out ATP-GENERIC
  dependencies; each becomes an ATP adapter or a visible skip with a reason, never a logic change.

## What the owner has done / must do first (checked 1 Nov from this session)
| # | Prerequisite | State | Evidence |
|---|---|---|---|
| 1 | `atp-private` exists, Private | present | GitHub API: `visibility = private` |
| 2 | Claude GitHub app access to `atp-private` (push) | present | API permissions `push = true`; this branch was pushed and its draft PR opened |
| 3a | Branch protection on `main` (PRs only, private CI required, no force push) | **missing** | API: branch `main` `protected = false`; rulesets API: "Upgrade to GitHub Pro or make this repository public"; protection on a private repo needs a paid plan |
| 3b | Actions spending limit for private minutes | **missing / blocked** | Both CI runs (main push, PR #1) "not started because recent account payments have failed or your spending limit needs to be increased" |
| 4 | Host READ-ONLY deploy key on `atp-private` | not verifiable here | the deploy-keys API path is refused by the session proxy; owner to confirm on the Deploy keys page |
| 5 | Trade repo Private + tokens rotated (Upstox / Telegram / Stoxkart) | Private: present; rotation: not verifiable | API: Trade `visibility = private`; token rotation is outside any repo |

Click paths (PRIVATE_PACKAGE section 6):
- 3a: atp-private -> Settings -> Branches -> Add branch protection rule `main`: require a pull request, require the
  status check `test` (ci), block force pushes. (Needs GitHub Pro on a private repo.)
- 3b: GitHub (account) -> Settings -> Billing and plans -> Payment information / Spending limits -> Actions: fix the
  payment method or set a limit; 0 still blocks private runs once the free minutes are used.
- 4: atp-private -> Settings -> Deploy keys -> Add deploy key (host `.pub` only, "Allow write access" unticked).
- 5: rotate in each broker / Telegram console; nothing to do in GitHub.

## Facts checked for the import (1 Nov)
- Trade: 813358b is Trade `main` HEAD; 813358b and 8e2b079 have the same tree; no `engine-snapshot-*` tag on Trade yet.
- `import/engine-snapshot-v2` (4315308): IMPORT_MANIFEST commit = 813358b; 190 listed files all present; against Trade
  at 813358b: 97 byte-equal, 93 differ only in import lines (the 93 the manifest lists as rewritten); 0 other diffs.
- No `.env`, key, database or market-data file; no server address. Committed by mistake: `atp_private/__pycache__/*.pyc`.
- The branch has **no common history with `main`** (its root is the v1 import commit, itself a root commit), so GitHub
  cannot open a PR from it. Merging locally with `--allow-unrelated-histories` is conflict-free and keeps main's
  `atp_private/__init__.py` and `atp_private/trade_engine/__init__.py` (the v2 copies are empty).
- Copied tests on main + v2 (Python 3.13, Trade's matplotlib / plotly installed): 501 passed, 14 skipped (private
  trade-data not present, visible reason), 10 failed, 17 errors, 1 xfailed. 501 + 14 = Trade's 515.
  - 10 failed: config (3: claim / mark_seen path), cloud_db (3), scripts or files read by path (4).
  - 17 errors: repo parquet (13), cloud_db at module level (1), research module / file read by path (2), a Trade
    script module not copied (1).
- Fixtures: MANIFEST commit = 813358b; 188 / 188 files match their sha256; no unlisted file.

## The work (one draft PR per step, self-reviewed, merge on green CI, PAPER only, flags OFF)
- **W0 (C5)** Merge PR #1 overseer kit once CI can run (blocked by 3b).
- **W1 Import (T1-T6 base)**: a new branch from `main` that carries the v2 tree as one commit on top of `main` (no
  force push, no history rewrite; v1 never merged), without the committed `__pycache__`, keeping main's two
  `__init__.py` files; then PR -> main. In the same PR: the private CI job (PRIVATE_PACKAGE sections 5, 13) running the
  copied tests, the stale-pack test and `tests/test_reader_no_numbers.py`; every C6 failure turned into a visible skip
  with a reason (`ATP adapter not ported yet: config | cloud_db`, `repo data file not in the package`, `Trade script
  read by path, not ported`) or an adapter; the 14 data tests skip visibly when the store is not mounted.
- **W2 Fixtures store (T13)**: a dry-run-first host command copying trade-data `parity/engine-snapshot-v2/` from branch
  `claude/fix-proof-gallery` (or `main` once merged) into `<ATP_PRIVATE_FIXTURES>/parity/engine-snapshot-v2/`, checking
  all 188 files against MANIFEST.json and stopping on the first mismatch; commit only paths + sha256. Owner runs ONE block.
- **W3 Parity per layer (T1-T6)**: one PR per layer, reading the store (skip visibly if not mounted, error if set but
  empty); build exactly as Trade's `scripts/reader_parity_export.build`; byte-equal after `_jsonable`; layer 1 swings +
  SW + step 1; 2 areas, BREAK-2 lifecycle, Z; 3 the 15M decision row; 4 lines + confluence; 5 RSI (C); 6 verdicts + every
  5M `decide5` row (EN1-EN3, D+E, E1-E4); plus golden, answer_key_v4, trigger5m, days. A difference = port bug.
- **W4 English owner modules (T1-T6)**: per the port map targets; logic copied as is, module headers name
  `engine-snapshot-v2` + 813358b; parity of W3 stays green; `atp_private/trade_engine/` is kept.
- **W5 Public boundary (ATP repo, C4)**: provider / loader / adapter per PRIVATE_PACKAGE sections 9-10 on the existing
  `backend/app/engine_provider/`; flags OFF; port map 3a "Stable tag" = `engine-snapshot-v2` (commit 813358b) with the
  re-port note; M66 EN-4 and `chart_analyze` provider re-pointed to v2. No method text, fixture or Trade logic public.
- **W6 T7** KB / Method Pack from `atp_private/trade_engine/docs/knowledge/` (pack hash = STABLE row) + stale-pack test.
- **W7 T8** Vision method checklist from the Method Pack, audit only (ADR-0006), human_confirm.
- **W8 T9 / T10 / T11** design notes first, then ATP-GENERIC adapters only; SL / target / lots / exits / approval
  window from the user's dashboard settings; exits never blocked (ADR-0004); T11 only after T6.
- **W9 T12 / T14** `atp.sh import-trade` driven by EXPORT_MANIFEST.json (sha256, dry run, idempotent). Owner runs it.
- **W10 Shadow run** ATP PAPER beside Trade PAPER; switch-over and SUNSET only on the owner's own words.

## W2 host command (T13) - the owner runs this ONE block on the ATP host, as root

Before it, once: as the `atp` user, `ssh-keygen -t ed25519 -f ~/.ssh/trade_data_ro -N "" -C "atp host trade-data read-only"`,
then trade-data -> Settings -> Deploy keys -> Add deploy key: paste `~/.ssh/trade_data_ro.pub`, "Allow write access"
unticked. (GitHub allows a key on one repository only, so this is a second key beside `atp_private_ro`.)

What it does: a sparse, depth-1 fetch of trade-data branch `claude/fix-proof-gallery`, only `parity/engine-snapshot-v2/`.
It checks the MANIFEST commit (813358b), all 188 sha256 and that there is no unlisted file. Then it renames the folder
into `/opt/atp/private_fixtures/parity/engine-snapshot-v2/` (read-only) and checks it again.
- Idempotent: if the folder is already there and verifies, it does nothing.
- Fail-safe: if the folder is there and does not verify, it stops and leaves it untouched. On any mismatch, missing or
  unlisted file it stops with exit 1 and writes nothing to the store.
- It runs in the background as `atp`. The last line of the log is `RESULT: OK` or `RESULT: FAILED (exit N)`.

```bash
cat > /tmp/atp-m79-fixtures.sh <<'ATPEOF'
#!/usr/bin/env bash
# M79 W2 / T13: copy trade-data parity/engine-snapshot-v2 into the private fixtures store, every file checked.
set -euo pipefail
SNAP=engine-snapshot-v2
COMMIT=813358bc1064645fcf2ca005959d9658804633e3
BRANCH="${BRANCH:-claude/fix-proof-gallery}"
REPO="${REPO:-git@github.com:abhishekwasu-hue/trade-data.git}"
KEY="${KEY:-$HOME/.ssh/trade_data_ro}"
STORE="${STORE:-/opt/atp/private_fixtures}"
DEST="$STORE/parity/$SNAP"
WORK="$STORE/.incoming-$SNAP"
say() { printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
fail() { say "STOP: $*"; exit 1; }
trap 'rc=$?; rm -rf "$WORK"; [ $rc -eq 0 ] || say "RESULT: FAILED (exit $rc)"' EXIT
[ "$(id -un)" = atp ] || [ -n "${ALLOW_ANY_USER:-}" ] || fail "run as the atp user"
command -v git >/dev/null && command -v python3 >/dev/null || fail "git and python3 are needed"
case "$REPO" in git@*) [ -r "$KEY" ] || fail "read-only deploy key $KEY not found"
  export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" ;; esac

# verify DIR: MANIFEST commit, every listed file's sha256, no unlisted file. Prints one line; non-zero on any problem.
verify() {
  python3 - "$1" "$COMMIT" 2>&1 <<'PY'
import hashlib, json, os, sys
root, commit = sys.argv[1], sys.argv[2]
m = json.load(open(os.path.join(root, "MANIFEST.json")))
if m.get("commit") != commit:
    sys.exit(f"MANIFEST commit {m.get('commit')} is not {commit}")
files = m["files"]
have = set()
for d, _, fs in os.walk(root):
    for f in fs:
        have.add(os.path.relpath(os.path.join(d, f), root))
have.discard("MANIFEST.json")
unlisted = sorted(have - set(files))
if unlisted:
    sys.exit(f"unlisted file(s): {unlisted[:5]} ({len(unlisted)})")
for rel, want in sorted(files.items()):
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        sys.exit(f"missing: {rel}")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != want:
        sys.exit(f"sha256 mismatch: {rel}")
print(f"verified {len(files)} / {len(files)} files, commit {commit[:7]}, no unlisted file")
PY
}

say "M79 W2: $SNAP -> $DEST"
if [ -e "$DEST" ]; then
  say "already present: checking it"
  out="$(verify "$DEST")" || fail "the installed copy does not verify (left untouched): $out"
  say "$out"; say "nothing to do"; say "RESULT: OK"; exit 0
fi
mkdir -p "$STORE/parity"
avail=$(df -Pk "$STORE" | awk 'NR==2{print $4}')
[ "$avail" -gt 1500000 ] || fail "less than 1.5 GB free under $STORE"
rm -rf "$WORK"
say "fetching branch $BRANCH (sparse, depth 1)"
git clone -q --depth 1 --filter=blob:none --sparse --no-tags --branch "$BRANCH" "$REPO" "$WORK/repo"
git -C "$WORK/repo" sparse-checkout set --no-cone "/parity/$SNAP/"
say "trade-data commit $(git -C "$WORK/repo" rev-parse --short HEAD)"
SRC="$WORK/repo/parity/$SNAP"
[ -f "$SRC/MANIFEST.json" ] || fail "no parity/$SNAP/MANIFEST.json on $BRANCH"
out="$(verify "$SRC")" || fail "$out"
say "$out"
mv "$SRC" "$WORK/$SNAP"
mv "$WORK/$SNAP" "$DEST"
chmod -R a-w "$DEST"
out="$(verify "$DEST")" || fail "after the move: $out"
say "$out"
say "installed: $DEST ($(du -sh "$DEST" | cut -f1))"
say "RESULT: OK"
ATPEOF
chown atp /tmp/atp-m79-fixtures.sh && su - atp -c "nohup bash /tmp/atp-m79-fixtures.sh > /tmp/atp-m79-fixtures.log 2>&1 &"
```
After a minute: `tail -n 8 /tmp/atp-m79-fixtures.log`.

Tested in the session (1 Nov) against trade-data with a temporary store (`STORE=`, `REPO=` overrides):
- First run: 188 / 188 verified, installed (424 MB), `RESULT: OK`.
- Second run: "nothing to do", `RESULT: OK`.
- One byte flipped in an installed file: "sha256 mismatch", exit 1, left untouched.
- An extra file: "unlisted file(s)", exit 1.
- A source branch with one corrupted byte: "sha256 mismatch", exit 1, the store stays empty.

Re-tested 1 Nov in the T1-T6 session the same way (REPO = the trade-data GitHub remote, temporary STORE): first run
188 / 188 verified, installed, OK; second run "nothing to do"; one byte flipped in an installed file: "sha256 mismatch",
exit 1, left untouched; an extra file: exit 1; a source branch whose one file has a flipped byte: "sha256 mismatch",
exit 1, the store holds no snapshot folder.

Open point (default used): the store path is `/opt/atp/private_fixtures` until the owner names another one.
`ATP_PRIVATE_FIXTURES` and `BACKUP_EXTRA_DIRS` in `/opt/atp/.env` are set later by an `atp.sh` PR (W9), not here.

## W5 host install block - the owner runs this ONE block on the ATP host, as root

What it does (Analyze a chart / Copilot "Analyze my chart" on production):
1. Makes the host's read-only deploy key `~/.ssh/atp_private_ro` for the `atp` user, only if it does not exist yet.
2. Checks with `git ls-remote` that the key can read `atp-private`. If not, it stops (exit 2) and prints the public
   half: paste it in atp-private -> Settings -> Deploy keys -> Add deploy key, "Allow write access" unticked; then run
   the block again.
3. Sets `ATP_PRIVATE_REF=ec152c9d331e5ba8ea135be1c6179be55c716112` in `/opt/atp/.env` (the reviewed atp-private main commit: the Analyze-a-chart shim
   on engine-snapshot-v2). A backup of `.env` is kept once as `.env.bak-m79`. Nothing else in `.env` changes.
4. Runs `atp.sh deploy` twice, then `atp.sh health`. The first deploy brings the `atp.sh` that can fetch by commit sha
   (ATP PR #857, which must be merged first); the second converges on the same release and fetches the private
   package into `/opt/atp/private` (read-only mount into the backend and the worker). It stops if `atp.sh` still
   cannot fetch by sha.
- Idempotent: a second run changes nothing (same key, same ref, deploy converges).
- What changes on the host: the key file pair (if new), one line in `.env`, the checkout `/opt/atp/private`, the
  backend and worker containers recreated on the new mount. No database migration, no flag, no order path.
- It runs in the background as `atp`. The last line of the log is `RESULT: OK` or `RESULT: FAILED (exit N)`.

```bash
cat > /tmp/atp-m79-engine.sh <<'ATPEOF'
#!/usr/bin/env bash
# M79 W5: the private package at a reviewed atp-private commit for Analyze a chart, then deploy + health.
set -euo pipefail
REF=ec152c9d331e5ba8ea135be1c6179be55c716112
ENVF="${ENVF:-/opt/atp/.env}"
ATP="${ATP:-/opt/atp/deploy/atp.sh}"
KEY="${KEY:-$HOME/.ssh/atp_private_ro}"
REPO="${REPO:-git@github.com:abhishekwasu-hue/atp-private.git}"
say() { printf '%s %s\n' "$(date -u +%H:%M:%SZ)" "$*"; }
trap 'rc=$?; [ $rc -eq 0 ] && say "RESULT: OK" || say "RESULT: FAILED (exit $rc)"' EXIT
[ "$(id -un)" = atp ] || [ -n "${ALLOW_ANY_USER:-}" ] || { say "STOP: run as the atp user"; exit 1; }
[ -f "$ENVF" ] || { say "STOP: $ENVF not found"; exit 1; }
if [ ! -f "$KEY" ]; then
  mkdir -p "$(dirname "$KEY")" && chmod 700 "$(dirname "$KEY")"
  ssh-keygen -q -t ed25519 -f "$KEY" -N "" -C "atp host read-only"
  say "made the read-only deploy key $KEY"
fi
if ! GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new" \
     GIT_TERMINAL_PROMPT=0 git ls-remote -q "$REPO" HEAD >/dev/null 2>&1; then
  say "STOP: the key cannot read atp-private yet. Add this PUBLIC key in atp-private -> Settings -> Deploy keys"
  say "      -> Add deploy key ('Allow write access' unticked), then run this block again:"
  cat "$KEY.pub"
  exit 2
fi
say "deploy key reads atp-private: OK"
[ -e "$ENVF.bak-m79" ] || cp -p "$ENVF" "$ENVF.bak-m79"
if grep -q '^ATP_PRIVATE_REF=' "$ENVF"; then sed -i "s|^ATP_PRIVATE_REF=.*|ATP_PRIVATE_REF=$REF|" "$ENVF"
else printf '\nATP_PRIVATE_REF=%s\n' "$REF" >> "$ENVF"; fi
say "ATP_PRIVATE_REF=$REF in $ENVF"
"$ATP" deploy
grep -q 'kind="commit"' "$ATP" || { say "STOP: this atp.sh cannot fetch by commit sha yet (ATP PR #857 not merged)"; exit 3; }
"$ATP" deploy
"$ATP" health || say "health reported a warning or a problem (see the lines above)"
ATPEOF
chown atp /tmp/atp-m79-engine.sh && su - atp -c "nohup bash /tmp/atp-m79-engine.sh > /tmp/atp-m79-engine.log 2>&1 &"
```
After about ten minutes: `grep -E 'chart analysis engine|trade engine|RESULT' /tmp/atp-m79-engine.log`.

Expected: `chart analysis engine source at commit ec152c9...`, then in health `chart analysis engine: OK
(atp-trade-engine engine-snapshot-v2+813358b)` and `trade engine: MISSING (the engine failed to start
(EngineNotImported))` (the signal-engine shim EN-1 is not built; its flag stays OFF).

Tested locally with fakes (a fake atp.sh that records its calls, a local bare repository for atp-private, a stub
ssh-keygen, a temporary .env): no access -> exit 2, the public half printed, the private half never, .env untouched;
access -> the ref line replaced (mode kept, one backup), deploy, deploy, health, RESULT: OK; a second run -> no new key,
no second backup, RESULT: OK; an atp.sh without sha support -> STOP after the first deploy, exit 3; a .env without the
line -> the line appended.

Proposed order now: W0 (after 3b) -> W1 -> W2 -> W3 T1 -> W5 port-map re-point -> W3 T2..T6 -> W4 -> W6 .. W10.

Status (1 Nov): W1 merged (#3). W2 host command tested (above). W3 T1-T6 merged (#4): layers 1-6, 48 / 48 cases
byte-equal. W3 comparisons (`atp_private/parity/extras.py`, local run on the v2 store, 1 Nov): golden 3 / 3
(golden.json + 2 chart cases), answer_key_v4 8 / 8, trigger_5m 20 / 20, real_days 20 / 20 day files (+ the chosen days
equal the MANIFEST for both indices). W5: Analyze-a-chart shim merged (#5,
main ec152c9); ATP PR #857 (ATP_PRIVATE_REF may be a commit sha) is a draft, it must merge before the install block.
The signal-engine shim (EN-1, `trade_engine.get_provider` -> `trade_engine/provider.py`) is built: the engine's own
live path (engine3_live) on a feed served from ATP's request bars, mapped to ATP's interface 1; ATP's loader loads it
(tested against ATP's real loader and contract). ATP's `trade_engine` flag stays OFF. Open (owner, defaults used): card
steps / setup / evidence tokens empty (needs a public phrase table); swings empty (no HH / HL labels in the engine);
ATP runner windows default to 10 intraday / 400 daily days, Trade's live path reads 90 days 15M + up to 1825 days of
15M history and 3650 Daily days - the runner settings decide what the engine gets.

Status (1 Nov, W6-W10 session): W6 KB / Method Pack (`knowledge/`, `atp_private.method_pack`, pack 1674732c62ba =
STABLE row) and W7 private side (Vision checklist + validator from the pack) built; W8 calendar adapter built (engine
config from ATP's request calendar) with ATP PR #863 (runner windows per timeframe as settings: 15m 90 + history
1825, Daily 400 + history 3650; calendar to the end of the next year); W9 design only (`docs/M79_W7_W10_DESIGN.md`,
waits for the owner's O-2); W10 shadow diff built here + ATP PR #865 (day export). T9-T11 wait for the owner (O-1).
