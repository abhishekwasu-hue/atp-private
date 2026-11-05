"""atp_private.chart_analyze: the Analyze-a-chart engine that ATP's `backend/app/chart_analyze/provider.py` imports.

Owner order M79, W5 (the provider shim). The method the model reads is the Method Pack of the imported Trade engine
(`atp_private/trade_engine/docs/knowledge/method_pack.md`, engine-snapshot-v2, Trade commit 813358b), loaded as is with
its own version check (`vision.method_pack.load`: the header version must equal the body hash). Nothing of the method is
written here: this module adds only the answer format, which is ATP's generic output contract
(`app/chart_analyze/contract.py`), and the platform's wording rules (signals, not advice).

- `image_only_instructions(width, height)`: system = the Method Pack + the answer format; user = the task.
- `parse_image_only(reply, width, height)`: the first JSON object in the reply (a fenced block is allowed). ATP's
  contract then validates it, filters every text and drops what does not fit; a reply without an object is an error,
  which ATP records as a failed analysis.
- `hybrid_instructions(width, height, facts)` / `parse_hybrid(reply, facts)` (owner 5 Nov: "Advanced analysis = code AND
  AI"): ATP's code reads and draws the structure (exact prices); the model receives ATP's own chart picture and those
  facts and writes the study in the Method Pack (story, state, setup, scenarios, what to wait for). Every price it gives
  must be one of the facts' prices: any other price is removed in `parse_hybrid` (never a price invented or read from
  a picture).

The AI only describes the chart. It never places, blocks or changes an order (ADR-0006); this module has no order,
broker or execution import.
"""
import json
import re
from dataclasses import dataclass

from atp_private.trade_engine.vision import method_pack as _MP

ENGINE_IMPORTED = True
NAME = "atp-trade-engine"
VERSION = "engine-snapshot-v2+813358b"
PROMPT_VERSION = "atp_chart_image_v3"   # v3 (owner CA-Q3): choch line, last_price, RSI-pane divergence   # v2 (owner CA-D1/D2, 3 Nov): story by structure, no calendar words; stock volume; lengths


@dataclass(frozen=True)
class Instructions:
    """The same three fields as ATP's `app.chart_analyze.provider.Instructions` (read by attribute)."""

    system: str
    user: str
    prompt_version: str


