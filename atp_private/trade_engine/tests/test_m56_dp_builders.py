"""M56 E4 (A4, D2): data-problem bars (the closing-auction flat tail + print, DECISIONS 84; the auction-extended Daily close, DECISIONS
87) reach every price builder only as TRADED price, through ONE helper (decision3/history.traded_arrays and its frame / Levels
wrappers). The builder list below is the register: a builder that reads OHLC must name the helper, and the behaviour tests show the
print never makes a 1H candle extreme, a 1H / Daily swing, an RSI value, a PDH / PDL, a gap's previous close or a level-bot price."""
import pathlib

import numpy as np
import pandas as pd

from atp_private.trade_engine.decision3 import history as HI
from atp_private.trade_engine.decision3 import levels as LV
from atp_private.trade_engine.decision3 import sw as SW

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILDERS = {                       # file ⇒ the helper call it must use (the one shared helper, never its own copy)
    "decision3/levels.py": ("HI.traded(m15)", "HI.traded_arrays("),          # the 1H frame + the running 1H candle (`At`)
    "decision3/sw.py": ("HI.traded(df)",),                                   # SW swings / trend (Daily, Weekly; 1H via h1_frame)
    "decision3/engine.py": ("skip=HI.dp_mask(self.m15)", "HI.traded_of(self.levels)"),   # rsi2 (flagged bars skipped) + legs2
    "decision3/entry_models.py": ("HI.traded_of(lv)",),                      # the place tolerance's ATR (M56 E2)
    "decision3/draw_objects.py": ("skip=HI.dp_mask(lv.m15)",),               # the charts' RSI (the engine's own reader)
    "decision3/liquidity.py": ("HI.traded_of(",),                            # pools (PDH / PDL / PWH / PWL, equal), sweeps
    "decision3/gaps.py": ("HI.traded_of(V.levels)",),                        # opening gaps (previous close)
    "decision3/candle_forms.py": ("HI.traded_of(V.levels)",),                # candle forms at locations
    "decision3/volume_read.py": ("HI.traded_of(V.levels)",),                 # volume reads (bar direction, extremes)
    "bots_common/level_reaction.py": ("HI.traded_frame(bars)",),             # the level bots (and level_gate_bot through it)
    "vision/worker.py": ("HI.traded_frame(m1",),                             # Vision's own level frame
}


def test_every_builder_uses_the_one_helper():
    for f, calls in BUILDERS.items():
        src = (ROOT / f).read_text(encoding="utf-8")
        for c in calls:
            assert c in src, f"{f}: does not read data-problem bars through the helper ({c})"
    lg = (ROOT / "bots_common/level_gate_bot.py").read_text(encoding="utf-8")
    assert "LR.evaluate" in lg or "LR.safe_evaluate" in lg               # level_gate_bot reads its bars through level_reaction


def _m15(print_high=None):
    """Two sessions of 15M bars; the second ends with a flagged 15:15 bar whose print spikes far above (DP-2)."""
    rows = []
    for day, base in (("2030-01-07", 100.0), ("2030-01-08", 110.0)):
        t = pd.Timestamp(f"{day} 09:15")
        for i in range(25):
            p = base + i * 0.2
            rows.append({"timestamp": t, "open": p, "high": p + 0.5, "low": p - 0.5, "close": p + 0.1, "data_problem": ""})
            t += pd.Timedelta(minutes=15)
    df = pd.DataFrame(rows)
    if print_high is not None:
        k = len(df) - 1
        o = float(df.loc[k, "open"])
        df.loc[k, ["high", "close", "data_problem"]] = [print_high, print_high, HI.CLOSE_PRINT]
        df.loc[k, "low"] = o
    return df


def test_traded_arrays_reads_a_flagged_bar_as_its_open_and_clamps_dp3():
    o, h, l, c = HI.traded_arrays([1.0, 2.0], [3.0, 9.0], [0.5, 1.5], [2.0, 9.0], np.array([False, True]))
    assert list(h) == [3.0, 2.0] and list(l) == [0.5, 2.0] and list(c) == [2.0, 2.0]
    o, h, l, c = HI.traded_arrays([1.0], [3.0], [0.5], [4.0], np.array([False]), ax=np.array([True]))
    assert list(c) == [3.0] and list(h) == [3.0]                          # DP-3: the close inside the traded range
    df = _m15()
    assert HI.traded(df) is df and HI.traded(df.drop(columns="data_problem")) is not None   # no flag ⇒ as given


