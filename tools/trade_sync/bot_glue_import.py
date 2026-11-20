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
    done = []
    for rel in MODULES:
        with open(os.path.join(src, rel), encoding="utf-8") as f:
            text = f.read()
        out = AIR.rewrite(text, tops, src)
        p = os.path.join(pkg, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(out)
        done.append(rel)
    later = man.get("added_later") or {}
    if isinstance(later, dict) and "modules" in later:                    # the first block (pre-open charts) kept as is
        later = {"preopen": later}
    later["srv2_glue"] = {"note": NOTE, "modules": done, "tests": []}
    man["added_later"] = later
    with open(man_p, "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(f"copied {len(done)} modules")


if __name__ == "__main__":
    main()
