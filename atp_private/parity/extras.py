"""Snapshot comparisons beside the six layers (owner order M79, W3; Trade order M65 X-4): golden, answer_key_v4,
trigger_5m, real_days.

What each file of `parity/engine-snapshot-v2/` holds and how Trade wrote it is copied as is from Trade at the snapshot commit
(engine-snapshot-v2, 813358bc1064645fcf2ca005959d9658804633e3): `scripts/reader_parity_export.py` (`GOLDEN`, `golden`, `gz_text`,
`write_jsonl`), `scripts/export_engine_snapshot.py` (`_rows`, `_spread`, `DAY_CLASSES`, `DAY_RULE`, the reading part of `_ak_run`,
`classify_days`, `pick_days`, `write_days`) and `scripts/export_parity_fixtures.py` (the reading part of `chart_cases`). Only the
import paths differ (`atp_private.trade_engine.`). New here, the ATP side only:
- inputs are read back from the fixture CSV files (Trade loaded them from its market-data folders, then wrote those CSV files);
- `write_days` reads the layer 1 / 2 / 6 rows THIS engine produced (written to a temporary folder), never the fixture's own rows;
- each produced file is compared byte for byte with the fixture file (gzip files: their decompressed text).

    python -m atp_private.parity.extras --store "$ATP_PRIVATE_FIXTURES" --what golden --what answer_key_v4 \
        --what trigger_5m --what real_days

Exit code 0 only if every compared file / case is equal.
"""
import argparse
import contextlib
import gzip
import io
import json
import os
import shutil
import sys
import tempfile

import pandas as pd

from atp_private.parity import runner as R

WHAT = ("golden", "answer_key_v4", "trigger_5m", "real_days")
TRIGGER_DIR, DAYS_DIR = "trigger_5m", "real_days"                         # the folder names export_parity_fixtures.export sets


# ------------------------------------------------------------------------------- copied from Trade (import paths only)
GOLDEN = {"2026-10-12": "bear call at the 1H supply (fast-form handover, 5M CHoCH, commitment volume above the approach-leg average; "
                        "the 09:15 turn at the descending line ⇒ \"confluence: line\")",
          "2026-10-13": "no bear call (no handover)",
          "2026-09-29": "no entry (FUT volume missing)"}


def golden(V):
    import numpy as np
    out = {}
    ts = pd.to_datetime(V.m15["timestamp"])
    for day, what in GOLDEN.items():
        ix = [int(i) for i in np.flatnonzero((ts.dt.normalize() == pd.Timestamp(day)).to_numpy())]
        rows = []
        for t in ix:
            r = R.row15(V, t, "golden")
            rows.append({"bar": t, "ts": str(ts.iloc[t]), "decision": r.get("decision"), "why": r.get("why"),
                         "conviction": r.get("conviction")})
        out[day] = {"expected (Abhi)": what, "bars": rows}
        F = V.trigger_frame() if hasattr(V, "trigger_frame") else None
        if F is not None and F.n:                                           # the live path (5M trigger) on the same day
            b5 = []
            for j in range(F.n):
                if pd.Timestamp(F.T(j)).normalize() != pd.Timestamp(day):
                    continue
                r = R._at("golden", V, int(F.k_of[j]) if F.k_of[j] >= 0 else 0, V.decide5, j)
                b5.append({"bar5": j, "ts": str(F.T(j)), "decision": r.get("decision"), "why": r.get("why"), "mark": r.get("mark"),
                           "entries": [{k: e.get(k) for k in ("model", "side", "object", "entry_ref", "invalidation", "invalidation_rule", "trigger_ts")
                                        if k in e}
                                       for e in r.get("entries") or []],
                           "watch": len(r.get("watch_alerts") or [])})
            out[day]["bars5"] = b5
    return out


