"""Layer parity runner (owner order M79, W3; Trade order M65).

The build and the layer outputs are copied as is from Trade `scripts/reader_parity_export.py` at the snapshot commit
(engine-snapshot-v2, 813358bc1064645fcf2ca005959d9658804633e3): `_jsonable`, `build`, `out_layer<N>`, `_bars`, `_at`,
`EngineError`, the layer outputs ported so far and the JSON-lines line format of `write_jsonl`. Only the import paths differ (`atp_private.trade_engine.`).
The one part that is new here is reading a case's inputs back from the fixture CSV files (`load_case`).

    python -m atp_private.parity.runner --store "$ATP_PRIVATE_FIXTURES" --layer 1 [--case NIFTY_real ...]

The store holds `parity/engine-snapshot-v2/` exactly as trade-data has it (MANIFEST.json + 188 files, see the M79 W2
host command). Exit code 0 only if every case of every asked layer is byte-equal.
"""
import argparse
import contextlib
import gzip
import io
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

from atp_private import adapters

adapters.install()

SNAPSHOT = "engine-snapshot-v2"
COMMIT = "813358bc1064645fcf2ca005959d9658804633e3"
#: case name prefix -> (instrument, holdout-sealed dates?) as Trade's CASES (reader_parity_export.CASES).
CASE_SYMBOL = {"NIFTY": ("NIFTY", True), "BANKNIFTY": ("BANKNIFTY", False), "BANKNIFTY_live": ("BANKNIFTY", False),
               "SYNTH": ("NIFTY", False)}
FRAMES = ("m15", "m1", "ltf", "fut", "daily", "h1_pre15", "h1_pre5")
DATE_COLUMNS = ("timestamp", "bar_end")


# ------------------------------------------------------------------------------- copied from Trade (import paths only)
def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        return str(pd.Timestamp(x))
    if isinstance(x, (str, int, bool)) or x is None:
        return x
    if hasattr(x, "__dataclass_fields__"):
        return _jsonable({k: getattr(x, k) for k in x.__dataclass_fields__})
    return str(x)


def build(symbol, inp, sealed=True):
    import atp_private.trade_engine.instruments as INS
    from atp_private.trade_engine.decision3 import engine as E3
    from atp_private.trade_engine.decision3 import history as HI
    from atp_private.trade_engine.decision3 import levels as LV
    INS.set_current(symbol)
    kw = {"sealed": HI.sealed_fn(symbol) if sealed else None}
    if inp.get("ltf") is not None:
        kw["ltf"] = inp["ltf"]
    if inp.get("fut") is not None:
        kw["futures"] = inp["fut"]
    if inp.get("h1_pre15") is not None and len(inp["h1_pre15"]):          # BANKNIFTY_live: the 1H history as live builds it
        kw["h1_history"] = LV.h1_history(inp["h1_pre15"], symbol, finer=inp.get("h1_pre5"))
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        return E3.V22(inp["m15"], inp["m1"], inp["daily"], **kw)


def out_layer1(V):
    """The 15M swing pivots per degree (swings2), then SW: the Daily / Weekly external swings and per-TF states (SW1–SW3), then step ①
    on every 15M bar (the Daily side the reader uses: trend, resolution, protecting swing, band, notes)."""
    for d, ps in sorted(V.res["pivots"].items()):
        for p in sorted(ps, key=lambda p: (p.bar, p.kind)):
            yield {"degree": int(d), "kind": p.kind, "bar": int(p.bar), "ts": str(p.ts), "price": float(p.price),
                   "confirm_bar": int(p.confirm_bar), "known_at": str(p.known_at), "eq": bool(p.eq), "warmup": bool(p.warmup)}
    for tf, ext, states in (("D", "sw_daily_ext", "sw_daily"), ("W", "sw_weekly_ext", "sw_weekly")):
        if getattr(V, states, None) is None:
            continue
        for x in getattr(V, ext) or []:
            yield {"sw": tf, "external_swing": x}
        for x in getattr(V, states):
            yield {"sw": tf, "state": x}
    for t in _bars(V):
        ok, why, _st, ctx = _at(1, V, t, V.step1, t)
        yield {"bar": t, "ts": str(V.m15["timestamp"].iloc[t]), "step1": {"ok": ok, "why": why, "ctx": ctx}}


