# atp-private

ATP's **private package** (`atp_private`). Everything that must not be in the public ATP repository lives here:
the Trade signal engine / chart reader, the chart-analyze method, later the KB and the Method Pack. ATP's public code
holds only the boundary (a provider interface and a loader); see the public repo's `docs/design/PRIVATE_PACKAGE.md`
and `docs/design/TRADE_TAKEOVER.md`, and ATP order M66.

## Status: SKELETON (version 0.0.1)

No engine is imported yet. Every entry point fails closed:

| Module | ATP loader | Today |
|---|---|---|
| `atp_private.chart_analyze` | `backend/app/chart_analyze/provider.py` (exists) | the Analyze-a-chart provider on the snapshot's Method Pack (M79 W5) |
| `atp_private.trade_engine` | `backend/app/engine_provider/` (M66 EN-1) | `get_provider()` = the signal-engine shim (`provider.py`, M79): the engine's live path behind ATP's interface 1; needs ATP's backend on the import path; ATP's `trade_engine` flag stays OFF |

`atp_private.status()` -> `{"version": "0.0.1", "engine_imported": false, "status": "engine package present, engine not yet imported"}`.

**Rename:** the older plan (PRIVATE_PACKAGE.md sections 3, 9-10) named the reader module `atp_private.reader` and the
public boundary `app/reader/`. ATP order M66 (newer) names them `atp_private.trade_engine` and `app/engine_provider/`.
This package follows M66.

## Layout

```
atp_private/
  __init__.py          __version__, ENGINE_IMPORTED, status(), EngineNotImported
  trade_engine/        Trade engine snapshot (M65) + the shim get_provider() for ATP's provider interface (M66)
  chart_analyze/       Analyze-a-chart engine (get_provider() for ATP's AnalysisProvider)
tests/                 package tests (today: the skeleton smoke test)
fixtures/              (later) PR-2 goldens, same relative layout as ATP's tests expect (ATP_PRIVATE_FIXTURES)
knowledge/             (later) the KB / method / Method Pack (PRIVATE_PACKAGE.md section 8)
ATP_VERSION            the ATP commit this version is tested against
.github/workflows/     private CI (logs stay private)
```

## How ATP installs it

`deploy/atp.sh deploy` (step "chart analysis engine (private package atp_private)") on the ATP host:

1. reads `ATP_PRIVATE_REF` from `/opt/atp/.env` - **a tag** of this repository (never a branch);
2. fetches only that tag (`--depth 1`) with the read-only deploy key `~/.ssh/atp_private_ro` into `/opt/atp/private`
   and checks it out detached (repo address: `ATP_PRIVATE_REPO`, default `git@github.com:<owner>/atp-private.git`);
3. `docker-compose.hostinger.yml` mounts it read-only at `/opt/atp-private` in the backend and worker with
   `PYTHONPATH=/opt/atp-private`; `ATP_PRIVATE_VERSION` = the checkout's sha12.

**No `pip install`** happens on the host: the package root must stay importable straight from the checkout
(`atp_private/` at the repository root). `deploy/atp.sh health` prints `chart analysis engine: OK (<name> <version>)`
or `MISSING (<reason>)`.

### Dependencies

`pyproject.toml` declares **no** runtime dependencies on purpose. Any third-party library the engine needs must
already be in ATP's backend image (`backend/requirements.txt`, Python 3.13); otherwise the import fails and ATP
reports the engine as unavailable. When the M65 snapshot is imported, list here every third-party import it uses
and check each against ATP's requirements (a missing one is an ATP PR, not an install step here).

## How the Trade snapshot goes in (Trade order M65)

1. The Trade session copies the engine at the snapshot tag into `atp_private/trade_engine/<original module paths>`,
   unmodified apart from import paths, with the Trade tag and commit in `SNAPSHOT_TAG` and a manifest (path, sha256).
2. Its own tests are copied to `tests/` alongside.
3. A separate PR adds the shim `trade_engine.get_provider()` that adapts the snapshot to ATP's EN-1 provider
   interface, sets `ENGINE_IMPORTED = True` and bumps the version.
4. Tag (e.g. `v0.1.0`), CI green, then the owner moves `ATP_PRIVATE_REF` to it.

## Parity job plan (M66 EN-4)

In this repository's own GitHub Actions (private logs):

- the snapshot's copied tests;
- trade-data `parity/engine-snapshot-v2/` fixtures (M79 C4: v1 superseded) run through ATP's adapter and runner at `ATP_VERSION`; outputs
  (areas, states, swings, signals) must equal Trade's **byte for byte** - nothing is "close enough";
- ATP's backend tests at `ATP_VERSION` with the package installed and `ATP_PRIVATE_FIXTURES=fixtures/`;
- logs print case ids and field names only, never fixture content or method text.

Fetching trade-data from this job needs a read-only credential for it (an open owner decision; not set up here).
Today's CI only installs the package and runs the skeleton smoke test.

## Owner steps (once)

1. On the ATP host, as `atp`: `ssh-keygen -t ed25519 -f ~/.ssh/atp_private_ro -N "" -C "atp host read-only"`.
2. Here: Settings -> Deploy keys -> Add deploy key, paste `~/.ssh/atp_private_ro.pub`, **"Allow write access" unticked**.
   The private key never leaves the host.
3. Protect `main` (pull requests only, CI required, no force push); set an Actions spending limit.
4. When an engine is imported and parity is green: `ATP_PRIVATE_REF=<tag>` in `/opt/atp/.env`, then the usual deploy.
   (The skeleton tag `v0.0.1` can be used to check the install path: health then says MISSING with
   `EngineNotImported`, which is expected.)
