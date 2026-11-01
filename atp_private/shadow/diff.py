"""The shadow run's daily diff report: every Trade engine signal of one day against every ATP engine signal of the
same day (owner order M79 W10; ATP order M66 EN-4: "signals, timing, states"; TRADE_TAKEOVER section 11).

Inputs (both made on the hosts by the owner's ONE command block; files stay on the ATP host, never in any repository):
- Trade: the day's rows of Trade's `engine_signals` table (`tools/shadow/trade_export.py`, one JSON object per line:
  symbol, bar_ts, computed_at, decision, payload). A row's fired entry models are `payload.entries`
  (`engine3_live.compact_entries`).
- ATP: the day's lines of ATP's `backend/scripts/trade_engine_export.py`: kind "signal" (the runner's internal
  signal row: symbol, timeframe, bar_end, model_id, instance_id, side, area_id, area_state, entry_zone, invalidation,
  written_at) and kind "run" (a run record: symbol, timeframe, bar_end, status, reason, problems, at).

Both sides go through the same normalisation the signal-engine shim uses (`provider.instrument_of`, `TF_KEYS`, the
area side from its role), so a difference is a real one. One signal = (symbol, bar END, model, entry key):
- same: on both sides with the same timeframe, side, area (range and id), area state and invalidation;
- different: on both sides, with the fields that differ;
- only Trade / only ATP: with ATP's run record of that bar as the reason when there is one (data gap, missing futures
  volume, missed / given up, the engine read failed, no signal = a port difference) or "no ATP run record".
Timing: ATP's write time minus Trade's computed time, per matched signal (seconds).

PAPER only; nothing here reads or changes an order, a flag or a setting. A difference is a port bug to explain, never a
fixture or golden change.
"""
import argparse
import datetime as dt
import json
import os
import sys
from collections import Counter
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
TF_KEYS = {"5M": "5m", "15M": "15m", "1H": "1h", "D": "1d", "W": "1w"}
AREA_SIDE = {"support": "buyer", "resistance": "seller"}
DIRECTION_SIDE = {1: "buyer", -1: "seller"}
FIELDS = ("timeframe", "side", "area", "area_id", "area_state", "invalidation")
SAME, DIFFERENT, ONLY_TRADE, ONLY_ATP = "same", "different", "only Trade", "only ATP"

# ATP run statuses (app/workers/engine_runner.py) -> the reason in plain words
RUN_REASON = {"data_gap": "ATP: data gap on this bar", "failed": "ATP: the engine read failed",
              "missed": "ATP: bar reached after its grace window", "given_up": "ATP: given up after its attempts",
              "no_signal": "ATP engine read the bar: no signal (port difference)",
              "signal": "ATP wrote other signal(s) on this bar"}


def _instrument(symbol):
    try:
        from atp_private.trade_engine.provider import instrument_of
        return instrument_of(symbol) or str(symbol).upper()
    except Exception:                                                     # noqa: BLE001 - names only; never fails the report
        return str(symbol).upper()


def _ts(x):
    """Any time text / datetime -> ISO minute in IST (naive Trade times are IST)."""
    if x in (None, ""):
        return None
    t = x if isinstance(x, dt.datetime) else dt.datetime.fromisoformat(str(x).replace("Z", "+00:00").replace(" ", "T", 1))
    t = t.replace(tzinfo=IST) if t.tzinfo is None else t.astimezone(IST)
    return t.replace(second=0, microsecond=0).isoformat()


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, 6) if v == v else None


def _range(lo, hi):
    lo, hi = _num(lo), _num(hi)
    return None if lo is None or hi is None else (min(lo, hi), max(lo, hi))


