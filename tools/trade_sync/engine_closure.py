#!/usr/bin/env python3
"""scripts/engine_closure.py — the static import closure of the live engine (owner order M65 X-2 / X-3): every module of this repo that
the entry points import, directly or through another module (module-level AND function-level imports, read with `ast`; nothing is
imported or run). A TRADE-ONLY module reached on the way is listed but not followed. Used by scripts/reader_export_manifest.py (EXPORT_MANIFEST engine section) and scripts/atp_import_rewrite.py (the PORT
set copied into atp-private). No network, no data.

    python3 scripts/engine_closure.py            # prints `class  path` per module
"""
import ast
import functools
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRIES = ("engine_signal.py", "engine3_live.py", "scripts/engine_resident.py", "paper/engine_entry.py", "vision/engine_audit.py",
           "vision/signal_audit.py", "bots_common/level_gate_bot.py")

# Classification (M65 X-2). First match wins; a path or a path prefix ("dir/"). PORT = into atp-private as is; ATP-GENERIC = ATP already
# has it (Telegram, PAPER fills, exits, approvals, brokers, storage, config); TRADE-ONLY = legacy bots, Streamlit pages, VPS scripts.
ATP_GENERIC = ("vision/tg.py", "vision/telegram_bot.py", "vision/notify.py", "vision/approval.py", "vision/store.py", "vision/worker.py",
               "vision/hook.py", "vision/images.py", "vision/outcome.py", "vision/shadow_view.py", "vision/signal_audit.py",
               "vision/config.py", "vision/card_summary.py", "vision/chart.py", "vision/decide.py", "vision/gate.py",
               "paper/", "notifications.py", "notify_policy.py", "cloud_db.py", "database.py", "config.py", "broker_adapter.py",
               "broker_factory.py", "upstox_api.py", "upstox_broker_adapter.py", "upstox_feed_pb2.py", "fyers_api.py",
               "fyers_broker_adapter.py", "shoonya_api.py", "shoonya_broker_adapter.py", "stocko_api.py", "stocko_broker_adapter.py",
               "order_execution.py", "order_safety.py", "trading_engine.py", "position_stream_monitor.py", "trade_monitor.py",
               "process_lock.py", "log_setup.py", "crypto_utils.py", "live_confirm.py", "exit_price_fallback.py", "carry_guard.py",
               "charges.py", "entry_inflight.py", "market_data_adapter.py", "price_stream.py", "shared_context.py", "read_cache.py",
               "bots_common/error_once.py", "bots_common/gate_alert.py", "bots_common/area_alert.py", "bots_common/private_file.py",
               "bots_common/one_bot.py", "mcx_margin.py", "pnl_reports.py", "pdf_reports.py", "live_ticker.py", "monitor_timing.py",
               "check_token_freshness.py", "upstox_token_webhook.py", "lib/")
TRADE_ONLY = ("scripts/", "deploy/", "app.py", "page_", "safe_widgets.py", "ui_headers.py", "bot_view.py", "live_chart.py",
              "live_chart_component/", "mini_chart.py", "position_chart.py", "tradingview_chart.py", "trade_table_view.py",
              "srv2_momentum_reversal_strategy.py", "srv3_instant_shadow.py", "classic_sr_reversal_trader.py",
              "dynamic_sr_instant_trader.py", "credit_spread_auto_trader.py", "oi_signal_auto_trader.py", "mcx_", "refresh_",
              "weekly_dual_expiry_option_seller.py", "gap_fill_reversal_strategy.py", "mtf_pullback_strategy.py", "strategies/",
              "orchestrator.py", "engine_service.py", "backtest_review/", "gallery2/", "review7/", "research/", "vision2/", "vision_led/",
              "eod_", "market_report.py", "oi_", "iv_snapshot_collector.py", "pullback_credit_spread/", "strategy.py",
              "strategy_payoff.py", "strike_breach_model.py", "multi_strategy_backtest.py", "backtest.py", "sr_", "level_memory.py",
              "market_zones.py", "signals.py", "entry_engine.py", "htf_alignment.py", "nifty_futures_swing_rsi_st.py",
              "banknifty_positional.py", "decision2/", "reader2/", "reader_report/", "simple_core/", "diagnostics.py",
              "yfinance_source.py", "real_nifty_data.py", "loader.py")
