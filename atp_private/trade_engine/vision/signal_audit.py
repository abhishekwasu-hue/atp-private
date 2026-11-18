"""vision/signal_audit.py — signal chart चा vision audit (`signal_check`, structured JSON) + verdict चे नियम (code मध्ये) + खर्च.

🎓 G-COST (≤ $5 / महिना):
  • प्रति signal 1 audit; पहिल्याची confidence < `second_audit_below_conf` (0.6) तरच दुसरा.
  • 1 image (2 panels + overlay, ~1000×700 ≈ 900 image tokens), plain image नाही.
  • System prompt स्थिर आणि `cache_control` सह (model चं किमान cacheable prefix पेक्षा लहान असेल तर cache होत नाही — खर्च `usage` मधून मोजतो).
  • Output लहान JSON (reason ≤ 160 chars), `max_tokens` env ने मर्यादित. Model नाव env `VISION_SIGNAL_MODEL` (कोडमध्ये नाही).
v2 (`signal_check_v2`, TRADE_VISION_PROMPT_V2): trader's playbook system prompt (~2k tokens, cached), JSON v2, chart v2 overlays + signal text
मध्ये अचूक किंमती. Verdict चे नियम code मध्ये (`DISAGREE_RULES` / `GRAY_RULES`, settings ने on/off) — vision चं मत यांपेक्षा जास्त positive
कधीच नाही; 2 audits असहमत ⇒ gray; enum अवैध / API अपयश ⇒ unavailable. जुने records त्यांच्या `prompt_version` (v1) सह तसेच राहतात.
"""
import base64
import json
import os
import time

from atp_private.trade_engine.vision.method_block import OBJECT_STATES