@contextlib.contextmanager
def gz_text(path):
    """A gzip text writer with no time stamp and no file name in its header: the same content ⇒ the same bytes (sha256) on every run."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz, \
            io.TextIOWrapper(gz, encoding="utf-8", newline="") as f:
        yield f


def write_jsonl(rows, path):
    with gz_text(path) as f:
        for r in rows:
            f.write(json.dumps(R._jsonable(r), ensure_ascii=False, sort_keys=True) + "\n")


DAY_CLASSES = (("trend", 4), ("range", 3), ("correction", 3))           # 10 days per index
DAY_RULE = ("per index (NIFTY_real, BANKNIFTY_live_real): a day with a full 15M session and 5M candles; class by the engine's own step ① "
            "at the day's last 15M bar — Daily side UP / DOWN and the day's close − open in that direction = trend, against it = "
            "correction; RANGE / TRANSITION = range; 4 trend + 3 range + 3 correction, evenly spaced in time inside each class, a class "
            "short of days filled from the others (fixture selection only, never a reading rule)")
DAY_CASES = {"NIFTY": "NIFTY_real", "BANKNIFTY": "BANKNIFTY_live_real"}


def _rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for ln in f:
            yield json.loads(ln)


def _spread(xs, k):
    if len(xs) <= k:
        return list(xs)
    return [xs[round(i * (len(xs) - 1) / (k - 1))] for i in range(k)] if k > 1 else [xs[0]]


def ak_reading(it, inp):
    """The reading part of Trade's `_ak_run` (one answer-key item, the guard's own build: 5M LTF, no FUT): what the engine reads about
    the owner's object at the window end. `inp` = the item's inputs (Trade: banknifty_live_inputs; here: read back from the fixture)."""
    from atp_private.trade_engine.tests import test_answer_key_v4 as AK
    V = R.build("BANKNIFTY", inp, sealed=False)
    lo, hi = it["object"]["lo"], it["object"]["hi"]
    tf = next(v for k, v in AK.TFW.items() if it["object"]["tf_band"].startswith(k))
    cands = [Lv for Lv in V.levels.L if Lv.tf == tf and (abs(Lv.bands[0][1] - lo) < 1.0 or abs(Lv.bands[0][2] - hi) < 1.0)
             and Lv.bands[0][1] <= lo + 1.0 and Lv.bands[0][2] >= hi - 1.0]       # the guard's own object match
    t = len(V.levels.ts) - 1
    ts = V.levels.ts
    out = {"item": it, "build": "tests/test_answer_key_v4._read (window end = the last session ≤ the item's window end)",
           "last_bar": t, "last_ts": str(ts.iloc[t]),
           "objects": [{"uid": Lv.uid, "id": Lv.id, "tf": Lv.tf, "role0": Lv.role0, "role_at_end": Lv.role_at(t),
                        "state_at_end": Lv.state_at(t), "dead_bar": Lv.dead_bar,
                        "events": [{"bar": int(b), "ts": str(ts.iloc[b]), "kind": k, "detail": x} for b, k, x in Lv.events],
                        "level": Lv} for Lv in cands],
           "snapshot_at_end": V.levels.snapshot(t), "decide_at_end": R.row15(V, t, "answer_key")}
    return json.dumps(R._jsonable(out), ensure_ascii=False, indent=1, sort_keys=True)


def chart_case_reads(case, df):
    """The reading part of Trade's `chart_cases` for one window case: market_state.read at every window bar / checkpoint, on the
    case's 1m slice (`df`, the fixture's m1.csv.gz)."""
    from atp_private.trade_engine import market_state as MS
    w = case["window"]
    at = list(pd.date_range(w["from"], w["to"], freq=f"{int(w.get('step_min', 15))}min"))
    at += [pd.Timestamp(cp["at"]) for cp in case.get("checkpoints") or []]
    return ({"asof": str(t), "market_state": MS.read(df, t)} for t in sorted(set(at)))


def classify_days(l1, l6_path):
    """From the case's layer-1 step ① rows: the day's last 15M row and its 15M bar count; from layer 6 (one streamed pass): the days
    with 5M candles."""
    by_day, m15n, have5 = {}, {}, set()
    for r in l1:
        if "step1" in r:
            day = r["ts"][:10]
            by_day[day] = r                                                  # the day's LAST 15M bar wins
            m15n[day] = m15n.get(day, 0) + 1
    for r in _rows(l6_path):
        if r.get("tf") == "5M":
            have5.add(str(r["decide5"].get("ts"))[:10])
    return by_day, m15n, have5


def pick_days(by_day, m15n, have5, oc):
    full = max(m15n.values()) if m15n else 0
    cls = {}
    for day, r in sorted(by_day.items()):
        if m15n[day] < full or day not in have5 or day not in oc:
            continue
        ctx = r["step1"]["ctx"] or {}
        side = ctx.get("daily_trend") or ctx.get("trend")
        o, c = oc[day]
        if side in ("UP", "DOWN"):
            cls[day] = "trend" if (c - o) * (1 if side == "UP" else -1) > 0 else "correction"
        elif side in ("RANGE", "TRANSITION"):
            cls[day] = "range"
    chosen = {}
    for name, k in DAY_CLASSES:
        for d in _spread([d for d, c in sorted(cls.items()) if c == name], k):
            chosen[d] = name
    want = sum(k for _, k in DAY_CLASSES)
    rest = [d for d in sorted(cls) if d not in chosen]
    if len(chosen) < want:
        for d in _spread(rest, want - len(chosen)):
            chosen[d] = cls[d]
    return dict(sorted(chosen.items()))


def write_days(root, index, cname):
    out = os.path.join(root, "outputs")
    l1 = list(_rows(os.path.join(out, "layer1", f"{cname}.jsonl.gz")))
    l6p = os.path.join(out, "layer6", f"{cname}.jsonl.gz")
    m15 = pd.read_csv(os.path.join(root, "inputs", cname, "m15.csv.gz"))
    m15["day"] = m15["timestamp"].astype(str).str[:10]
    oc = {d: (float(g["open"].iloc[0]), float(g["close"].iloc[-1])) for d, g in m15.groupby("day")}
    days = pick_days(*classify_days(l1, l6p), oc)
    last = {day: max(r["bar"] for r in l1 if "step1" in r and r["ts"][:10] == day) for day in days}
    snaps = {r["bar"]: r for r in _rows(os.path.join(out, "layer2", f"{cname}.jsonl.gz")) if r.get("bar") in set(last.values())}
    v15, d5 = {d: [] for d in days}, {d: [] for d in days}
    for r in _rows(l6p):
        day = r["ts"][:10] if r.get("tf") == "15M" else str(r["decide5"].get("ts"))[:10]
        if day in days:
            (v15 if r.get("tf") == "15M" else d5)[day].append(r)
    piv = [r for r in l1 if "degree" in r]
    for day, kind in days.items():
        end = pd.Timestamp(day) + pd.Timedelta(days=1)
        rec = {"index": index, "case": cname, "day": day, "class": kind, "rule": DAY_RULE,
               "daily_side": [r for r in l1 if "step1" in r and r["ts"][:10] == day],
               "swings_known_by_close": [p for p in piv if pd.Timestamp(p["known_at"]) < end],
               "areas_at_close": snaps[last[day]], "verdicts_15m": v15[day], "decisions_5m": d5[day]}
        p = os.path.join(root, DAYS_DIR, index, f"{day}.json.gz")
        with gz_text(p) as f:                                               # deterministic bytes (no gzip time stamp / name)
            json.dump(rec, f, ensure_ascii=False, indent=1, sort_keys=True)
    return days


# ------------------------------------------------------------------------------- ATP side: the comparisons
def _manifest(root):
    with open(os.path.join(root, "MANIFEST.json"), encoding="utf-8") as f:
        return json.load(f)


def _gz_equal(produced, expected):
    """Two gzip files hold the same text (streamed, 1 MB at a time)."""
    with gzip.open(produced, "rb") as a, gzip.open(expected, "rb") as b:
        while True:
            x, y = a.read(1 << 20), b.read(1 << 20)
            if x != y:
                return False
            if not x:
                return True


def compare_golden(root, V=None):
    """golden/golden.json (NIFTY_real, 15M and 5M on the golden days). Returns {"golden.json": equal}."""
    V = V or R.build_case(root, "NIFTY_real")
    produced = json.dumps(R._jsonable(golden(V)), ensure_ascii=False, indent=1, sort_keys=True)
    with open(os.path.join(root, "golden", "golden.json"), encoding="utf-8") as f:
        return {"golden.json": produced == f.read()}


def compare_chart_case(root, cid):
    """golden/chart_cases/<id>/market_state.jsonl.gz: market_state.read on every window bar / checkpoint, line by line."""
    d = os.path.join(root, "golden", "chart_cases", cid)
    with open(os.path.join(d, "case.json"), encoding="utf-8") as f:
        case = json.load(f)
    df = pd.read_csv(os.path.join(d, "m1.csv.gz"), parse_dates=["timestamp"], float_precision="round_trip")
    produced = chart_case_reads(case, df)
    n_exp = n_got = 0
    first = None
    with gzip.open(os.path.join(d, "market_state.jsonl.gz"), "rb") as f:
        for raw in f:
            n_exp += 1
            line = next(produced, None)
            if line is None:
                first = first or n_exp
                continue
            n_got += 1
            if first is None and R.jsonl_line(line).encode("utf-8") != raw:
                first = n_exp
    for _ in produced:
        n_got += 1
        first = first or n_exp + 1
    return {"equal": first is None and n_exp == n_got, "expected": n_exp, "produced": n_got, "first_diff": first}


def ak_inputs(root, item_id):
    folder = os.path.join(root, "answer_key_v4", item_id, "inputs")
    inp = {k: None for k in R.FRAMES}
    for k in R.FRAMES:
        path = os.path.join(folder, f"{k}.csv.gz")
        if os.path.exists(path):
            df = pd.read_csv(path, float_precision="round_trip")
            for c in R.DATE_COLUMNS:
                if c in df:
                    df[c] = pd.to_datetime(df[c])
            inp[k] = df
    return inp


def compare_answer_key(root, item_id):
    """answer_key_v4/<id>/reading.json, built on the item's own inputs."""
    with open(os.path.join(root, "answer_key_v4", "items.json"), encoding="utf-8") as f:
        it = next(x for x in json.load(f) if x["id"] == item_id)
    produced = ak_reading(it, ak_inputs(root, item_id))
    with open(os.path.join(root, "answer_key_v4", item_id, "reading.json"), encoding="utf-8") as f:
        return produced == f.read()