def trade_signals(rows):
    """Trade engine_signals rows -> normalised signals (one per fired entry model)."""
    out = []
    for row in rows:
        payload = row.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        payload = payload or {}
        bar_end = _ts(payload.get("bar_end") or row.get("bar_ts"))
        for e in payload.get("entries") or []:
            if not isinstance(e, dict):
                continue
            a = e.get("area") or {}
            inv = e.get("invalidation")
            inv = inv.get("price") if isinstance(inv, dict) else inv
            out.append({"symbol": _instrument(row.get("symbol")), "bar_end": bar_end, "model": str(e.get("model")),
                        "key": None if e.get("key") is None else str(e.get("key")),
                        "timeframe": TF_KEYS.get(str(e.get("trigger_tf")), "15m"),
                        "side": AREA_SIDE.get(str(a.get("role"))) or DIRECTION_SIDE.get(e.get("direction")),
                        "area": _range(a.get("lo"), a.get("hi")), "area_id": None if a.get("id") is None else str(a.get("id")),
                        "area_state": None if a.get("state") is None else str(a.get("state")).lower(),
                        "invalidation": _num(inv), "at": _ts(row.get("computed_at")), "at_raw": row.get("computed_at")})
    return out


def atp_lines(lines):
    """ATP export lines -> (normalised signals, run records by (symbol, timeframe, bar END))."""
    signals, runs = [], {}
    for x in lines:
        if x.get("kind") == "signal":
            zone = x.get("entry_zone") or [None, None]
            signals.append({"symbol": _instrument(x.get("symbol")), "bar_end": _ts(x.get("bar_end")), "model": str(x.get("model_id")),
                            "key": None if x.get("instance_id") is None else str(x.get("instance_id")),
                            "timeframe": x.get("timeframe"), "side": x.get("side"), "area": _range(*zone[:2]),
                            "area_id": None if x.get("area_id") is None else str(x.get("area_id")),
                            "area_state": None if x.get("area_state") is None else str(x.get("area_state")).lower(),
                            "invalidation": _num(x.get("invalidation")), "at": _ts(x.get("written_at")), "at_raw": x.get("written_at")})
        elif x.get("kind") == "run":
            runs[(_instrument(x.get("symbol")), _ts(x.get("bar_end")))] = x
    return signals, runs


def _seconds(a, b):
    try:
        ta = dt.datetime.fromisoformat(str(a).replace("Z", "+00:00").replace(" ", "T", 1))
        tb = dt.datetime.fromisoformat(str(b).replace("Z", "+00:00").replace(" ", "T", 1))
    except (TypeError, ValueError):
        return None
    ta = ta.replace(tzinfo=IST) if ta.tzinfo is None else ta
    tb = tb.replace(tzinfo=IST) if tb.tzinfo is None else tb
    return round((tb - ta).total_seconds(), 1)


def _why(runs, s):
    run = runs.get((s["symbol"], s["bar_end"]))
    if run is None:
        return "no ATP run record of this bar"
    words = RUN_REASON.get(str(run.get("status")), f"ATP: {run.get('status')}")
    problems = [p for p in run.get("problems") or [] if p]
    return words + (f" ({', '.join(problems)})" if problems else "")


def compare(trade, atp, runs=None):
    """-> list of rows {status, symbol, bar_end, model, key, fields, reason, delay_s}, sorted by symbol / bar / model."""
    runs = runs or {}
    left = {(s["symbol"], s["bar_end"], s["model"], s["key"]): s for s in trade}
    right = {(s["symbol"], s["bar_end"], s["model"], s["key"]): s for s in atp}
    # a key the two sides name differently: match once by (symbol, bar, model) when that is unique on both sides
    loose_l = Counter(k[:3] for k in left)
    loose_r = Counter(k[:3] for k in right)
    for k in [k for k in left if k not in right and loose_l[k[:3]] == 1 and loose_r[k[:3]] == 1]:
        other = next(r for r in right if r[:3] == k[:3])
        if other not in left:
            right[k] = right.pop(other)
    out = []
    for k in sorted(set(left) | set(right), key=lambda k: tuple("" if v is None else str(v) for v in k)):
        a, b = left.get(k), right.get(k)
        row = {"symbol": k[0], "bar_end": k[1], "model": k[2], "key": k[3], "fields": [], "reason": "", "delay_s": None}
        if a and b:
            row["fields"] = [f for f in FIELDS if a.get(f) != b.get(f) and not (f == "area_state" and b.get(f) is None)]
            row["status"] = DIFFERENT if row["fields"] else SAME
            row["delay_s"] = _seconds(a.get("at_raw"), b.get("at_raw"))
            if b.get("key") != a.get("key"):
                row["fields"].append("key")
                row["status"] = DIFFERENT
        elif a:
            row["status"], row["reason"] = ONLY_TRADE, _why(runs, a)
        else:
            row["status"], row["reason"] = ONLY_ATP, "Trade has no such signal on this bar"
        out.append(row)
    return out


