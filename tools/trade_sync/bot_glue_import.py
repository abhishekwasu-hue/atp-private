#!/usr/bin/env python3
"""tools/trade_sync/bot_glue_import.py - owner order SRV2 (15 + 18 Nov, "Default yes"): copy the Trade bot glue of "15M SRv2" (the
engine-signal entry path) from the same Trade commit as the engine snapshot into `atp_private/trade_engine/`, unmodified except the
import paths (the same `atp_import_rewrite.rewrite`), and list it in IMPORT_MANIFEST.json under `added_later`.

The Trade modules these files call at run time that ATP replaces (cloud_db, database, upstox_api, trading_engine, notifications,
classic_sr_reversal_trader, vision.*) are NOT copied: `atp_private.srv2.host` installs ATP's adapters for them.

    python3 tools/trade_sync/bot_glue_import.py --src <Trade checkout at the snapshot commit> --dest <atp-private checkout>
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

ENGINE_MODULES = ("trading_engine.py", "database.py", "trade_monitor.py", "order_safety.py", "entry_inflight.py", "carry_guard.py",
                  "exit_price_fallback.py", "monitor_timing.py", "charges.py", "log_setup.py", "process_lock.py", "order_execution.py",
                  "engine_service.py", "oi_analysis.py", "paper/watch.py", "mcx_contract_specs.py", "mcx_quantity_check.py",
                  "notify_policy.py", "read_cache.py", "paper/journal.py")
ENGINE_NOTE = ("owner 18 Nov (SRV2, OPEN_QUESTIONS SRV2-Q1 default A): Trade's PAPER engine for the bot's positions - open, exits "
               "(manage_open_trades) and the monitor loop - copied from the same commit with the same import rewrite; ATP's adapters for "
               "cloud_db / upstox_api / notifications / broker_factory are installed by atp_private.srv2.host")
RUNNER_MODULES = ("scripts/engine_signal_run.py", "scripts/engine_resident.py")
RUNNER_NOTE = ("owner 18 Nov (SRV2): the engine's run path (engine_signal_run.main per symbol, engine_resident's close / due / window "
               "functions) copied AS IS; atp_private.srv2.runner calls them in-process at each 5M close instead of Trade's cron")
MODULES = ("strategy.py", "paper/__init__.py", "paper/engine_entry.py", "paper/bot_hooks.py", "paper/config.py",
           "paper/lots.py", "paper/pause.py", "bots_common/gate_alert.py", "bots_common/error_once.py")
NOTE = ("owner 18 Nov (SRV2, 15M SRv2 port AS IS): the bot's engine-entry glue copied from the same commit with the same import "
        "rewrite (tools/trade_sync/bot_glue_import.py); ATP's adapters for the Trade IO modules it calls are installed by atp_private.srv2.host")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dest", required=True)
    a = ap.parse_args(argv)
    src, dest = os.path.abspath(a.src), os.path.abspath(a.dest)
    sys.path.insert(0, src)                                               # the rewrite tools import `scripts.engine_closure` (Trade layout)
    sys.path.insert(0, os.path.join(src, "scripts"))
    import atp_import_rewrite as AIR
    from scripts import engine_closure as EC
    pkg = os.path.join(dest, "atp_private", "trade_engine")
    man_p = os.path.join(pkg, "IMPORT_MANIFEST.json")
    with open(man_p, encoding="utf-8") as f:
        man = json.load(f)
    tops = EC.top_modules(src)
    later = man.get("added_later") or {}
    if isinstance(later, dict) and "modules" in later:                    # the first block (pre-open charts) kept as is
        later = {"preopen": later}
    for key, mods, note in (("srv2_glue", MODULES, NOTE), ("srv2_engine", ENGINE_MODULES, ENGINE_NOTE),
                             ("srv2_runner", RUNNER_MODULES, RUNNER_NOTE)):
        later[key] = {"note": note, "modules": _copy(src, pkg, tops, AIR, mods), "tests": []}
    man["added_later"] = later
    with open(man_p, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print("copied", {k: len(v["modules"]) for k, v in later.items()})


def _copy(src, pkg, tops, AIR, modules):
    done = []
    for rel in modules:
        with open(os.path.join(src, rel), encoding="utf-8") as f:
            text = f.read()
        out = AIR.rewrite(text, tops, src)
        p = os.path.join(pkg, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(out)
        done.append(rel)
    return done


if __name__ == "__main__":
    main()
