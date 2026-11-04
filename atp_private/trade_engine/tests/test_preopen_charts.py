# ATP (pre-open charts, owner 4 Nov): copied from Trade 813358b tests/test_preopen_charts.py (import paths only); the four
# tests of the Trade bot's own message / Telegram plumbing (cloud_db, notifications) stay in Trade - ATP sends through its own job.
"""Abhi (track F): pre-open संदेशाच्या वर CRUX (प्रत्येक symbol ≤ 5 ओळी) + Daily / 1H / 15M charts. Network / Telegram / DB नाही.

  • crux = fake reader state वरून: जवळचा area (kind, पट्टा, अंतर, state, confluence), method चा क्रम, invalidation, target — प्रत्येक
    आकडा input मधूनच (नवा आकडा नाही);
  • setting `preopen_charts` बंद ⇒ आजचाच संदेश अक्षरशः; चालू ⇒ फक्त crux block जोडलेला;
  • chart अयशस्वी (render / send) ⇒ संदेश तसाच जातो, "(chart unavailable)";
  • synthetic data वर प्रत्येक tf चा PNG, वेळ / memory मर्यादेत.
"""
import importlib.util
import os
import re
import time
import tracemalloc

import pandas as pd
import pytest

from atp_private.trade_engine.bots_common import level_reaction as LR
from atp_private.trade_engine.bots_common import plain_text as PT
from atp_private.trade_engine.bots_common import preopen_crux as PC
from atp_private.trade_engine.tests import engine_watch_stub as EW  # the engine payload stub (P1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _preopen():
    spec = importlib.util.spec_from_file_location("level_gate_preopen_f", os.path.join(ROOT, "scripts", "level_gate_preopen.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)
    return P


# Abhi च्या आजच्या संदेशासारखी अवस्था (आकडे त्या संदेशातले; state / tests / protected = fake reader facts)
NIFTY = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN", "protected": 23456.0}
BANK = {"ok": True, "trend": "DOWN", "sides": {LR.BEAR}, "band": None, "reason": "Daily DOWN", "protected": None}
CTX = {"NIFTY": NIFTY, "BANKNIFTY": BANK}
LAST = {"NIFTY": 22889.0, "BANKNIFTY": 55488.0}
LEVELS = {
    "NIFTY": [
        {"id": 1, "tf": "D", "role": "resistance", "lo": 23039.0, "hi": 23111.0, "state": "ACTIVE", "tests": 0, "flips": 0,
         "trade_location": True, "confluence": [], "confluence_label": None},
        {"id": 2, "tf": "1H", "role": "resistance", "lo": 23119.0, "hi": 23172.0, "state": "TESTED", "tests": 2, "flips": 0,
         "trade_location": True, "confluence": [{"tf": "W", "id": 9, "lo": 21281.0, "hi": 23290.0}, {"tf": "D", "id": 8, "lo": 23116.0,
                                                                                                       "hi": 23202.0}],
         "confluence_label": "confluence: Weekly 21,281–23,290; Daily 23,116–23,202"},
        {"id": 3, "tf": "1H", "role": "support", "lo": 22610.0, "hi": 22655.0, "state": "ACTIVE", "tests": 1, "flips": 0,
         "trade_location": True, "confluence": [], "confluence_label": None},
        {"id": 4, "tf": "1H", "role": "support", "lo": 22400.0, "hi": 22430.0, "state": "BROKEN", "tests": 1, "flips": 0,
         "trade_location": True, "confluence": [], "confluence_label": None}],
    "BANKNIFTY": [
        {"id": 5, "tf": "1H", "role": "resistance", "lo": 55699.0, "hi": 55970.0, "state": "FLIPPED", "tests": 1, "flips": 1,
         "trade_location": True, "confluence": [{"tf": "D", "id": 7, "lo": 55800.0, "hi": 56100.0}],
         "confluence_label": "confluence: Daily 55,800–56,100"},
        {"id": 6, "tf": "1H", "role": "resistance", "lo": 55947.0, "hi": 56066.0, "state": "ACTIVE", "tests": 0, "flips": 0,
         "trade_location": True, "confluence": [], "confluence_label": None}]}
ONE_BOT = {("15m_dynamic_sr", s): {"symbol_enabled": True, "signal_source": "engine"} for s in ("NIFTY", "BANKNIFTY")}
NOW = pd.Timestamp("2026-10-13 09:00")


def _settings(on, extra=None):
    def get(key, sym):
        return {"symbol_enabled": False, "trading_mode": "PAPER", **on.get((key, sym), {}), **((extra or {}) if (key, sym) in on else {})}
    return get


def _report(P, active, **kw):
    return P.build_report(["NIFTY", "BANKNIFTY"], "tok", lambda s: None, lambda s: LAST[s], trend_fn=lambda s: CTX[s],
                          weekly_fn=lambda s: "UP", day="2026-10-13", active=active, engine_fn=lambda s: pd.Timestamp("2026-10-12 15:16"),
                          now=NOW, engine_cron=True, engine_areas_fn=lambda s: EW.stamp(LEVELS[s], LAST[s], CTX[s]["sides"]), **kw)


def _crux(msg):
    """Decision needed नंतरचा crux block (पहिल्या रिकाम्या ओळीनंतर, symbol ओळींच्या आधी)."""
    body = msg.split(PT.DECISION_NONE + "\n\n", 1)[1].split("\n")
    out = []
    for i, ln in enumerate(body):                                      # crux lines; "" only between two crux blocks (A4: no symbol line)
        if ln == "" and not (i + 1 < len(body) and body[i + 1].startswith("<b>🎯")):
            break
        out.append(ln)
    return out


def _nums(text):
    return {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", re.sub(r"<[^>]+>", "", text))}


def test_crux_from_fake_reader_state_nearest_sequence_invalidation_target():
    P = _preopen()
    msg = _report(P, P.bot_status(["NIFTY", "BANKNIFTY"], _settings(ONE_BOT)))
    crux = _crux(msg)
    nifty = crux[:crux.index("")]
    bank = crux[crux.index("") + 1:]
    assert len(nifty) <= 5 and len(bank) <= 5
    assert nifty[0] == "<b>🎯 NIFTY</b> — Daily DOWN, Weekly UP ⇒ sell side only: supply above price."
    assert nifty[1] == ("Nearest: supply 23,039–23,111 (Daily, ≈150 pts above last close 22,889) · fresh (not tested yet) · "
                        "confluence: none · 72 pts wide")                                  # A4: the width rides on the crux line
    assert nifty[2].startswith("Entry only if: price visits it → handover → commitment candle with volume → 5-min change of character.")
    assert "Evidence at the area: 0 confluence piece(s)" in nifty[2] and "Label" not in nifty[2]   # A2: no A / B label (DECISIONS 58)
    assert nifty[3] == ("Invalid: close above 23,111 + a swing beyond it (area broken); Daily DOWN ends on a daily close above "
                        "23,456 (protected).")                                                # engine rule: close + swing beyond
    # target = विरुद्ध बाजूचा सर्वात जवळचा जिवंत support (BROKEN 22,400 tradeable_levels ने वगळला); पुढचा supply = 1H 23,119
    assert nifty[4] == ("Next opposite area (engine): demand 22,610–22,655 (1H, ≈234 pts below) · SL / target = dashboard · "
                        "if the nearest area breaks, next: supply 23,119–23,172 (1H).")
    assert bank[1] == ("Nearest: supply 55,699–55,970 (1H, ≈211 pts above last close 55,488) · flipped (reader role now supply, was demand), "
                       "tested 1× · "
                       "confluence: Daily · 271 pts wide · one cluster with 55,947–56,066")   # A3: the overlapping band
    assert "Evidence at the area: 1 confluence piece(s)" in bank[2] and "label" not in bank[2].lower()   # A2: the evidence count
    assert bank[3] == "Invalid: close above 55,970 + a swing beyond it (area broken)."         # protected नाही ⇒ ती अट नाही
    assert bank[4].startswith("Next opposite area (engine): no demand area in the list · SL / target = dashboard")
    assert "next: supply 55,947–56,066" not in bank[4]                                          # A3: in the cluster, never "next"
    # नवा आकडा नाही: crux मधला प्रत्येक आकडा = input (पट्टे, last close, protected) किंवा त्यांचं अंतर, किंवा tf / touch / tests
    allowed = {float(v) for s in LEVELS for x in LEVELS[s] for v in (x["lo"], x["hi"])} | set(LAST.values()) | {23456.0}
    allowed |= {round(23039 - 22889), round(22889 - 22655), round(55699 - 55488)} | {1.0, 5.0, 15.0} | {72.0, 271.0, 0.0}   # + widths, the evidence count
    assert _nums("\n".join(crux)) <= allowed, _nums("\n".join(crux)) - allowed
    assert not PT.has_raw_codes(PT.first_part(msg))                                             # वरचा भाग साध्या शब्दांत
    top = PT.first_part(msg)
    assert "🎯 NIFTY" in top and "<b>NIFTY</b>: Daily DOWN" not in top                           # A4: each index ONCE (its crux)




def test_chart_failure_never_blocks_the_text():
    P = _preopen()
    active = P.bot_status(["NIFTY", "BANKNIFTY"], _settings(ONE_BOT))
    ok = _report(P, active, chart_fn=lambda *a: True)

    def boom(sym, f, wk, line):
        raise MemoryError("render")
    bad = _report(P, active, chart_fn=boom)
    assert bad.count(PC.CHART_NA) == 2 and PC.CHART_NA not in ok
    assert bad.replace(" " + PC.CHART_NA, "") == ok                                             # बाकी संदेश तसाच
    half = _report(P, active, chart_fn=lambda sym, *a: sym == "NIFTY")
    assert half.count(PC.CHART_NA) == 1 and "🎯 BANKNIFTY</b> — Daily DOWN, Weekly UP ⇒ sell side only: supply above price. (chart" in half
    seen = []
    _report(P, active, chart_fn=lambda sym, f, wk, line: seen.append((sym, f["nearest"]["lo"], f["target"])) or True)
    assert seen[0][:2] == ("NIFTY", 23039.0) and seen[0][2]["lo"] == 22610.0                     # chart ला crux चीच तथ्यं


def test_send_charts_failure_is_logged_only(capsys):
    P = _preopen()
    png = {"NIFTY": [("Daily", b"\x89PNG..", "c1"), ("1H", b"\x89PNG..", "c2"), ("15M", b"\x89PNG..", "c3")]}
    got = []
    assert P.send_charts(png, lambda items: got.append(items) or True) == {"NIFTY": True}
    assert [c for _, c in got[0]] == ["c1", "c2", "c3"]

    def boom(items):
        raise ConnectionError("telegram down")
    assert P.send_charts(png, boom) == {"NIFTY": False}
    assert P.send_charts(png, lambda items: False) == {"NIFTY": False}
    out = capsys.readouterr().out
    assert "ConnectionError" in out and "NOT sent (text message already sent)" in out
    assert P.send_charts({}, boom) == {}






@pytest.fixture(scope="module")
def synth_v():
    from atp_private.trade_engine.decision3 import engine as E3
    from atp_private.trade_engine.tests import oct12_fixture as F
    m15, _fut, _ltf = F.build()
    return E3.V22(m15, None, None)


def test_charts_render_png_per_timeframe_on_synthetic_data_within_budget(synth_v):
    from atp_private.trade_engine.decision3 import preopen_chart as PCH
    V = synth_v
    t = len(V.m15) - 1
    last = float(V.m15["close"].iloc[t])
    from atp_private.trade_engine.engine3_live import tradeable_levels
    lv = tradeable_levels(V.levels.snapshot(t))
    st = V.daily[-1]
    ctx = {"ok": True, "trend": st.trend if st.trend in ("UP", "DOWN") else "DOWN", "sides": {LR.BEAR}, "band": None,
           "protected": st.protected.price if st.protected is not None else None}
    sides = [(LR.BEAR, x["lo"], x["hi"], "ENGINE_LEVEL_1H") for x in lv if x["lo"] > last] or \
        [(LR.BEAR, last + 10.0, last + 20.0, "ENGINE_LEVEL_1H")]
    line = PCH.line_facts(V, ctx["trend"])
    f = PC.facts(ctx, last, sides[:3], lv, line["tags"])
    tracemalloc.start()
    t0 = time.time()
    items, errs = PCH.render(V, "BANKNIFTY", f, "UP", line)
    took = time.time() - t0
    peak = tracemalloc.get_traced_memory()[1] / 2 ** 20
    tracemalloc.stop()
    assert errs == [] and [tf for tf, _, _ in items] == ["Daily", "1H", "15M"]
    for tf, png, cap in items:
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and 5_000 < len(png) < 600_000, (tf, len(png))
        assert cap.startswith(f"BANKNIFTY · {tf} · Daily ")
    assert took < 30 and peak < 150, (took, peak)                                              # 1 vCPU / 1 GB VPS: हलकं
    import matplotlib.pyplot as plt
    assert plt.get_fignums() == []                                                              # प्रत्येक figure बंद
    # एक tf अयशस्वी ⇒ बाकीचे तरी, कारण errors मध्ये
    items2, errs2 = PCH.render(V, "BANKNIFTY", {**f, "nearest": {"bad": 1}, "watched": [{"bad": 1}]}, "UP", line, tfs=("15M",))
    assert items2 == [] and errs2 and errs2[0].startswith("15M: KeyError")


def test_crux_edge_cases_no_area_na_unclear():
    assert PC.lines("NIFTY", {"ok": False, "trend": "UNKNOWN", "sides": set(), "reason": "x"}, None, 1.0)[0].startswith(
        "<b>🎯 NIFTY</b> — no new entries today")
    f = PC.facts(NIFTY, 22889.0, [], None)
    out = PC.lines("NIFTY", NIFTY, "UP", 22889.0, f)
    assert out[1] == "Last close 22,889: no supply area near price yet — nothing to enter."
    assert PC.lines("NIFTY", NIFTY, "UP", 22889.0, f, na="engine areas not available")[1] == "Watched areas NA — engine areas not available."
    assert PC.lines("NIFTY", NIFTY, "UP", None, PC.facts(NIFTY, None, [], None))[1].startswith("Price data missing")
    # own source (engine levels नाहीत): state / target NA, कुठलाही नवा आकडा नाही
    f = PC.facts(NIFTY, 22889.0, [(LR.BEAR, 23000.0, 23050.0, "DYNAMIC_SR_RESISTANCE_15M")], None)
    out = PC.lines("NIFTY", NIFTY, "UP", 22889.0, f)
    assert out[1] == "Nearest: supply 23,000–23,050 (15-min, ≈111 pts above last close 22,889) · confluence: none"
    assert out[4] == "Next opposite area (engine): no demand area in the list · SL / target = dashboard."
    # line touch N (reader चं confluence_areas) ⇒ confluence शब्द
    f = PC.facts(NIFTY, 22889.0, [(LR.BEAR, 23039.0, 23111.0, "ENGINE_LEVEL_1D")], LEVELS["NIFTY"], {1: "line (touch 3)"})
    assert f["nearest"]["conf"] == "line (touch 3)"


def test_nearest_is_by_edge_distance_not_midpoint_order():
    """12 Oct-like: the message lists 22,570–22,579 first (midpoint ≈211 pts) but price reaches 22,544–22,622 first (edge ≈181 pts)."""
    P = _preopen()
    last = 22363.0
    levels = [{"id": 1, "tf": "1H", "role": "resistance", "lo": 22570.0, "hi": 22579.0, "state": "ACTIVE", "tests": 0},
              {"id": 2, "tf": "1H", "role": "resistance", "lo": 22544.0, "hi": 22622.0, "state": "TESTED", "tests": 5},
              {"id": 3, "tf": "1H", "role": "resistance", "lo": 22723.0, "hi": 22732.0, "state": "ACTIVE", "tests": 0}]
    areas = [(LR.BEAR, x["lo"], x["hi"], "ENGINE_LEVEL_1H") for x in levels]
    ordered = P.nearest(areas, last, 3)
    assert (ordered[0][1], ordered[0][2]) == (22570.0, 22579.0)                                # the message's own order: midpoint
    f = PC.facts(NIFTY, last, ordered, levels)
    assert (f["nearest"]["lo"], f["nearest"]["hi"], f["nearest"]["dist"]) == (22544.0, 22622.0, 181.0)
    assert (f["next"]["lo"], f["next"]["hi"]) == (22723.0, 22732.0)                            # 22,570–22,579 sits inside: not "next"
    out = PC.lines("NIFTY", NIFTY, "UP", last, f)
    assert out[1] == ("Nearest: supply 22,544–22,622 (1H, ≈181 pts above last close 22,363) · tested 5× · confluence: none"
                      " · one cluster with 22,570–22,579")                                     # A3: overlapping ⇒ one cluster
    assert out[3].startswith("Invalid: close above 22,622 + a swing beyond it (area broken)")
    assert out[4].endswith("if the nearest area breaks, next: supply 22,723–22,732 (1H).")
    assert [(a["lo"], a["hi"]) for a in f["watched"]] == [(x[1], x[2]) for x in ordered]       # everything else unchanged


def test_crux_error_never_blocks_the_message_and_omits_the_crux(monkeypatch, capsys):
    """Review MUST 1: crux (facts / lines) त्रुटी ⇒ log + crux नाही ⇒ संदेश setting-off सारखाच अक्षरशः."""
    P = _preopen()
    active = P.bot_status(["NIFTY", "BANKNIFTY"], _settings(ONE_BOT))
    off = _report(P, active, crux_on=False)
    monkeypatch.setattr(PC, "facts", lambda *a, **k: (_ for _ in ()).throw(KeyError("boom")))
    assert _report(P, active) == off
    assert capsys.readouterr().out.count("pre-open crux: KeyError") == 2
    monkeypatch.undo()
    calls = []

    def lines(sym, *a, **k):                                                                    # एकाच symbol ला त्रुटी ⇒ दुसऱ्याचा crux राहतो
        calls.append(sym)
        if sym == "NIFTY":
            raise ValueError("x")
        return ["<b>🎯 BANKNIFTY</b> — ok"]
    monkeypatch.setattr(PC, "lines", lines)
    msg = _report(P, active)
    assert "🎯 NIFTY" not in msg and "<b>🎯 BANKNIFTY</b> — ok\n\n<b>NIFTY</b>" in msg and calls == ["NIFTY", "BANKNIFTY"]


def test_render_time_budget_skips_remaining_charts(synth_v):
    from atp_private.trade_engine.decision3 import preopen_chart as PCH
    t = iter([0.0, 100.0, 100.0])
    f = PC.facts({"ok": True, "trend": "DOWN", "sides": {LR.BEAR}}, float(synth_v.m15["close"].iloc[-1]), [], None)
    items, errs = PCH.render(synth_v, "BANKNIFTY", f, "UP", None, deadline=50.0, clock=lambda: next(t))
    assert [tf for tf, _, _ in items] == ["Daily"] and errs == ["1H: skipped (time budget)", "15M: skipped (time budget)"]




def _area(side, lo, hi):
    return (side, lo, hi, "ENGINE_LEVEL_1H")


def test_next_area_must_reach_past_the_nearest_far_edge():
    """Re-review: "next" = a same-side band extending PAST the nearest band's far edge, ranked from that edge; nested ⇒ never."""
    last = 22363.0
    nested = PC.facts(NIFTY, last, [_area(LR.BEAR, 22570.0, 22579.0), _area(LR.BEAR, 22544.0, 22622.0)])
    assert (nested["nearest"]["lo"], nested["nearest"]["hi"]) == (22544.0, 22622.0) and nested["next"] is None
    out = PC.lines("NIFTY", NIFTY, "UP", last, nested)
    assert "if the nearest area breaks" not in out[4] and out[4].endswith("SL / target = dashboard.")   # none ⇒ clause omitted
    # A3 (28 Oct): partly overlapping bands are ONE cluster with the nearest (chained), never "next" (BANKNIFTY 54,590–54,654 →
    # 54,636–54,968 live); "next" lies fully beyond the cluster's far edge
    bank = PC.facts(BANK, 55488.0, [_area(LR.BEAR, 55699.0, 55970.0), _area(LR.BEAR, 55947.0, 56066.0),
                                    _area(LR.BEAR, 56038.0, 56125.0), _area(LR.BEAR, 56200.0, 56300.0)])
    assert [(a["lo"], a["hi"]) for a in bank["cluster"]] == [(55947.0, 56066.0), (56038.0, 56125.0)]
    assert (bank["next"]["lo"], bank["next"]["hi"]) == (56200.0, 56300.0) and bank["next"]["lo"] > 56125.0
    nifty = PC.facts(NIFTY, 22700.0, [_area(LR.BEAR, 22778.0, 22789.0), _area(LR.BEAR, 22778.0, 22809.0)])   # NIFTY live case
    assert nifty["next"] is None and [(a["lo"], a["hi"]) for a in nifty["cluster"]] == [(22778.0, 22809.0)]
    # ranked by distance from the far edge, not from the last close
    far = PC.facts(NIFTY, last, [_area(LR.BEAR, 22500.0, 22600.0), _area(LR.BEAR, 22700.0, 22720.0),
                                 _area(LR.BEAR, 22520.0, 22590.0), _area(LR.BEAR, 22640.0, 22900.0)])
    assert (far["next"]["lo"], far["next"]["hi"]) == (22640.0, 22900.0)
    # demand mirror: below the nearest band's low only
    up = {"ok": True, "trend": "UP", "sides": {LR.BULL}, "band": None, "protected": None}
    dem = PC.facts(up, 23000.0, [_area(LR.BULL, 22800.0, 22900.0), _area(LR.BULL, 22820.0, 22880.0), _area(LR.BULL, 22700.0, 22780.0)])
    assert (dem["nearest"]["lo"], dem["next"]["lo"]) == (22800.0, 22700.0)


def test_r2_one_band_per_same_side_overlap_display_only():
    """R2 (DECISIONS 140): overlapping same-side areas = one band on the chart (the engine's nearest, else the member nearest to the last
    close) with the count of the others; the opposite side and a separate band stay as they are; the input list is never changed."""
    from atp_private.trade_engine.decision3 import preopen_chart as PCH
    a = {"side": "bear", "lo": 100.0, "hi": 110.0, "dist": 5.0}
    b = {"side": "bear", "lo": 105.0, "hi": 120.0, "dist": 10.0}
    c = {"side": "bear", "lo": 130.0, "hi": 140.0, "dist": 30.0}
    d = {"side": "bull", "lo": 80.0, "hi": 90.0, "dist": 5.0}
    w = [a, b, c, d]
    out = PCH.one_per_cluster(w, near=None, last=95.0)
    assert [(x is a, n) for x, n in out if x["side"] == "bear" and x["lo"] < 125] == [(True, 1)]
    assert (c, 0) in out and (d, 0) in out and len(w) == 4
    assert PCH.one_per_cluster(w, near=b, last=95.0)[0] == (b, 1)        # the engine's nearest leads its group