FORMAT_TEXT = """\
ANSWER FORMAT (ATP output contract). Reply with ONE JSON object and nothing else (no prose before or after it).

Wording rules (always):
- Describe the chart with the Method Pack above, in structure words only. Never write buy, sell, target, stop-loss,
  entry advice, a recommendation or a guarantee. Conditions only ("a close below the area would ...").
- Read only what the picture shows. Prices come from the price axis and are approximate. If something cannot be read,
  say so and use "unclear" / "none" instead of guessing.
- Evidence is listed, never scored: no score, probability or confidence number anywhere.
- Tell the story by STRUCTURE only: swings (HH / HL / LH / LL), impulses, corrections, areas and breaks, in the order
  they happen ("the first impulse ...", "the next lower high ..."). Never a month, date, weekday, session or clock word
  anywhere in the story, trend, state, scenarios, levels or evidence (the chart is one continuous unit). Only
  "recognised.first_bar" / "recognised.last_bar" may name the axis dates.
- Write for the user, not about your inputs: never mention FACTS, OHLC text, prompts, the Method Pack or which inputs
  are missing, and never explain which instrument the chart is not.
- Volume: for an index read its near-month futures volume when the picture shows it; for a single stock read the
  stock's own volume bars on this chart. Say "not readable" only when no volume is visible.
- Lengths (longer text is cut): each story paragraph and each scenario <= 550 characters; trend.text,
  current_state.text, rsi.text, waiting_for and what_to_wait_for.condition <= 300; every note, evidence reason and
  next-area text <= 150; names <= 70; recognised.first_bar / last_bar <= 40 (for example "Jul 2026").
- current_state.text starts with the direction price is moving now (up / down / sideways), so it never reads as the
  trend side.

Coordinates: pixels of this image, x to the right, y down, 0 <= x <= WIDTH, 0 <= y <= HEIGHT.

Keys (enum values exactly as written):
{
 "recognised": {"symbol": str|null, "exchange": str|null, "timeframe": str|null, "first_bar": str|null, "last_bar": str|null,
                "last_price": number|null},       (the last candle's close read from the price axis)
 "story": [str, ...]                      (the chart's story from the left edge to the last candle, a few short paragraphs),
 "trend": {"side": "up"|"down"|"sideways"|"unclear", "text": str},
 "current_state": {"phase": "pullback"|"handover"|"commitment"|"trending"|"range"|"unclear", "text": str},
 "rsi": {"divergence": "bullish"|"bearish"|"none", "text": str}   ("none" when no RSI pane is visible),
 "setup": {"side": "bull_put"|"bear_call"|"none", "label": "A"|"B"|null, "status": "formed"|"forming"|"none",
           "waiting_for": str|null, "trigger": {"text": str, "price": number|null},
           "invalidation": {"text": str, "price": number|null}, "next_areas": [{"text": str, "price": number|null}, ...]},
 "evidence": [{"name": str, "present": true|false, "reason": str}, ...],
 "scenarios": {"primary": str, "alternative": str, "primary_invalidated_at": {"text": str, "price": number|null}},
 "what_to_wait_for": {"condition": str, "alert": {"kind": "above"|"below", "price": number}
                      | {"kind": "between", "low": number, "high": number} | null} | null,
 "htf_context": [{"timeframe": str, "trend": "up"|"down"|"sideways"|"unclear",
                  "nearest_areas": [{"side": "buyer"|"seller", "state": "fresh"|"tested"|"broken"|"flipped",
                                     "price_low": number, "price_high": number}, ...]}, ...]   ([] when not visible),
 "key_levels": [{"kind": "area"|"line", "name": str, "side": "buyer"|"seller"|null,
                 "state": "fresh"|"tested"|"broken"|"flipped"|null, "price_low": number, "price_high": number}, ...],
 "annotations": {
   "swings": [{"label": "HH"|"HL"|"LH"|"LL", "x": number, "y": number, "price": number|null}, ...],
   "areas": [{"id": str, "side": "buyer"|"seller", "state": "fresh"|"tested"|"broken"|"flipped",
              "x0": number, "y0": number, "x1": number, "y1": number, "price_low": number|null, "price_high": number|null,
              "note": str}, ...],
   "lines": [{"id": str, "name": str, "x0": number, "y0": number, "x1": number, "y1": number,
              "touches": [{"x": number, "y": number}, ...], "note": str}, ...],
   "rsi_divergence": {"kind": "bullish"|"bearish", "price": {"x0": number, "y0": number, "x1": number, "y1": number},
                      "rsi": {"x0": number, "y0": number, "x1": number, "y1": number}|null, "note": str} | null,
   "commitment_candle": {"x": number, "y": number, "note": str} | null,
   "ltf_choch": {"x": number, "y": number, "note": str} | null,
   "setup_lines": [{"kind": "trigger"|"invalidation"|"next_area", "y": number, "price": number|null, "note": str}, ...],
   "choch": {"x0": number, "y0": number, "x1": number, "y1": number, "price": number|null, "note": str} | null}
     (the swing level whose close-through is the latest CHoCH, drawn from that swing to the breaking candle; null if none)
}
Required: story (at least one paragraph), trend.side, setup, scenarios.primary and scenarios.alternative.
"what_to_wait_for" only when the setup is not formed.
When an RSI pane is visible and a divergence is read, give "rsi_divergence.rsi" on the RSI line too (the two RSI
points of the same two swings), so it is drawn in both panes.
"""

TASK_TEXT = ("Read this chart image ({width} x {height} pixels) with the Method Pack and return the JSON object described "
             "in the answer format. Describe only; ATP places no order from it.")

HYBRID_PROMPT_VERSION = "atp_chart_hybrid_v1"