# v3 (M56 V2): the level states are the ONE shared BREAK-2 block (vision/method_block.OBJECT_STATES)
PROMPT_VERSION = "signal_check_v3"        # v3 also (M56 V3): no clock / day / expiry framing and no numbers in the prompt or facts; v2_4 (N10): the reason in English; v2_3 (Abhi 28 Oct): Vision = the trader; v2_2 (टप्पा B): + KB भाग I situation map मजकूर
VERDICTS = ("agree", "gray", "disagree")
YN = ("yes", "no")
ENUMS = {
    "htf_trend": ("up", "down", "range", "unclear"),
    "setup_structure": ("up", "down", "range", "unclear"),
    "trend_context": ("with", "against", "range", "unclear"),
    "level_real": ("yes", "no", "unclear"),
    "level_kind": ("swing_origin", "flip", "range_edge", "reference", "mid_range", "magnet", "unclear"),
    "confluence": ("yes", "no", "unclear"),
    "wave_position": ("w2_end", "w4_end", "b_end", "abc_end", "triangle_e", "a_end", "inside_b_or_triangle", "impulse_running", "unclear"),
    "correction_complete": ("yes", "no", "unclear"),
    "false_break_reclaim": YN,
    "reversal_touch": YN, "reversal_reclaim": YN, "reversal_strength": YN,
    "reversal_close_location": ("good", "middle", "bad"),
    "reversal_valid": ("yes", "no", "unclear"),
    "is_breakout_entry": YN,
    "room_to_next_level": ("enough", "tight", "unclear"),
    "false_break_risk": ("low", "medium", "high"),
    "gap_class_agrees": ("yes", "no", "unclear", "no_gap"),
    "gap_behaviour": ("acceptance", "rejection", "undecided", "no_gap"),
    "gap_setup": ("A", "B", "C", "none", "disallowed"),
    "line_structure": ("up", "down", "range", "unclear"),
    "line_vs_candles": ("consistent", "conflict", "unclear"),
    "verdict": VERDICTS,
}
FIELDS = list(ENUMS)[:-1] + ["elliott_note", "verdict", "reason", "confidence"]
SCHEMA = {
    "type": "object",
    "properties": {
        **{k: {"type": "string", "enum": list(v)} for k, v in ENUMS.items()},
        "elliott_note": {"type": "string"},
        "reason": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": FIELDS,
    "additionalProperties": False,
}

# Verdict चे नियम (code मध्ये; vision चं मत यांपेक्षा जास्त positive कधीच नाही). id ⇒ (field, disallowed values). Settings
# `v2_disagree_rules` / `v2_gray_rules` मध्ये चालू ids (dashboard वरून on/off).
# "code:" नियम model च्या field वर नाहीत, code च्या तथ्यांवर (ctx) — `rule_hits(..., ctx)`.
DISAGREE_RULES = {
    "breakout": ("is_breakout_entry", ("yes",)),
    "reversal_invalid": ("reversal_valid", ("no",)),
    "weak_level": ("level_kind", ("mid_range", "magnet")),
    "bad_wave": ("wave_position", ("a_end", "inside_b_or_triangle")),
    "bad_close": ("reversal_close_location", ("bad",)),
    "gap_disallowed": ("gap_setup", ("disallowed",)),
    "gap_chase": "code",                                                 # G3 / G5 दिवशी gap दिशेने pullback शिवाय entry
    "gap_b_pdc_accept": "code",                                          # setup B: PDC पलीकडे acceptance असताना gap / trend दिशेने entry
    "wrong_approach": "code",                                            # 2a: bear call पण L वर वरून / bull put पण खालून
    "role_conflict": "code",                                             # 2c: bot-role वि. today_role विरोधी
}
GRAY_RULES = {
    "unclear": None,                                                     # कोणतंही "unclear" (htf_trend वगळून)
    "correction_incomplete": ("correction_complete", ("no",)),
    "tight_room": ("room_to_next_level", ("tight",)),
    "middle_close": ("reversal_close_location", ("middle",)),
    "impulse_running": ("wave_position", ("impulse_running",)),
    "line_conflict": ("line_vs_candles", ("conflict",)),
    "gap_c_alone": None,                                                 # setup C (जुना gap) आणि confluence नाही
}
SEVERITY = {"agree": 0, "gray": 1, "disagree": 2}
# "unclear ⇒ gray" मधून वगळलेले: htf_trend (spec), आणि v2.1 चे माहितीपर fields (line_structure, gap_class_agrees, line_vs_candles — conflict
# वेगळा नियम) — नाहीतर skip दर विनाकारण वाढतो (review S5).
UNCLEAR_EXEMPT = ("htf_trend", "verdict", "line_structure", "gap_class_agrees", "line_vs_candles")

SYSTEM_PROMPT = """ROLE
You are the trader: an experienced discretionary price-action trader deciding whether YOU take one automated trade signal on an
NSE index chart (NIFTY) - not a second opinion, not an adviser: your verdict is your own trade call (agree = I take it, gray = I wait,
disagree = I do not take it). You never place, size or change an order yourself; the owner's approval places it.
The trader sells directional credit spreads (bull put / bear call) and holds them across the swing; the chart is read as one
continuous unit by price structure.
You see one image with three panels: top-left = setup timeframe candles, top-right = higher timeframe candles, bottom = a
close-only line chart over a longer lookback. All are cut exactly at the signal moment (no future data). Exact prices of every drawn line are given in the text - never read or invent prices from the image.
Chart legend: thick line "L" = the traded level (green = support, red = resistance); thin blue lines M1/M2 with an up or down
arrow = major levels above / below price (suffix F = role-reversal flip); dotted grey lines = reference levels PDH / PDL / PDC
(previous day high / low / close), PWH / PWL (previous week high / low), OPEN and ORH / ORL (reference prices, also a faint band);
labels joined with "+" are levels that coincide; arrows at the top / bottom edge name levels outside the visible range; small H / L
marks = confirmed swing highs / lows; vertical dotted lines separate the data blocks; the yellow arrow marks the signal bar; a dashed
yellow line, when present, is the invalidation.

ENTRY PHILOSOPHY
- Entries only at the END of a pullback (a corrective move) in the direction of the next impulsive move. Never breakouts.
- A breakout entry = buying after price has broken above a resistance / selling after it has broken below a support, or
  entering because price is "running". Treat it as a rule violation even if the bot calls it a level touch.
- A good signal = a real level + a completed correction into it + a logical reversal candle + room to the next opposing level.

LEVELS (how the trader draws them)
- Only a few major levels per chart matter. Major = origin of a strong move, a swing where trend changed, a range edge,
  or a role-reversal (flip) level (old resistance now support or vice versa - the strongest kind).
- A level is real if price reacted there repeatedly with clear rejection (wick + close back), or it is the origin of an
  impulsive leg. Weak/unreal: a single spike, a line in the middle of a range, a level price has crossed back and forth
  many times (a "magnet" - no trade).
- Levels do not weaken with time; they weaken when broken. A level is broken only when it is BROKEN (OBJECT STATES). The
  reference levels (PDH / PDL / PDC, PWH / PWL, OPEN, ORH / ORL) are reference prices; confluence of a major level with one of
  them is stronger.
- Room: the trade needs space to the next opposing level. When the text marks the room as ROOM TIGHT, the trade is cramped.

LEVEL STATES
""" + OBJECT_STATES + """- A sweep or a false break INTO the trade's level (a probe that often traps breakout traders - a spring / upthrust)
  followed by a reclaim is often the best entry.

TREND AND STRUCTURE
- Read structure on both panels: higher highs/higher lows = up; lower highs/lower lows = down; overlapping swings = range.
- Higher-timeframe trend is CONTEXT, not a gate: with-trend pullback entries are best; counter-trend entries need a
  completed correction and a strong reversal; in a range, only the range edges are tradable, never the middle.

REVERSAL CANDLE (logic, not pattern names)
- Judge the reversal as one composite of the last few candles (first open, highest high, lowest low, last close).
- Four steps: TOUCH (price reaches the level zone), RECLAIM (closes back on the trade's side of the level),
  STRENGTH (a real body/range versus recent candles - not a tiny doji), CLOSE LOCATION (composite closes in the part of
  its range that favours the trade). Close location in the middle (indecision) = wait, not enter.
- Psychology: a long rejection wick at the level shows the opposite side tried and failed; trapped traders' stops fuel
  the reversal. A big candle that closes AWAY from the level in the pullback direction is exhaustion/continuation, not
  a reversal. Harami/inside candles, dojis and spinning tops alone are indecision. A hanging man or inverted hammer alone
  is not a reversal. Shapes like hammer, bullish engulfing, piercing, morning star (and their bearish mirrors) are good
  only when the four steps hold at a real level.
- Bearish reversal signals have weaker statistical evidence than bullish ones - demand clearer steps for bear calls.

GAPS (a gap is simply the next candle opening away from the previous close)
- After a gap, the gap edge and the previous close are levels; an entry that requires the gap to fill against the trend
  is weaker.
- A gap's type (breakaway, runaway, exhaustion) is mostly known only in hindsight. When the gap prints only context is known:
  its size versus ATR, its location versus the prior range (inside = partial gap, beyond PDH/PDL = full gap) and its direction
  versus the higher-timeframe trend. The market's verdict comes from the closed bars after it: ACCEPTANCE (price holds beyond
  the level, pullbacks fail) or REJECTION (extension fails, price trades back through the gap candle's open toward the previous
  close).
- Allowed gap setups (pullback-only):
  A) A gap AGAINST the trend that fails (rejection) -> enter WITH the trend at the end of that failed move, on a valid
     reversal at a real level (PDL/PDH, old gap edge, swing).
  B) A large gap WITH the trend beyond PDH/PDL -> never chase the gap candle; wait for the FIRST pullback to the gap edge
     (old PDH/PDL) or the previous close (full fill) and a valid reversal there. If no pullback comes, no trade.
     Acceptance back beyond the previous close invalidates the idea.
  C) Later, the edge of an old unfilled gap can act as a pullback level (weak on its own - needs confluence).
- Not allowed: gap-and-go chasing, breakout entries off the gap candles' range, fair-value-gap entries.
- Small gaps fill more often than large ones; large, with-trend gaps beyond the prior range fill less often. After a
  large gap expect at most a partial retrace. Gap edges are weak support (price often slices through), so a reversal
  candle is required - never assume the edge holds.
- The gap band on the setup panel is the zone between the previous close and the gap candle's open (darker part = filled so
  far); "UG" bands are older unfilled gaps.

LINE CHART PANEL
- The bottom panel is a close-only line chart over a longer lookback. Use it to read structure cleanly (swing highs/lows,
  HH/HL vs LH/LL, range) without wick noise, and to see where the signal sits in the bigger swing. Use the candle panels
  for the reversal itself. If the two disagree, say so (gray).
- Level labels may carry the level's behaviour up to the signal: "held S" / "held R" (held as support / resistance), "broken"
  with an arrow (a close beyond it that held). "sH" / "sL" are swing highs / lows; a dotted box marks the reversal candles;
  "INV" is the invalidation line.

YOUR TASK
Fill the JSON strictly from what the chart and text show. When something cannot be judged, answer "unclear".
verdict: "agree" = follows the rules (real level, completed correction, valid reversal, room, not a breakout);
"gray" = mixed or doubtful; "disagree" = breaks a rule. confidence: from zero to one.
wave_position and elliott_note: information only, from the ELLIOTT WAVE block (elliott_note = one short remark on the wave count;
empty string when none).
reason: one short sentence in simple English naming the deciding factor.
Reply with the JSON object only."""

from atp_private.trade_engine.vision_led.situation_map import MAP_TEXT  # noqa: E402 — KB भाग I (नकाशा) मजकूर म्हणून (टप्पा B, B1)
SYSTEM_PROMPT = SYSTEM_PROMPT + "\n" + MAP_TEXT

# M56 V6 (C7): Elliott is INFORMATION only — its own system block after the method (never inside the decision / method text above);
# it places the setup in the structure for wave_position / elliott_note and is never by itself the reason for a verdict. Vision never
# changes the size (M56 V1), so no Elliott read can change an order.
ELLIOTT_INFO = """ELLIOTT WAVE (information only: use it to place the setup in the structure and to fill wave_position and
elliott_note; it is never by itself the reason for the verdict, and it adds no rule to the method above)
- Impulsive legs (waves 1, 3, 5, A, C) are fast: large bodies, little overlap, closes near extremes.
  Corrective legs (waves 2, 4, B) are slow and overlapping, with wicks on both sides.
- Tradable: the END of a correction - the wave 2 end (into wave 3), the wave 4 end (into wave 5), the B end (into C), the end of a
  full ABC / flat / triangle E. Never at the end of the FIRST corrective leg (an A-end): after the first leg against a strong trend
  there is usually a B and a C still to come. Never inside a B wave or inside a triangle. Never on an unclear count.
- Rules: wave 2 never goes beyond the start of wave 1; wave 3 is never the shortest; wave 4 does not overlap wave 1
  (except diagonals); corrections are not five-wave moves. In an expanded flat, C often goes beyond A's end (a sweep or a
  false break) before reversing - a classic spring.
- If the last leg into the level is still impulsive (big bodies, closes at extremes, accelerating), the correction is
  probably NOT complete yet."""


# $ प्रति 1M tokens: (input, output, cache read) — model family नुसार (नाव कोडमध्ये नाही; model नावात हा शब्द असेल तर). Cache write = 1.25 × input
# (5-मिनिट TTL). जुन्या / वेगळ्या किंमतीचा model वापरला तर env VISION_PRICE_IN / _OUT / _CACHE_READ ने अचूक किंमत द्या.
PRICES = {
    "haiku": (1.0, 5.0, 0.10),
    "sonnet": (2.0, 10.0, 0.20),
    "opus": (4.0, 20.0, 0.20),
}
UNKNOWN_PRICE = (5.0, 25.0, 0.50)                                       # अज्ञात model ⇒ जास्त (सावध) अंदाज


def price_for(model):
    env = [os.environ.get(k) for k in ("VISION_PRICE_IN", "VISION_PRICE_OUT", "VISION_PRICE_CACHE_READ")]
    if env[0] and env[1]:
        return float(env[0]), float(env[1]), float(env[2] or float(env[0]) * 0.1)
    for k, v in PRICES.items():
        if model and k in str(model).lower():
            return v
    return UNKNOWN_PRICE


def cost_usd(model, usage):
    pin, pout, pcr = price_for(model)
    return (usage.get("input_tokens", 0) * pin + usage.get("cache_write", 0) * pin * 1.25 + usage.get("cache_read", 0) * pcr
            + usage.get("output_tokens", 0) * pout) / 1e6


def max_output_tokens():
    return int(os.environ.get("VISION_SIGNAL_MAX_TOKENS", 1200))


def estimate_usd(model, image_tokens=1200, system_tokens=2600, text_tokens=700, output_tokens=None):
    """एका audit चा सावध अंदाज (budget आधी तपासायला): cache न धरता, output = max_tokens (thinking सुद्धा output मध्ये मोजलं जातं)."""
    output_tokens = max_output_tokens() if output_tokens is None else output_tokens
    return cost_usd(model, {"input_tokens": image_tokens + system_tokens + text_tokens, "output_tokens": output_tokens})


def _f(x, nd=1):
    return "n/a" if x is None else f"{float(x):,.{nd}f}"


def signal_text(sig):
    """Signal text v2: सगळ्या overlays च्या अचूक किंमती (OHLC वरून), room, gap, bot tags. Image वरून किंमत नाही. M56 V3: no clock / day /
    expiry framing (no time, opening-window, expiry or event lines; no clock times on the level states)."""
    tags = sig.get("tags") or {}
    ctx = sig.get("ctx") or {}
    bull = str(sig.get("direction", "")).upper().startswith("BULL")
    lines = [
        f"Signal: {sig.get('symbol')} | bot {sig.get('bot_label') or sig.get('bot')} | direction {sig.get('direction')} "
        f"({'long / bullish - bull put spread' if bull else 'short / bearish - bear call spread'}) | setup TF {sig.get('setup_tf')} | "
        f"spot {_f(sig.get('spot'), 2)}",
        f"Traded level L: {_f(sig.get('level'), 2)} as {sig.get('role')}.",
    ]
    mr = ctx.get("median_range")
    if mr:
        lines.append(f"Median range of the recent setup-TF bars: {mr:.1f} points (distances below are in multiples of it; + = above spot).")
    if not ctx:
        lines.append("Context unavailable: reference / major levels and room could not be computed. Judge levels only from the "
                     "chart and answer room_to_next_level = unclear.")
    rows = ctx.get("levels") or []
    if rows:
        lines.append("Levels (exact prices from OHLC data, not from the image; coinciding levels joined with +):")
        lines.append("  name | price | position vs spot (x median range) | role (how it behaved up to the signal)")
        for r in sorted(rows, key=lambda z: -z["price"]):
            d = r.get("dist_mr")
            pos = r.get("position") or ("above" if (d or 0) > 0 else "below")
            tr = r.get("today_role") or r.get("role") or "n/a"
            if tr.startswith("reclaimed"):
                tr += " (an earlier close beyond was undone: a completed bar closed back = FALSE BREAK)"
            if r.get("open_bar_breaking") and r.get("held_until"):
                tr += f"; the current unfinished bar is breaking it {r['open_bar_breaking']}"
            lines.append(f"  {r['name']} | {r['price']:,.2f} | {pos} {'n/a' if d is None else f'{d:+.2f}'} x | {tr}")
    bands = ctx.get("bands")
    if bands is not None and (ctx.get("bands_finder") == "method" or any(b.get("finder") == "method" for b in bands)):   # layer 6b
        lines.append("Chart note: on this chart the major levels M1 / M2 are NOT drawn as lines (their exact prices stay in the levels "
                     "table above). Shaded horizontal zones = the engine's own areas (each built from one base, wick to body), with "
                     "their state: orange = supply (resistance), light blue = demand (support), dashed brown-grey outline = a broken "
                     "area. They are not the traded level L (thick green / red line).")
        lines.append("Areas (exact prices from OHLC data): role | low - high | state" if bands else
                     "Areas: the engine row carries no areas, so none are drawn.")
        for b in sorted(bands, key=lambda z: -z["hi"]):
            lines.append(f"  {'supply' if b['role'] == 'resistance' else 'demand'} | {b['lo']:,.2f} - {b['hi']:,.2f} | {b['state']}")
    elif bands is not None:                                             # setting vision_chart_bands ON (R1, TA4): chart legend + prices
        lines.append("Chart note: on this chart the major levels M1 / M2 are NOT drawn as lines (their exact prices stay in the levels "
                     "table above). Shaded horizontal zones = S/R bands (2+ real reaction touches, low-high from the reaction candles): "
                     "orange = supply (resistance), light blue = demand (support), dashed brown-grey outline = the most recently broken "
                     "band. They are not the traded level L (thick green / red line).")
        if bands:
            lines.append("Bands (exact prices from OHLC data): role | low - high | reaction touches | state")
            for b in sorted(bands, key=lambda z: -z["hi"]):
                role = "supply" if b["role"] == "resistance" else "demand"
                lines.append(f"  {role} | {b['lo']:,.2f} - {b['hi']:,.2f} | {b['touches']} | {b['state']}")
        else:
            lines.append("Bands: none pass the band rule near price, so none are drawn.")
    ll = ctx.get("l_line")
    if ll:
        brk = ("yes - " + ll["today_role"]) if ll["broken"] else (
            "no - an earlier close beyond was RECLAIMED (closed back: FALSE BREAK)" if ll.get("reclaimed") else "no")
        lines.append(f"Traded level L: price approached L {ll['approach']}; before the latest bars L was {ll['earlier_role']}; a close "
                     f"beyond that held (completed bars only): {brk}; price is now {ll.get('spot_side', '?')} L.")
    room = ctx.get("room") or {}
    if not ctx:
        pass
    if not ctx:
        pass
    elif room.get("next_name"):
        tight = room.get("next_mr") is not None and room["next_mr"] < TIGHT_ROOM_MR
        lines.append(f"Room: next opposing level in the trade direction = {room['next_name']} at {room['next_price']:,.2f}"
                     + (" (broken today = flip, now acts against the trade)" if room.get("next_flip") else f" ({room.get('next_role')})")
                     + f", {_f(room.get('next_mr'), 2)} x median range away" + (f" - ROOM TIGHT ({room['next_name']})." if tight else "."))
    else:
        lines.append("Room: no opposing reference / major level in the trade direction within the data.")
    if ctx and ctx.get("recent_breaks"):
        lines.append("Levels broken IN THE TRADE DIRECTION by the signal bar or the bars just before it: "
                     + ", ".join(f"{x['name']}" for x in ctx["recent_breaks"]) + " (= breakout entry).")
    if room.get("invalidation_mr") is not None:
        lines.append(f"Invalidation: {_f(ctx.get('invalidation', sig.get('invalidation')), 2)} ({ctx.get('invalidation_source', 'bot')}), "
                     f"{room['invalidation_mr']:.2f} x median range away.")
    sb = ctx.get("signal_bar") or {}
    if sb:
        if ctx.get("spot_signal") is not None and abs(float(ctx["spot_signal"]) - float(ctx.get("spot") or 0)) > 1e-9:
            lines.append(f"Spot at signal {ctx['spot_signal']:,.2f}; at evaluation (bar close) {ctx['spot']:,.2f} - levels / room use the latter.")
        lines.append("Signal bar: " + ("closed." if sb["closed"] else "NOT CLOSED yet - the reversal candle is not final."))
    lines += gap_lines(ctx.get("gap_ctx"))                               # M56 V3: no time / opening-window / expiry lines
    g = tags.get("gate") if isinstance(tags.get("gate"), dict) else None
    if g:                                                                # level bots confirmation (§9): engine चं वाचन — Vision ने तपासावं
        a = g.get("area") or [None, None]
        lines.append(f"Confirmation gate (engine reading, please audit): trend {g.get('trend')}; area {_f(a[0], 2)}-{_f(a[1], 2)} "
                     f"({'demand' if g.get('side') == 'BULLISH' else 'supply'}); commitment {g.get('form')} on {g.get('tf')}; "
                     f"entry {_f(g.get('entry'), 2)}; engine reference (information only — the trade's SL / target are the owner's "
                     f"dashboard settings): SL {_f(g.get('sl'), 2)}, target {_f(g.get('target'), 2)}"   # Abhi RR2
                     + (f", R:R {g.get('rr')}" if g.get("rr") is not None else "") + ". "   # R:R फक्त dashboard rr gate चालू असेल तर
                     +
                     "Check zone, trend, pullback and trigger.")
    rest = {k: v for k, v in tags.items() if k not in ("gate", "entry_pa_evidence")}   # T9 PA list: card only — Vision's input
    # (and its paid prompt size) stays as before (OPEN_QUESTIONS T9-2)
    if rest:
        lines.append("Bot tags: " + ", ".join(f"{k}={v}" for k, v in sorted(rest.items())))
    lines.append("Audit this signal against the playbook and fill the JSON.")
    return "\n".join(lines)


def _gap_desc(g):
    if g.get("atr_missing"):
        return " (ATR unavailable)"
    if g["class"] == "G0":
        return " (noise, no gap)"
    tr = (f"{'WITH' if g['with_trend'] else 'AGAINST'} the daily trend ({g['trend']})" if g["trend"] in ("up", "down")
          else f"no clear daily trend ({g['trend']})")
    return f", {g['direction']}, {g['location']} the prior day's range, {tr}"


def gap_lines(g):
    """Signal text: gap संदर्भ (OHLC वरून अचूक आकडे)."""
    if not g:
        return ["Gap context: unavailable."]
    if g.get("error") or g.get("pdc") is None:
        return [f"Gap context: unavailable ({g.get('error') or g.get('reason')})."]
    out = [f"Gap: open {g['open']:,.2f} vs previous close {g['pdc']:,.2f} = {g['gap']:+,.2f} ({g['gap_pct']:+.2f}%), "
           f"{_f(g.get('gap_atr'), 2)} x daily ATR ({_f(g.get('atr14'), 1)}) -> class {g['class']}"
           + _gap_desc(g)
           + (f", prior leg {g['leg_atr']:+.1f} x ATR" if g.get("leg_atr") is not None else "") + "."]
    if g["class"] != "G0":
        out.append(f"Gap fill so far: {g['fill_pct']:.0f}%; previous close touched: {'yes' if g['pdc_touched'] else 'no'}; acceptance beyond the "
                   f"previous close: {'yes' if g['pdc_acceptance'] else 'no'}. Behaviour after the gap (re-decided on every closed bar): "
                   f"{g['behaviour']}"
                   + (f" (history: {', '.join(g['behaviour_history'])})" if g.get("behaviour_history") else "") + "."
                   + (f" Gap edge: {g['edge']:,.2f}." if g.get("edge") else ""))
    for u in (g.get("old_gaps") or [])[:4]:
        out.append(f"Old unfilled gap (gap {u['dir']}): remaining {u['low']:,.2f}-{u['high']:,.2f}, "
                   f"{u['filled_pct']:.0f}% filled.")
    return out


def build_request(png, sig, model, max_tokens=None, effort=None, thinking=None):
    if not model:
        raise ValueError("VISION_SIGNAL_MODEL env not set")
    params = {
        "model": model,
        "max_tokens": int(max_tokens or max_output_tokens()),
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
                   {"type": "text", "text": ELLIOTT_INFO, "cache_control": {"type": "ephemeral"}}],   # M56 V6: Elliott = information
        "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.standard_b64encode(png).decode("utf-8")}},
            {"type": "text", "text": signal_text(sig)}]}],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
    }
    if effort:
        params["output_config"]["effort"] = effort
    if thinking:
        params["thinking"] = {"type": thinking}
    return params