PORT_ALWAYS = ("scripts/build_method_pack.py",)
PORT_EXTRA = ("backtest_review/__init__.py", "backtest_review/charts.py", "vision_led/__init__.py", "vision_led/charts.py")   # chart
# helpers a PORT module (pivots/charts.py) imports at module level — display only, copied with it
NAMESPACE = ("scripts",)                                                   # imported as a package without an __init__.py (tests)                            # the Method Pack builder goes with the KB (TRADE_TAKEOVER §8)


def classify(rel):
    if rel in PORT_ALWAYS or rel in PORT_EXTRA:
        return "PORT"
    for kind, pats in (("ATP-GENERIC", ATP_GENERIC), ("TRADE-ONLY", TRADE_ONLY)):
        if any(rel == p or (p.endswith(("/", "_")) and rel.startswith(p)) for p in pats):
            return kind
    return "PORT"


@functools.lru_cache(maxsize=None)
def top_modules(root=HERE):
    """Top-level importable names of this repo: packages (dir with __init__.py) and *.py files at the root."""
    out = set()
    for e in os.listdir(root):
        p = os.path.join(root, e)
        if e.endswith(".py"):
            out.add(e[:-3])
        elif os.path.isdir(p) and (os.path.exists(os.path.join(p, "__init__.py")) or e in NAMESPACE):
            out.add(e)
    return frozenset(out)


@functools.lru_cache(maxsize=None)
def resolve(name, root=HERE):
    """Dotted module name ⇒ repo-relative file (package ⇒ its __init__.py), or None."""
    base = os.path.join(root, *name.split("."))
    if os.path.isfile(base + ".py"):
        return os.path.relpath(base + ".py", root)
    if os.path.isfile(os.path.join(base, "__init__.py")):
        return os.path.relpath(os.path.join(base, "__init__.py"), root)
    return None


def _modname(rel):
    m = rel[:-3].replace(os.sep, ".")
    return m[:-9] if m.endswith(".__init__") else m


def imports_of(rel, root=HERE):
    return set(_imports_of(rel, root))


@functools.lru_cache(maxsize=None)
def _imports_of(rel, root=HERE):
    """Repo modules imported anywhere in file `rel` (absolute + relative imports; `from pkg import mod` resolves mod when it is one)."""
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        tree = ast.parse(f.read(), rel)
    me = _modname(rel)
    pkg = me if rel.endswith("__init__.py") else me.rpartition(".")[0]
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = pkg.split(".") if pkg else []
                parts = parts[:len(parts) - (node.level - 1)] if node.level > 1 else parts
                mod = ".".join(parts + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            names.append(mod)
            names += [f"{mod}.{a.name}" for a in node.names if a.name != "*"]
    tops = top_modules(root)
    out = set()
    for n in names:
        if not n or n.split(".")[0] not in tops:
            continue
        parts = n.split(".")
        for k in range(1, len(parts) + 1):                                  # every package on the way is imported too
            r = resolve(".".join(parts[:k]), root)
            if r:
                out.add(r)
    out.discard(rel)
    return frozenset(out)


def closure(entries=ENTRIES, root=HERE, expand_trade_only=False):
    """{module rel path: sorted imports} for everything reachable from `entries`. A TRADE-ONLY module (a VPS script, a legacy bot, a
    page) is listed where it is imported but not followed further (its own imports are not the live engine's), unless it is an entry
    point or `expand_trade_only`."""
    entries = [e for e in entries if os.path.exists(os.path.join(root, e))]
    seen, todo = {}, list(entries)
    while todo:
        r = todo.pop()
        if r in seen:
            continue
        if r not in entries and not expand_trade_only and classify(r) == "TRADE-ONLY":
            seen[r] = []
            continue
        seen[r] = sorted(imports_of(r, root))
        todo += [x for x in seen[r] if x not in seen]
    return dict(sorted(seen.items()))


def main():
    c = closure()
    for r in c:
        print(f"{classify(r):12s} {r}")
    print(f"{len(c)} modules", file=sys.stderr)


if __name__ == "__main__":
    main()
