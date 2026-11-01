"""M79 W10: the shadow run's daily diff (atp_private/shadow/diff.py) and Trade's day export, on made-up rows only."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from atp_private.shadow import diff as D

ROOT = Path(__file__).resolve().parents[1]
DAY = "2030-01-07"


def trade_row(bar="2030-01-07 10:00:00", entries=None, at="2030-01-07 10:00:04"):
    entries = entries if entries is not None else [{"model": "E1", "key": "k1", "trigger_tf": "5M",
                                                     "area": {"id": "a1", "role": "support", "lo": 101.0, "hi": 100.0, "state": "ACTIVE"},
                                                     "invalidation": {"price": 99.5, "rule": "x"}}]
    return {"symbol": "NIFTY", "bar_ts": bar, "computed_at": at, "decision": "x",
            "payload": json.dumps({"bar_end": bar, "entries": entries})}


def atp_signal(**kw):
    x = {"kind": "signal", "symbol": "NIFTY", "timeframe": "5m", "bar_end": "2030-01-07T10:00:00+05:30", "model_id": "E1",
         "instance_id": "k1", "side": "buyer", "area_id": "a1", "area_state": "active", "entry_zone": [100.0, 101.0],
         "invalidation": 99.5, "written_at": "2030-01-07T04:30:07+00:00"}
    x.update(kw)
    return x


def test_same_signal_is_same_with_its_delay():
    rows = D.compare(D.trade_signals([trade_row()]), D.atp_lines([atp_signal()])[0])
    assert [r["status"] for r in rows] == [D.SAME] and rows[0]["delay_s"] == 3.0
    assert D.summary(rows)["result"] == "PASS"


def test_a_differing_area_is_named():
    rows = D.compare(D.trade_signals([trade_row()]), D.atp_lines([atp_signal(entry_zone=[100.0, 102.0], area_state="broken")])[0])
    assert rows[0]["status"] == D.DIFFERENT and rows[0]["fields"] == ["area", "area_state"]


def test_only_trade_takes_the_atp_run_reason():
    signals, runs = D.atp_lines([{"kind": "run", "symbol": "NSE_INDEX:Nifty 50", "timeframe": "5m",
                                  "bar_end": "2030-01-07T10:00:00+05:30", "status": "data_gap", "problems": ["missing_bars:15m"]}])
    rows = D.compare(D.trade_signals([trade_row()]), signals, runs)
    assert rows[0]["status"] == D.ONLY_TRADE and rows[0]["reason"] == "ATP: data gap on this bar (missing_bars:15m)"
    rows = D.compare(D.trade_signals([trade_row()]), [], {})
    assert rows[0]["reason"] == "no ATP run record of this bar"


def test_only_atp_and_a_renamed_key_matches_once():
    rows = D.compare([], D.atp_lines([atp_signal()])[0])
    assert rows[0]["status"] == D.ONLY_ATP
    rows = D.compare(D.trade_signals([trade_row()]), D.atp_lines([atp_signal(instance_id="other")])[0])
    assert len(rows) == 1 and rows[0]["status"] == D.DIFFERENT and rows[0]["fields"] == ["key"]


def test_a_bar_without_entries_gives_no_signal():
    assert D.trade_signals([trade_row(entries=[])]) == []


def test_run_writes_the_report_and_prints_counts_only(tmp_path):
    t, a = tmp_path / "t.jsonl", tmp_path / "a.jsonl"
    t.write_text(json.dumps(trade_row()) + "\n" + json.dumps(trade_row(bar="2030-01-08 10:00:00")) + "\n")
    a.write_text(json.dumps(atp_signal()) + "\n")
    summ = D.run(str(t), str(a), DAY, str(tmp_path / "out"))
    assert summ["signals"] == 1 and summ["same"] == 1                     # the other day is left out
    assert (tmp_path / "out" / f"shadow-{DAY}.md").read_text().startswith(f"# Shadow run {DAY}")


def test_trade_export_reads_one_day_read_only(tmp_path):
    db = tmp_path / "engine_signals.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE engine_signals (symbol TEXT, bar_ts TEXT, computed_at TEXT, decision TEXT, payload TEXT, "
                "PRIMARY KEY (symbol, bar_ts))")
    for r in (trade_row(), trade_row(bar="2030-01-08 10:00:00")):
        con.execute("INSERT INTO engine_signals VALUES (?, ?, ?, ?, ?)", (r["symbol"], r["bar_ts"], r["computed_at"], r["decision"], r["payload"]))
    con.commit()
    con.close()
    out = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "shadow" / "trade_export.py"), "--db", str(db), "--day", DAY],
                         capture_output=True, text=True, check=True)
    lines = [json.loads(x) for x in out.stdout.splitlines()]
    assert [x["bar_ts"] for x in lines] == ["2030-01-07 10:00:00"] and "1 row(s)" in out.stderr


def test_trade_compaction_and_the_atp_shim_normalise_to_the_same_signal():
    """The same raw engine entry through Trade's own row compaction and through the shim's mapping (as ATP's runner
    stores it) compares as `same` - the diff measures the engines, not the two formats."""
    import os
    import pytest
    if not os.environ.get("ATP_BACKEND"):
        pytest.skip("ATP_BACKEND not set: ATP's backend (the provider contract) is needed")
    sys.path.insert(0, os.environ["ATP_BACKEND"])
    from atp_private.trade_engine import engine3_live as L
    from atp_private.trade_engine import provider as PV
    raw = {"model": "E2", "key": "v1:E2", "trigger_tf": "5M", "direction": 1, "invalidation": 99.25, "invalidation_rule": "r",
           "area": {"id": "z9", "tf": "15M", "role": "support", "lo": 100.5, "hi": 101.5, "state": "ACTIVE"},
           "evidence_list": {"confirming": {"x": "present"}, "context": {}}}
    r = {"bar_end": "2030-01-07 10:00:00", "trend_used": "UP", "entries": [raw]}
    trade = {"symbol": "NIFTY", "bar_ts": r["bar_end"], "computed_at": "2030-01-07 10:00:04",
             "payload": json.dumps({"bar_end": r["bar_end"], "entries": L.compact_entries([raw])})}
    s = PV.Provider()._signal("NIFTY", r, raw)
    atp = atp_signal(model_id=s.model_id, instance_id=s.instance_id, side=s.side, area_id=s.area_id, timeframe=s.timeframe,
                     entry_zone=[s.entry_zone.low, s.entry_zone.high], invalidation=s.invalidation,
                     bar_end=s.bar_end.isoformat())
    rows = D.compare(D.trade_signals([trade]), D.atp_lines([atp])[0])
    assert [x["status"] for x in rows] == [D.SAME], rows