HYBRID_FORMAT_TEXT = """\
ANSWER FORMAT (ATP output contract, Advanced analysis). Reply with ONE JSON object and nothing else.

How this works: ATP's code has already read the candles of this chart and drawn them in the picture you see. Its
reading comes with the request as exact numbers (the structure per timeframe, the protected level, the last break of
structure, the areas of interest above and below the last close, the swing levels). Your part is the STUDY: read that
structure with the Method Pack above and write what a trader following the method studies next.

Rules (always):
- Every price you write must be one of the prices in ATP's reading (an area edge, a swing level, the protected level,
  the last break, the last close). Never invent a price and never read one from the picture; when no price of the
  reading fits, use null.
- Structure words only. Never write buy, sell, target, stop-loss, entry advice, a recommendation or a guarantee.
  Conditions only ("a close below the area would ...").
- Evidence is listed, never scored: no score, probability or confidence number anywhere.
- Tell the story by STRUCTURE only (swings HH / HL / LH / LL, impulses, corrections, areas, breaks, in the order they
  happen). Never a month, date, weekday, session or clock word anywhere.
- Write for the user: never mention ATP's reading, FACTS, JSON, prompts or the Method Pack by name.
- Lengths (longer text is cut): each story paragraph and each scenario <= 550 characters; trend.text,
  current_state.text, waiting_for and what_to_wait_for.condition <= 300; every evidence reason and next-area text <= 150;
  names <= 70.
- current_state.text starts with the direction price is moving now (up / down / sideways).

Keys (enum values exactly as written):
{
 "story": [str, ...],
 "trend": {"side": "up"|"down"|"sideways"|"unclear", "text": str},
 "current_state": {"phase": "pullback"|"handover"|"commitment"|"trending"|"range"|"unclear", "text": str},
 "rsi": {"divergence": "none", "text": ""},
 "setup": {"side": "bull_put"|"bear_call"|"none", "label": "A"|"B"|null, "status": "formed"|"forming"|"none",
           "waiting_for": str|null, "trigger": {"text": str, "price": number|null},
           "invalidation": {"text": str, "price": number|null}, "next_areas": [{"text": str, "price": number|null}, ...]},
 "evidence": [{"name": str, "present": true|false, "reason": str}, ...],
 "scenarios": {"primary": str, "alternative": str, "primary_invalidated_at": {"text": str, "price": number|null}},
 "what_to_wait_for": {"condition": str, "alert": {"kind": "above"|"below", "price": number}
                      | {"kind": "between", "low": number, "high": number} | null} | null
}
Required: story (at least one paragraph), trend.side, setup, scenarios.primary and scenarios.alternative.
"what_to_wait_for" only when the setup is not formed.
"""

HYBRID_TASK_TEXT = ("This picture ({width} x {height} pixels) is ATP's chart of {symbol} on the {timeframe} candles. ATP's reading "
                    "of it, exact numbers:\n{reading}\nWrite the study as the JSON object described in the answer format. "
                    "Describe only; ATP places no order from it.")

FACT_KEYS = ("symbol", "timeframe", "last_close", "timeframes", "protected", "last_break", "areas", "levels", "trigger_candle")
PRICE_TOLERANCE = 0.0005          # a written price within 0.05 % of one of the reading's prices is that price


def hybrid_reading(facts):
    """ATP's reading as the model sees it: the structure facts only (the candles are in the picture), compact JSON."""
    return json.dumps({k: facts.get(k) for k in FACT_KEYS if facts.get(k) is not None}, separators=(",", ":"), default=str)


