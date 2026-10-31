"""BANKNIFTY replay inputs for the private-data guard tests (skip without trade-data) (read-only, local trade-data). Raw series as the live feed would return them (Upstox spot 15m/5m/1m, near-month
FUT 5M with volume, Upstox Daily). Nothing is filled: a missing session stays missing (listed by gaps())."""
import glob
import os

import pandas as pd

TD = os.environ.get("TRADE_DATA", "/home/user/trade-data")
BN = f"{TD}/banknifty"


def _naive(s):
    t = pd.to_datetime(s)
    if getattr(t.dt, "tz", None) is not None:
        t = t.dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return t.astype("datetime64[ns]")


def _rd(p):
    d = pd.read_parquet(p) if p.endswith(".parquet") else pd.read_csv(p)
    d["timestamp"] = _naive(d["timestamp"])
    return d


def _merge(frames):
    """Older sources first, later wins on the same bar start (the Upstox export is passed last = the live source)."""
    fr = [f.assign(_k=k) for k, f in enumerate(frames) if f is not None and len(f)]
    d = pd.concat(fr, ignore_index=True).sort_values(["timestamp", "_k"]).drop_duplicates("timestamp", keep="last")
    return d.drop(columns="_k").reset_index(drop=True)


def latest(sub):
    xs = sorted(glob.glob(f"{BN}/{sub}/*/"))
    return xs[-1] if xs else None


def load():
    """{m15, m5, m1, fut, daily_hist, notes, sources}."""
    sp, vh = latest("vps_spot_history"), latest("vps_history")
    notes, src = [], {}
    cols = ["timestamp", "open", "high", "low", "close"]
    # spot 15M: Upstox 15m export (live source = Upstox 15minute). Older trade-data 15M only where the export has no bar (none expected).
    old15 = _rd(f"{BN}/BANKNIFTY_15M.csv.gz")[cols]
    up15 = _rd(f"{sp}BANKNIFTY_15m.csv.gz")[cols] if sp else None
    m15 = _merge([old15, up15])
    src["m15"] = [f"{BN}/BANKNIFTY_15M.csv.gz", f"{sp}BANKNIFTY_15m.csv.gz"]
    # spot 5M: Upstox 5m export (live: Upstox 5minute); VPS oe_index 5M only for days the export lacks (no 15M there ⇒ no decision anyway)
    up5 = _rd(f"{sp}BANKNIFTY_5m.csv.gz")[cols] if sp else None
    oe5 = _rd(f"{vh}BANKNIFTY_5M.csv.gz")[cols] if vh else None
    m5 = _merge([oe5, up5])
    src["m5"] = [f"{vh}BANKNIFTY_5M.csv.gz", f"{sp}BANKNIFTY_5m.csv.gz"]
    up1 = _rd(f"{sp}BANKNIFTY_1m.csv.gz")[cols] if sp else None
    vc1 = _rd(f"{vh}BANKNIFTY_1M.csv.gz")[cols] if vh else None
    m1 = _merge([vc1, up1])
    src["m1"] = [f"{vh}BANKNIFTY_1M.csv.gz", f"{sp}BANKNIFTY_1m.csv.gz"]
    # FUT 5M near-month (with volume + contract)
    fr = []
    for p in [f"{TD}/futures_volume/oe_futures_5min_BANKNIFTY.parquet", f"{TD}/live_export/2026-10-13-fut45/oe_futures_5min_BANKNIFTY.parquet",
              f"{vh}BANKNIFTY_FUT_5M.csv.gz" if vh else None]:
        if p and os.path.exists(p):
            fr.append(_rd(p)[["timestamp", "open", "high", "low", "close", "volume", "contract"]])
    fut = _merge(fr)
    src["fut"] = [p for p in [f"{TD}/futures_volume/oe_futures_5min_BANKNIFTY.parquet",
                              f"{TD}/live_export/2026-10-13-fut45/oe_futures_5min_BANKNIFTY.parquet", f"{vh}BANKNIFTY_FUT_5M.csv.gz"]]
    from atp_private.trade_engine.legs2 import volume as LVOL
    fut["expiry"] = LVOL.expiry_of(fut)
    # Daily (Upstox Daily as live's feed.index(day)): 2015-2024 csv + Upstox D (to its last day); days after it from the 15M (complete days)
    from atp_private.trade_engine.decision3 import history as HI
    dh = _merge([HI._ohlc_daily(HI._read(p)) for p in sorted(glob.glob(f"{BN}/BANKNIFTY_daily_*.csv")) + sorted(glob.glob(f"{BN}/BANKNIFTY_D.csv*"))])
    dh = dh.drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    g = m15.assign(day=m15["timestamp"].dt.normalize()).groupby("day").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), n=("close", "size")).reset_index()
    g = g[(g["n"] == 25) & (g["day"] > dh["timestamp"].max())].rename(columns={"day": "timestamp"}).drop(columns="n")
    daily = pd.concat([dh, g], ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    notes.append(f"Daily: Upstox D to {dh['timestamp'].max().date()}, then {len(g)} days from complete 15M sessions")
    src["daily"] = sorted(glob.glob(f"{BN}/BANKNIFTY_daily_*.csv")) + sorted(glob.glob(f"{BN}/BANKNIFTY_D.csv*"))
    return {"m15": m15, "m5": m5, "m1": m1, "fut": fut, "daily": daily, "notes": notes, "sources": src,
            "conflicts": conflicts(old15, up15)}


def conflicts(a, b):
    if a is None or b is None:
        return {}
    j = a.merge(b, on="timestamp", suffixes=("_a", "_b"))
    diff = j[(abs(j["close_a"] - j["close_b"]) > 0.05) | (abs(j["high_a"] - j["high_b"]) > 0.05) | (abs(j["low_a"] - j["low_b"]) > 0.05)]
    return {"m15_overlap_bars": int(len(j)), "m15_bars_differing": int(len(diff)),
            "examples": diff.head(5).astype(str).to_dict("records")}