def test_the_1h_frame_never_takes_the_auction_print():
    raw = _m15(print_high=500.0)
    h1, of = LV.h1_frame(raw)
    plain, pof = LV.h1_frame(raw.drop(columns="data_problem"))
    assert plain["high"].max() == 500.0                                  # unmarked data reads as given (the marks decide)
    assert h1["high"].max() < 200 and len(h1) == len(plain) - 1          # the flagged-only 15:15 bin is NOT a 1H candle (excluded)
    assert of[-1] == of[-2] and h1["close"].iloc[-1] == raw["close"].iloc[-2]   # its bar joins the 14:15 bin, no price from it
    assert len(of) == len(raw)


def test_sw_reads_traded_prices():
    d = pd.DataFrame({"timestamp": pd.date_range("2030-01-01", periods=40, freq="D"),
                      "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "data_problem": ""})
    d.loc[20, ["high", "close", "data_problem"]] = [180.0, 180.0, HI.CLOSE_PRINT]
    s = {"sw_pivot_n": 2, "sw_atr_n": 14, "sw_ext_atr": 3.0, "sw_int_atr": 1.0}
    _st, ext, allv = SW.tf_states(d, s)
    assert all(x.price < 180.0 for x in allv)


def test_level_bot_and_vision_frames_are_marked_then_traded():
    raw = _m15(print_high=500.0).drop(columns="data_problem")
    x = HI.traded_frame(raw.assign(data_problem=_m15(print_high=500.0)["data_problem"]))
    assert x["high"].max() < 200
    assert HI.traded_frame(None) is None and HI.traded_frame(raw.iloc[:0]).empty


def test_one_cas_detector_the_clock_window_only_logs_disagreement():
    """The marks come from the shape detector only; the config clock window is a sanity check that logs each disagreeing session."""
    def day(d, tail_flat):
        t, rows = pd.Timestamp(f"{d} 09:15"), []
        for i in range(75):
            p = 100.0 + (i % 7)
            if tail_flat and i >= 72:                                    # 15:15 … 15:25: flat, then the 15:25 print
                rows.append((t, 103.0, 103.0, 103.0, 103.0 if i < 74 else 110.0))
            else:
                rows.append((t, p, p + 1, p - 1, p + 0.5))
            t += pd.Timedelta(minutes=5)
        return rows
    rows = day("2030-01-07", True) + day("2030-01-08", False)
    m5 = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close"])
    m5.loc[(m5["timestamp"].dt.strftime("%H:%M") == "15:25") & (m5["timestamp"].dt.day == 7), "open"] = 103.0
    marked = HI.mark_data_problems(m5, None, "5M")
    got = []
    out = HI.cas_sanity(marked, cas={"effective_from": "2030-01-01"}, log_fn=got.append)
    assert [x["session"] for x in out] == ["2030-01-08"] and len(got) == 1   # the window expects CAS on 8 Jan, the detector saw none
    assert HI.dp_mask(HI.mark_data_problems(m5, None, "5M")).sum() == HI.dp_mask(marked).sum()   # the check never marks anything
    src = (ROOT / "engine3_live.py").read_text(encoding="utf-8")
    assert "HI.cas_sanity(ltf" in src and "HI.ensure_marked(m15, [ltf, df1m])" in (ROOT / "decision3/engine.py").read_text(encoding="utf-8")


def test_rsi_never_uses_a_flagged_bar():
    from atp_private.trade_engine.rsi2 import engine as RE
    c = np.r_[np.linspace(100, 120, 30), [500.0], np.linspace(121, 110, 10)]
    seg, skip = np.zeros(len(c)), np.zeros(len(c), bool)
    skip[30] = True
    r = RE.rsi_skipping(c, seg, 14, skip)
    assert np.allclose(np.delete(r, 30), RE.rsi_segmented(np.delete(c, 30), np.delete(seg, 30), 14), equal_nan=True)
    assert r[30] == r[29]                                                # the flagged bar shows the last traded bar's RSI
    assert np.array_equal(RE.rsi_skipping(c, seg, 14, None), RE.rsi_segmented(c, seg, 14), equal_nan=True)