def validate(raw):
    """(स्वच्छ dict, error|None). Enum अवैध ⇒ error (⇒ unavailable)."""
    if not isinstance(raw, dict):
        return None, "no JSON object"
    out = {}
    for k, allowed in ENUMS.items():
        v = str(raw.get(k, "")).strip().lower()
        canon = {x.lower(): x for x in allowed}                          # gap_setup "A/B/C" — case-insensitive, मूळ रूपात
        if v not in canon:
            return None, f"{k} invalid: {raw.get(k)!r}"
        out[k] = canon[v]
    try:
        conf = float(raw.get("confidence"))
    except (TypeError, ValueError):
        return None, "confidence invalid"
    if conf != conf:
        return None, "confidence NaN"
    out["confidence"] = min(1.0, max(0.0, conf))
    note = raw.get("elliott_note")
    out["elliott_note"] = (str(note).strip()[:100] or None) if note not in (None, "null") else None
    out["reason"] = str(raw.get("reason") or "").strip()[:160]
    return out, None


def usage_of(message):
    u = getattr(message, "usage", None)
    g = (lambda k: int(getattr(u, k, 0) or 0)) if u is not None else (lambda k: 0)
    return {"input_tokens": g("input_tokens"), "output_tokens": g("output_tokens"), "cache_read": g("cache_read_input_tokens"),
            "cache_write": g("cache_creation_input_tokens")}