def _bars(V):
    return range(len(V.m15))


class EngineError(RuntimeError):
    """The engine raised on a bar: the export stops (no fixture ever records an error as the layer's output)."""


def _at(layer, V, t, fn, *a):
    try:
        return fn(*a)
    except Exception as exc:                                                # noqa: BLE001 — re-raised with the bar named
        raise EngineError(f"layer {layer}: the engine raised on bar {t} ({V.m15['timestamp'].iloc[t]}): "
                          f"{type(exc).__name__}: {exc}") from exc


def jsonl_line(r):
    """One line of Trade's write_jsonl."""
    return json.dumps(_jsonable(r), ensure_ascii=False, sort_keys=True) + "\n"


def out_layer2(V):
    """Every 15M bar's alive areas (levels.snapshot: band, tf, role, BREAK-2 state, far swing, Z facts, confluence), then every area
    object built in the window with its whole lifecycle (births, bands, events, flip facts, dead bar, Z, uid)."""
    for t in _bars(V):
        yield {"bar": t, "ts": str(V.m15["timestamp"].iloc[t]), "levels": V.levels.snapshot(t)}
    for L in V.levels.L:
        yield {"object": L}


def row15(V, t, layer=3):
    """V.decide(t), read once per bar and shared by layers 3, 5, 6 and the golden file (the engine is deterministic: a second read of
    the same bar is the same row)."""
    memo = V.__dict__.setdefault("_parity_rows15", {})
    if t not in memo:
        memo[t] = _at(layer, V, t, V.decide, t)
    return memo[t]


def out_layer3(V):
    for t in _bars(V):
        yield {"bar": t, "ts": str(V.m15["timestamp"].iloc[t]), "decide": row15(V, t)}


def out_layer4(V):
    from atp_private.trade_engine.decision3 import trendline as TL
    for t in _bars(V):
        rec = {"bar": t, "ts": str(V.m15["timestamp"].iloc[t])}
        for name, d in (("down", TL.DOWN), ("up", TL.UP)):
            ln = _at(4, V, t, TL.swing_line, V, t, d)
            rt = _at(4, V, t, TL.reaction_touch, V, t, d, ln) if ln is not None else None
            trend = "DOWN" if d == TL.DOWN else "UP"
            _, _, act = _at(4, V, t, V.step2, t, trend)
            lab = [{"id": x["id"], "lo": x["lo"], "hi": x["hi"], "confluence_label": x.get("confluence_label"),
                    "line_touch": x.get("line_touch")} for x in act if x.get("confluence_line")]
            rec[name] = {"line": ln, "reaction_touch": rt, "confluence": lab}
        yield rec


def _found(x, keys, path=""):
    """Every value under one of `keys` anywhere inside x, with its path (the RSI facts the entry models attached to their reads)."""
    if isinstance(x, dict):
        for k, v in x.items():
            p = f"{path}.{k}" if path else str(k)
            if k in keys:
                yield p, v
            else:
                yield from _found(v, keys, p)
    elif isinstance(x, (list, tuple)):
        for i, v in enumerate(x):
            yield from _found(v, keys, f"{path}[{i}]")


def out_layer5(V):
    """C (RSI): rsi2's facts at every 15M bar (the RSI value, per degree and side the latest pair, divergence or the absence statement),
    then every RSI read the decision row carries (zone read, entries, armed visits, WATCH) with its path in the row."""
    V.rsi_divergence(0, -1, 0)                                              # builds the engine's own rsi2 reader (V._rsi), pure
    rs = V._rsi
    for t in _bars(V):
        rec = {"bar": t, "ts": str(V.m15["timestamp"].iloc[t])}
        rec["rsi2"] = rs if isinstance(rs, str) else _at(5, V, t, rs.read, t)
        rec["reads"] = dict(_found(row15(V, t, 5), ("rsi", "rsi_divergence")))
        yield rec