def summary(rows, runs=None):
    """Counts only (what may be said outside the host): per status, per differing field, per reason."""
    c = Counter(r["status"] for r in rows)
    fields = Counter(f for r in rows for f in r["fields"])
    reasons = Counter(r["reason"] for r in rows if r["reason"])
    delays = sorted(r["delay_s"] for r in rows if r["delay_s"] is not None)
    run_status = Counter(str(x.get("status")) for x in (runs or {}).values())
    return {"signals": len(rows), "same": c[SAME], "different": c[DIFFERENT], "only_trade": c[ONLY_TRADE], "only_atp": c[ONLY_ATP],
            "fields": dict(sorted(fields.items())), "reasons": dict(sorted(reasons.items())),
            "delay_s": None if not delays else {"min": delays[0], "median": delays[len(delays) // 2], "max": delays[-1]},
            "atp_runs": dict(sorted(run_status.items())), "result": "PASS" if c[SAME] == len(rows) else "DIFF"}


def markdown(day, rows, summ):
    lines = [f"# Shadow run {day}: ATP engine vs Trade engine", "",
             f"Result: **{summ['result']}** - {summ['signals']} signal(s): {summ['same']} same, {summ['different']} different, "
             f"{summ['only_trade']} only Trade, {summ['only_atp']} only ATP.", ""]
    if summ["delay_s"]:
        d = summ["delay_s"]
        lines += [f"ATP write time minus Trade's (seconds): min {d['min']}, median {d['median']}, max {d['max']}.", ""]
    if summ["atp_runs"]:
        lines += ["ATP run records: " + ", ".join(f"{k} {v}" for k, v in summ["atp_runs"].items()) + ".", ""]
    lines += ["| Status | Symbol | Bar end (IST) | Model | Differs in | Reason |", "|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] != SAME:
            lines.append(f"| {r['status']} | {r['symbol']} | {r['bar_end']} | {r['model']} | {', '.join(r['fields'])} | {r['reason']} |")
    return "\n".join(lines) + "\n"


def _jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run(trade_path, atp_path, day, out_dir):
    """Write `<out_dir>/shadow-<day>.md` and `.json`; return the summary (counts only)."""
    trade = [r for r in trade_signals(_jsonl(trade_path)) if r["bar_end"] and r["bar_end"][:10] == day]
    atp, runs = atp_lines(_jsonl(atp_path))
    atp = [r for r in atp if r["bar_end"] and r["bar_end"][:10] == day]
    runs = {k: v for k, v in runs.items() if k[1] and k[1][:10] == day}
    rows = compare(trade, atp, runs)
    summ = summary(rows, runs)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"shadow-{day}.md"), "w", encoding="utf-8") as fh:
        fh.write(markdown(day, rows, summ))
    with open(os.path.join(out_dir, f"shadow-{day}.json"), "w", encoding="utf-8") as fh:
        json.dump({"day": day, "summary": summ, "rows": rows}, fh, indent=1, default=str)
    return summ


def main(argv=None):
    p = argparse.ArgumentParser(description="Shadow run daily diff: ATP engine vs Trade engine (counts on stdout).")
    p.add_argument("--trade", required=True, help="Trade's day export (JSON lines)")
    p.add_argument("--atp", required=True, help="ATP's day export (JSON lines)")
    p.add_argument("--day", required=True, help="the IST day, YYYY-MM-DD")
    p.add_argument("--out", required=True, help="the private report folder on the host")
    a = p.parse_args(argv)
    summ = run(a.trade, a.atp, a.day, a.out)
    print(json.dumps({k: summ[k] for k in ("result", "signals", "same", "different", "only_trade", "only_atp")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