def fact_prices(facts):
    """Every price of ATP's reading: the last close, the protected level, the last break, each area's edges, each level."""
    out = []

    def add(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            out.append(float(v))
    add(facts.get("last_close"))
    add(facts.get("protected"))
    add((facts.get("last_break") or {}).get("price"))
    for a in facts.get("areas") or ():
        add(a.get("low"))
        add(a.get("high"))
    for lv in facts.get("levels") or ():
        add(lv.get("price"))
    for row in facts.get("timeframes") or ():
        add(row.get("protected"))
        add((row.get("last_break") or {}).get("price"))
    return sorted(set(out))


def keep_known_prices(raw, prices):
    """The reply with every price that is not one of the reading's prices set to null (an alert with an unknown price is
    dropped). Changes the dict in place and returns it."""
    def known(v):
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return False
        return any(abs(float(v) - p) <= p * PRICE_TOLERANCE for p in prices)

    def ref(r):
        if isinstance(r, dict) and r.get("price") is not None and not known(r.get("price")):
            r["price"] = None
    setup = raw.get("setup") if isinstance(raw.get("setup"), dict) else {}
    ref(setup.get("trigger"))
    ref(setup.get("invalidation"))
    for n in setup.get("next_areas") or ():
        ref(n)
    scen = raw.get("scenarios") if isinstance(raw.get("scenarios"), dict) else {}
    ref(scen.get("primary_invalidated_at"))
    wait = raw.get("what_to_wait_for") if isinstance(raw.get("what_to_wait_for"), dict) else None
    if wait is not None and isinstance(wait.get("alert"), dict):
        al = wait["alert"]
        vals = [al.get("price")] if al.get("kind") in ("above", "below") else [al.get("low"), al.get("high")]
        if not all(known(v) for v in vals):
            wait["alert"] = None
    for k in ("annotations", "recognised", "key_levels", "htf_context"):        # code draws and reads these in hybrid
        raw.pop(k, None)
    return raw


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


class Provider:
    """ATP's AnalysisProvider (image-only). `method_version` is the Method Pack's own version (its body hash)."""

    name = NAME
    version = VERSION

    def __init__(self, pack_path=None):
        self._pack, self.method_version = _MP.load(pack_path) if pack_path else _MP.load()

    def image_only_instructions(self, *, width: int, height: int) -> Instructions:
        fmt = FORMAT_TEXT.replace("WIDTH", str(int(width))).replace("HEIGHT", str(int(height)))
        system = self._pack.rstrip() + "\n\n" + fmt
        return Instructions(system=system, user=TASK_TEXT.format(width=int(width), height=int(height)),
                            prompt_version=f"{PROMPT_VERSION}+pack-{self.method_version}")

    def parse_image_only(self, reply: str, *, width: int, height: int) -> dict:
        return parse_json(reply)

    # --- Advanced analysis (code + AI): ATP's code reading, the model's study on top -----------------------------------
    def hybrid_instructions(self, *, width: int, height: int, facts: dict) -> Instructions:
        system = self._pack.rstrip() + "\n\n" + HYBRID_FORMAT_TEXT
        user = HYBRID_TASK_TEXT.format(width=int(width), height=int(height), symbol=facts.get("symbol") or "this symbol",
                                       timeframe=facts.get("timeframe") or "", reading=hybrid_reading(facts))
        return Instructions(system=system, user=user, prompt_version=f"{HYBRID_PROMPT_VERSION}+pack-{self.method_version}")

    def parse_hybrid(self, reply: str, *, facts: dict) -> dict:
        raw = keep_known_prices(parse_json(reply), fact_prices(facts))
        raw.setdefault("version", VERSION)
        raw.setdefault("method_version", self.method_version)
        return raw


def parse_json(reply):
    """The first JSON object in the reply: inside a ``` fence if there is one, else from the first "{". ValueError if none."""
    text = reply or ""
    fenced = _FENCE.search(text)
    candidates = ([fenced.group(1)] if fenced else []) + [text]
    decoder = json.JSONDecoder()
    for chunk in candidates:
        start = chunk.find("{")
        while start != -1:
            try:
                obj, _ = decoder.raw_decode(chunk, start)
            except ValueError:
                start = chunk.find("{", start + 1)
                continue
            if isinstance(obj, dict):
                return obj
            start = chunk.find("{", start + 1)
    raise ValueError("the reply holds no JSON object")


def get_provider():
    return Provider()