# ------------------------------------------------------------------------------- ATP side
OUTPUTS = {1: out_layer1, 2: out_layer2, 3: out_layer3, 4: out_layer4, 5: out_layer5}


def snapshot_root(store):
    return os.path.join(store, "parity", SNAPSHOT)


def cases(root):
    return list(json.load(open(os.path.join(root, "MANIFEST.json"), encoding="utf-8"))["cases"])


def case_symbol(name):
    base = name.rsplit("_", 1)[0]
    return CASE_SYMBOL[base]


def load_case(root, name):
    """A case's input frames, read back from the fixture CSV files (timestamp / bar_end parsed as datetimes)."""
    folder = os.path.join(root, "inputs", name)
    inp = {k: None for k in FRAMES}
    for k in FRAMES:
        path = os.path.join(folder, f"{k}.csv.gz")
        if os.path.exists(path):
            df = pd.read_csv(path, float_precision="round_trip")   # exact floats (the default parser may be 1 ulp off)
            for c in DATE_COLUMNS:
                if c in df:
                    df[c] = pd.to_datetime(df[c])
            inp[k] = df
    return inp


def compare_case(root, layer, name, V=None):
    """Stream the produced lines against the expected file. Returns a dict: equal, expected / produced line counts, the
    first differing line number (or None), settings equal. `V` may be a case build shared by several layers."""
    if V is None:
        V = build_case(root, name)
    with open(os.path.join(root, "inputs", name, "settings.json"), encoding="utf-8") as f:
        settings_ok = f.read() == json.dumps(_jsonable(dict(getattr(V, "s", None) or {})), ensure_ascii=False, indent=1,
                                             sort_keys=True)
    n_exp = n_got = 0
    first = None
    produced = OUTPUTS[layer](V)
    with gzip.open(os.path.join(root, "outputs", f"layer{layer}", f"{name}.jsonl.gz"), "rb") as f:
        for raw in f:
            n_exp += 1
            line = next(produced, None)
            if line is None:
                first = first or n_exp
                continue
            n_got += 1
            if first is None and jsonl_line(line).encode("utf-8") != raw:
                first = n_exp
    for _ in produced:
        n_got += 1
        first = first or n_exp + 1
    return {"equal": first is None and n_exp == n_got, "expected": n_exp, "produced": n_got, "first_diff": first,
            "settings_equal": settings_ok}


def build_case(root, name):
    symbol, sealed = case_symbol(name)
    return build(symbol, load_case(root, name), sealed=sealed)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", default=os.environ.get("ATP_PRIVATE_FIXTURES"))
    ap.add_argument("--layer", type=int, action="append", required=True)
    ap.add_argument("--case", action="append")
    a = ap.parse_args(argv)
    if not a.store:
        ap.error("--store or ATP_PRIVATE_FIXTURES is needed")
    root = snapshot_root(a.store)
    layers = sorted(set(a.layer))
    names = a.case or cases(root)
    equal = {n: 0 for n in layers}
    for name in names:
        V = build_case(root, name)                                          # one build per case for every layer (as Trade's export)
        for layer in layers:
            r = compare_case(root, layer, name, V)
            equal[layer] += r["equal"]
            print(f"layer {layer} {name}: {'EQUAL' if r['equal'] else 'DIFF'} lines expected {r['expected']} produced "
                  f"{r['produced']}{'' if r['first_diff'] is None else ' first diff line ' + str(r['first_diff'])} settings "
                  f"{'equal' if r['settings_equal'] else 'DIFF'}", flush=True)
    for layer in layers:
        print(f"layer {layer}: {equal[layer]} / {len(names)} cases byte-equal", flush=True)
    ok_all = all(equal[n] == len(names) for n in layers)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