def parse_message(message):
    """(data, error, usage)."""
    usage = usage_of(message)
    stop = getattr(message, "stop_reason", None)
    if stop == "refusal":
        return None, "refusal", usage
    if stop == "max_tokens":
        return None, "max_tokens reached", usage
    text = next((b.text for b in (getattr(message, "content", None) or []) if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, "no text reply", usage
    try:
        raw = json.loads(text)
    except ValueError as exc:
        return None, f"JSON parse: {exc}", usage
    data, err = validate(raw)
    return data, err, usage


TIGHT_ROOM_MR = 1.0                                                     # spec: पुढचा विरोधी level < ~1 median range ⇒ cramped


def apply_facts(a, ctx, direction=None):
    """Code ला आधीच माहीत असलेली तथ्यं (OHLC वरून) model च्या उत्तरावर लादणे — नियम model ने ती पुन्हा लिहिण्यावर अवलंबून नकोत.
    फक्त कडक दिशेने (M56 V3: no clock fact any more): room < TIGHT_ROOM_MR × median range ⇒ tight; संदर्भ नाही ⇒ room unclear. रिटर्न (a, बदल).
    T-5: an engine signal's context (vision/engine_audit.engine_ctx) ⇒ the engine audit's own facts (no session / gap / L-line fact)."""
    if _engine(ctx):
        from . import engine_audit as EA
        return EA.apply_facts(a, ctx)
    if not a:
        return a, []
    a, ch = dict(a), []
    if not ctx:
        if a.get("room_to_next_level") != "unclear":
            a["room_to_next_level"] = "unclear"
            ch.append("room=unclear (no context)")
        return a, ch
    sb = ctx.get("signal_bar") or {}
    if sb and not sb.get("closed") and a.get("reversal_valid") == "yes":   # तुमचा नियम 1c: signal bar बंद नाही ⇒ reversal unclear ⇒ gray
        a["reversal_valid"] = "unclear"
        ch.append("reversal_valid=unclear (signal bar not closed)")
    why = None
    rb = ctx.get("recent_breaks") or []
    if direction and rb:                                                 # तुमचा नियम 2b: signal bar / मागचे 3 bars नी trade दिशेने level तोडला
        why = "recent real break in trade direction: " + ", ".join(f"{x['name']} {x['at']}" for x in rb)
    if why and a.get("is_breakout_entry") != "yes":
        a["is_breakout_entry"] = "yes"
        ch.append(f"is_breakout_entry=yes ({why})")
    nm = (ctx.get("room") or {}).get("next_mr")
    if nm is not None and nm < TIGHT_ROOM_MR and a.get("room_to_next_level") == "enough":
        a["room_to_next_level"] = "tight"
        ch.append(f"room=tight ({nm:.2f}x)")
    return a, ch


# Code-only pre-verdict: vision "सगळं ठीक / agree" म्हणाला असता तरी code चे नियम काय म्हणतात (vision शिवाय, खर्च 0)
NEUTRAL = {"htf_trend": "up", "setup_structure": "range", "trend_context": "with", "level_real": "yes", "level_kind": "swing_origin",
           "confluence": "yes", "wave_position": "abc_end", "correction_complete": "yes", "false_break_reclaim": "no", "reversal_touch": "yes",
           "reversal_reclaim": "yes", "reversal_strength": "yes", "reversal_close_location": "good", "reversal_valid": "yes",
           "is_breakout_entry": "no", "room_to_next_level": "enough", "false_break_risk": "low",
           "gap_class_agrees": "yes", "gap_behaviour": "no_gap", "gap_setup": "none", "line_structure": "up", "line_vs_candles": "consistent",
           "elliott_note": "", "verdict": "agree", "reason": "", "confidence": 1.0}


def pre_verdict(ctx, direction, disagree_rules=None, gray_rules=None):
    """(verdict, {"disagree": […], "gray": […]}, code तथ्यं) — फक्त OHLC वरून (vision शिवाय)."""
    a, facts = apply_facts(dict(NEUTRAL), ctx, direction)
    d, g = rule_hits(a, disagree_rules, gray_rules, ctx, direction)
    return code_verdict(a, disagree_rules, gray_rules, ctx, direction), {"disagree": d, "gray": g}, facts


def rule_hits(a, disagree_rules=None, gray_rules=None, ctx=None, direction=None):
    """(disagree ids, gray ids) जे या audit ला लागतात. None ⇒ सगळे नियम चालू. T-5: engine context ⇒ the engine checklist's own ids."""
    if _engine(ctx):
        from . import engine_audit as EA
        return EA.rule_hits(a, ctx)
    dr = DISAGREE_RULES if disagree_rules is None else {k: v for k, v in DISAGREE_RULES.items() if k in disagree_rules}
    gr = GRAY_RULES if gray_rules is None else {k: v for k, v in GRAY_RULES.items() if k in gray_rules}
    code = code_facts(ctx, direction)
    d = [k for k, spec in dr.items() if (code.get(k) if spec == "code" else a.get(spec[0]) in spec[1])]
    g = []
    for k, spec in gr.items():
        if k == "unclear":
            if any(a.get(f) == "unclear" for f in ENUMS if f not in UNCLEAR_EXEMPT):
                g.append(k)
        elif k == "gap_c_alone":
            if a.get("gap_setup") == "C" and a.get("confluence") != "yes":
                g.append(k)
        elif spec == "code":
            if code.get(k):
                g.append(k)
        elif a.get(spec[0]) in spec[1]:
            g.append(k)
    return d, g


def code_facts(ctx, direction=None):
    """Gap नियमांची code-तथ्यं (OHLC वरून, model वर अवलंबून नाहीत)."""
    g = (ctx or {}).get("gap_ctx") or {}
    out = {}                                                             # M56 V3: no event-day (day framing) fact
    ll = (ctx or {}).get("l_line") or {}
    if direction and ll:
        bull_ = str(direction).upper().startswith("BULL")
        # 2a: bear call ⇒ किंमत L कडे खालून; bull put ⇒ वरून. उलट ⇒ disagree
        out["wrong_approach"] = ll.get("approach") == ("from below" if bull_ else "from above")
        # 2c: L चा bot-role आणि आजचं वागणं विरोधी (resistance म्हणून trade पण held_as_support, आणि उलट)
        br, tr_ = ll.get("bot_role"), ll.get("today_role")
        out["role_conflict"] = (br == "RESISTANCE" and tr_ == "held_as_support") or (br == "SUPPORT" and tr_ == "held_as_resistance")
    if not g.get("has_gap"):
        return out
    bull = str(direction or "").upper().startswith("BULL")
    with_gap = (g.get("direction") == "up") == bull
    mr = (ctx or {}).get("median_range") or 0.0
    lvl = (ctx or {}).get("level")
    near = lvl is not None and any(x is not None and abs(float(lvl) - float(x)) <= 0.5 * mr for x in (g.get("pdc"), g.get("edge")))
    out["gap_chase"] = g.get("class") in ("G3", "G5") and with_gap and float(g.get("fill_pct") or 0) < 25 and not near
    out["gap_b_pdc_accept"] = g.get("class") in ("G3", "G5") and with_gap and bool(g.get("pdc_acceptance"))
    return out


def code_verdict(a, disagree_rules=None, gray_rules=None, ctx=None, direction=None):
    """एका audit चा verdict: नियमांनी ठरलेली पातळी किंवा vision चा स्वतःचा verdict — जो जास्त कडक तो (नियमांपेक्षा positive कधीच नाही).
    T-5: engine context ⇒ the engine audit's floor (its own checklist only; the old rules are context lines, never the floor)."""
    if _engine(ctx):
        from . import engine_audit as EA
        return EA.code_verdict(a, ctx)
    if not a:
        return "unavailable"
    d, g = rule_hits(a, disagree_rules, gray_rules, ctx, direction)
    floor = "disagree" if d else ("gray" if g else "agree")
    own = a.get("verdict") if a.get("verdict") in SEVERITY else "gray"
    return max(floor, own, key=SEVERITY.get)


def _engine(ctx):
    """T-5: the context was built for an engine signal's engine audit (vision/chart.render marks it)."""
    return isinstance(ctx, dict) and ctx.get("signal_source") == "engine"


def combine(verdicts):
    """2 audits: एक unavailable ⇒ दुसरा; दोन्ही सारखे ⇒ तोच; असहमत ⇒ gray."""
    vs = [v for v in verdicts if v and v != "unavailable"]
    if not vs:
        return "unavailable"
    return vs[0] if len(set(vs)) == 1 else "gray"


HTTP_HEADERS = {"Accept-Encoding": "gzip, deflate"}                       # never brotli: an old `brotli` (<1.2) breaks httpx's decoder


def make_client(timeout_sec=20):
    import anthropic
    return anthropic.Anthropic(timeout=float(timeout_sec), max_retries=1, default_headers=HTTP_HEADERS)


CONNECT_RETRY_WAIT_SEC = (3, 8)                                             # a failed CONNECTION is retried after these waits


def _connect_failed(exc):
    """The request never reached the API (DNS / TCP / TLS) ⇒ not billed ⇒ safe to retry. A timeout (the request may have been processed
    and billed) is never retried here."""
    names = {c.__name__ for c in type(exc).__mro__}                      # by the SDK's class names (APITimeoutError ⊂ APIConnectionError)
    return "APIConnectionError" in names and "APITimeoutError" not in names


HTTP_LOGGERS = ("httpx", "httpcore", "anthropic")


def std_http_loggers():
    """30 Oct (V7 on the VPS: APIConnectionError ← "TypeError: process() takes no keyword arguments"): rendering a chart with kaleido
    loads choreographer / logistro, which replaces Python's logger class; httpx / httpcore create some loggers lazily at the first
    request, so they became logistro loggers and that version breaks the call. Before every Vision call the HTTP libraries' loggers
    are plain `logging.Logger` again (only theirs — the rest of the process is left as it is); new loggers made during the call too.
    The 30 Oct root cause was the brotli decoder (old `brotli` < 1.2; see HTTP_HEADERS); this guard is kept, it is covered by a test."""
    import logging
    for name, lg in list(logging.Logger.manager.loggerDict.items()):
        if name.split(".")[0] in HTTP_LOGGERS and isinstance(lg, logging.Logger) and type(lg) is not logging.Logger:
            lg.__class__ = logging.Logger
    return logging.getLoggerClass()


def create(client, params, sleep=time.sleep):
    """The one Vision API call of every path (signal audit, engine audit): (message, None) | (None, error words). Never raises. A failed
    connection (never reached the API ⇒ never billed) is retried after CONNECT_RETRY_WAIT_SEC; never a timeout or an API answer (no
    double billing). The error names the connection error's root (DNS / TLS / reset)."""
    import logging
    prev = std_http_loggers()
    logging.setLoggerClass(logging.Logger)                                 # loggers httpcore creates during the call: plain
    try:
        return _create(client, params, sleep)
    finally:
        logging.setLoggerClass(prev)
        std_http_loggers()


def _create(client, params, sleep):
    for wait in (*CONNECT_RETRY_WAIT_SEC, None):
        try:
            return client.messages.create(**params), None
        except Exception as exc:
            if wait is not None and _connect_failed(exc):
                sleep(wait)
                continue
            cause = exc.__cause__ or exc.__context__
            why = f" ({type(cause).__name__}: {str(cause)[:120]})" if cause is not None and _connect_failed(exc) else ""
            return None, f"API: {type(exc).__name__}: {str(exc)[:160]}{why}"


def one_call(client, params, sleep=time.sleep):
    """(data, error, usage, latency_ms). कधीच raise नाही. The call = `create` (connection retry, root cause)."""
    t0 = time.monotonic()
    msg, err = create(client, params, sleep)
    if msg is None:
        return None, err, {}, int((time.monotonic() - t0) * 1000)
    data, err, usage = parse_message(msg)
    return data, err, usage, int((time.monotonic() - t0) * 1000)


def audit(client, png, sig, model, second_below=0.6, effort=None, thinking=None, on_usage=None, budget_ok=None, disagree_rules=None,
          gray_rules=None):
    """1 audit (+ confidence < second_below असेल तर दुसरा, budget_ok() खरं असेल तरच). रिटर्न dict:
    {verdict, audits:[…], verdicts:[…], confidence, cost_usd, usage, latency_ms, error, prompt_version, model}.
    T-5 (DECISIONS 31, provisional): an engine signal (`vision_engine_audit = engine`) ⇒ vision/engine_audit.audit (the engine's own
    reading, the method's concepts; old rules = context lines only). Every other signal: this audit, unchanged."""
    from . import engine_audit as EA
    if EA.use_engine(sig):
        return EA.audit(client, png, sig, model, second_below=second_below, effort=effort, thinking=thinking, on_usage=on_usage,
                        budget_ok=budget_ok, disagree_rules=disagree_rules, gray_rules=gray_rules)
    params = build_request(png, sig, model, effort=effort, thinking=thinking)
    out = {"audits": [], "verdicts": [], "cost_usd": 0.0, "latency_ms": 0, "error": None, "prompt_version": PROMPT_VERSION, "model": model,
           "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read": 0, "cache_write": 0}}
    for n in range(2):
        if n == 1:
            first = out["audits"][0] if out["audits"] else None
            if first is None or first["confidence"] >= second_below or (budget_ok is not None and not budget_ok()):
                break
        data, err, usage, ms = one_call(client, params)
        if not usage and err and err.startswith("API"):
            # timeout / network: request कदाचित billed झाला असेल पण usage मिळाला नाही ⇒ budget साठी सावध अंदाज नोंदवतो
            usage = {"input_tokens": 2050, "output_tokens": max_output_tokens(), "estimated": 1}
        c = cost_usd(model, usage)
        out["cost_usd"] += c
        out["latency_ms"] += ms
        for k in out["usage"]:
            out["usage"][k] += usage.get(k, 0)
        if on_usage is not None and usage:
            on_usage(usage, c)
        if err:
            out["error"] = err
            out["verdicts"].append("unavailable")
            if n == 0:
                break
            continue
        data, facts = apply_facts(data, sig.get("ctx"), sig.get("direction"))
        if facts:
            data["code_overrides"] = facts
        out["audits"].append(data)
        cx, dr = sig.get("ctx"), sig.get("direction")
        out["verdicts"].append(code_verdict(data, disagree_rules, gray_rules, cx, dr))
        out.setdefault("rule_hits", []).append(dict(zip(("disagree", "gray"), rule_hits(data, disagree_rules, gray_rules, cx, dr))))
    out["verdict"] = combine(out["verdicts"])
    if len(out["verdicts"]) == 2 and out["verdicts"][1] == "unavailable" and out["verdict"] == "agree":
        out["verdict"] = "gray"                                          # कमी confidence चा agree, दुसरा audit अयशस्वी ⇒ entry नाही
    confs = [a["confidence"] for a in out["audits"]]
    out["confidence"] = round(sum(confs) / len(confs), 3) if confs else None
    out["cost_usd"] = round(out["cost_usd"], 6)
    return out
