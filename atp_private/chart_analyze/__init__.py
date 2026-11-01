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
- No hybrid entry point yet: ATP's hybrid mode then shows its own code reading ("Advanced analysis (code)").

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
PROMPT_VERSION = "atp_chart_image_v1"


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

Coordinates: pixels of this image, x to the right, y down, 0 <= x <= WIDTH, 0 <= y <= HEIGHT.

Keys (enum values exactly as written):
{
 "recognised": {"symbol": str|null, "exchange": str|null, "timeframe": str|null, "first_bar": str|null, "last_bar": str|null},
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
   "setup_lines": [{"kind": "trigger"|"invalidation"|"next_area", "y": number, "price": number|null, "note": str}, ...]}
}
Required: story (at least one paragraph), trend.side, setup, scenarios.primary and scenarios.alternative.
"what_to_wait_for" only when the setup is not formed.
"""

TASK_TEXT = ("Read this chart image ({width} x {height} pixels) with the Method Pack and return the JSON object described "
             "in the answer format. Describe only; ATP places no order from it.")

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