def trigger_cases(root):
    with open(os.path.join(root, TRIGGER_DIR, "cases.json"), encoding="utf-8") as f:
        return json.load(f)["cases"]


def _canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def compare_trigger(V, case):
    """One trigger_5m case: V.decide5(bar5) on a build of inputs/<case>/ equals the case's decide5 (as the fixture's `how` says),
    and its ts / kind / models read the same."""
    d5 = json.loads(R.jsonl_line(V.decide5(case["bar5"])))                 # the layer-6 line, read back (as Trade read it)
    kind = "fired" if (d5.get("entries") or d5.get("watch_alerts")) else "armed"
    models = sorted({e.get("model") for e in (d5.get("entries") or []) + (d5.get("watch_alerts") or []) if e.get("model")})
    return {"decide5": _canon(d5) == _canon(case["decide5"]), "ts": d5.get("ts") == case["ts"], "kind": kind == case["kind"],
            "models": models == case["models"]}


def compare_real_days(root, index, V=None, work=None):
    """real_days/<index>/<day>.json.gz: this engine's layer 1 / 2 / 6 rows of the index's case, written to a temporary folder,
    then Trade's own write_days on them. Returns {"days": chosen days equal to the MANIFEST, "<day>": file equal, ...}."""
    cname = DAY_CASES[index]
    V = V or R.build_case(root, cname)
    tmp = tempfile.mkdtemp(prefix="m79-days-", dir=work)
    try:
        os.makedirs(os.path.join(tmp, "inputs"))
        os.symlink(os.path.join(root, "inputs", cname), os.path.join(tmp, "inputs", cname))
        for n in (1, 2, 6):
            write_jsonl(R.OUTPUTS[n](V), os.path.join(tmp, "outputs", f"layer{n}", f"{cname}.jsonl.gz"))
        days = write_days(tmp, index, cname)
        res = {"days": days == _manifest(root)["days"][index]}
        want = sorted(f[:-len(".json.gz")] for f in os.listdir(os.path.join(root, DAYS_DIR, index)))
        res["files"] = sorted(days) == want
        for day in want:
            p = os.path.join(tmp, DAYS_DIR, index, f"{day}.json.gz")
            res[day] = os.path.exists(p) and _gz_equal(p, os.path.join(root, DAYS_DIR, index, f"{day}.json.gz"))
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=os.environ.get("ATP_PRIVATE_FIXTURES"))
    ap.add_argument("--what", action="append", choices=WHAT, required=True)
    ap.add_argument("--work", default=None, help="folder for the temporary real_days layer files (default: the system temp)")
    a = ap.parse_args(argv)
    if not a.store:
        ap.error("--store or ATP_PRIVATE_FIXTURES is needed")
    root = R.snapshot_root(a.store)
    man = _manifest(root)
    what = set(a.what)
    tally = {}
    builds = {}

    def V_of(cname):                                                        # one build per case, shared by the comparisons
        if cname not in builds:
            builds.clear()                                                  # keep one engine build in memory at a time
            builds[cname] = R.build_case(root, cname)
        return builds[cname]

    def put(name, ok, note=""):
        e, t = tally.get(name, (0, 0))
        tally[name] = (e + bool(ok), t + 1)
        print(f"{name} {note}: {'EQUAL' if ok else 'DIFF'}", flush=True)

    if "golden" in what:
        put("golden", compare_golden(root, V_of("NIFTY_real"))["golden.json"], "golden.json")
    if "real_days" in what and "NIFTY" in man["days"]:
        for k, v in compare_real_days(root, "NIFTY", V_of("NIFTY_real"), a.work).items():
            put("real_days", v, f"NIFTY {k}")
    bn_days_done = False
    if "trigger_5m" in what:
        by_case = {}
        for c in trigger_cases(root):
            by_case.setdefault(c["case"], []).append(c)
        order = sorted(by_case, key=lambda c: (c != "NIFTY_real", c))       # NIFTY_real first: its build is already in memory
        for cname in order:
            for c in by_case[cname]:
                r = compare_trigger(V_of(cname), c)
                put("trigger_5m", all(r.values()), f"#{c['n']} {cname} bar5 {c['bar5']} {r}")
            if cname == "BANKNIFTY_live_real" and "real_days" in what:  # while its build is in memory
                for k, v in compare_real_days(root, "BANKNIFTY", V_of(cname), a.work).items():
                    put("real_days", v, f"BANKNIFTY {k}")
                bn_days_done = True
    if "real_days" in what and not bn_days_done:
        for k, v in compare_real_days(root, "BANKNIFTY", V_of("BANKNIFTY_live_real"), a.work).items():
            put("real_days", v, f"BANKNIFTY {k}")
    builds.clear()
    if "golden" in what:
        for cid in man["golden_chart_cases"]:
            r = compare_chart_case(root, cid)
            put("golden", r["equal"], f"chart case {cid} {r}")
    if "answer_key_v4" in what:
        for item_id in man["answer_key_v4"]:
            put("answer_key_v4", compare_answer_key(root, item_id), item_id)
    for name, (e, t) in tally.items():
        print(f"{name}: {e} / {t} equal", flush=True)
    return 0 if all(e == t for e, t in tally.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
