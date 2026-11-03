"""Chart reading with Claude vision: Abhi's method, or one independent book strategy.

Ported from the private repo trade-data, `books/ai/chart_read.py` at commit 6dd8bf4 (Trade order M85; ATP order M86 W1).
The reader logic is kept as is; the port changes only what ATP needs:
- charts come in as bytes: `(label, image_bytes, media_type)` instead of a file path;
- the model and the effort are parameters (defaults `MODEL` / "high"), not hard-coded;
- the client is always given by the caller: this module never builds a client and never reads an API key;
- the data files (`prompts/`, `strategies/`) live in this package, byte-for-byte copies of trade-data's
  `books/ai/prompts/` and `books/strategies/`; the env `ATP_CHART_READER_DIR`, if set, points to another folder that
  holds `prompts/` and `strategies/` (read once, at import);
- the CLI is left out (not needed in ATP).

Two kinds of read, never mixed (owner rule):
  ABHI (default)  Abhi's own method only: trend -> buyer/seller area -> correction with weakening
                  momentum -> commitment candle. No book material enters this prompt.
  <BOOK_ID>       ONE book's own strategy, kept independent and labelled with the book's name
                  (spec: strategies/<BOOK_ID>.md, section 8 JSON). Reference/testing only.

Information only: the output never carries strike / SL / target / lots / buy-sell calls (the prompt forbids
them, and `sanitize()` strips anything that slips through) and never frames the read by day/date/clock.

PRIVATE: this package stays in the private repo (atp-private). Never copy it to the public ATP repo.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ENV_DATA_DIR = "ATP_CHART_READER_DIR"


def _data_dir() -> Path:
    """The folder holding prompts/ and strategies/: ATP_CHART_READER_DIR if set, else this package."""
    other = os.environ.get(ENV_DATA_DIR, "").strip()
    return Path(other).expanduser() if other else PACKAGE_DIR


DATA_DIR = _data_dir()
PROMPT_DIR = DATA_DIR / "prompts"
STRATEGY_DIR = DATA_DIR / "strategies"
ABHI = "ABHI"
PROMPT_VERSION = {ABHI: "abhi_read_v5", "BOOK": "book_strategy_read_v5"}
MODEL = "claude-opus-5-5"
MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}

# ---------------------------------------------------------------- output schemas (structured outputs)
_NUM_OR_NULL = {"anyOf": [{"type": "number"}, {"type": "null"}]}
_STR_OR_NULL = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_TRI = {"type": "string", "enum": ["yes", "no", "unclear"]}


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


ABHI_SCHEMA = _obj({
    "trend": _obj({"direction": {"type": "string", "enum": ["up", "down", "sideways", "unclear"]},
                   "evidence": {"type": "string"}}),
    "areas": {"type": "array", "items": _obj({
        "side": {"type": "string", "enum": ["buyer", "seller"]},
        "price_low": _NUM_OR_NULL, "price_high": _NUM_OR_NULL,
        "chart": {"type": "string"}, "evidence": {"type": "string"}})},
    "correction": _obj({"present": {"type": "boolean"}, "area_index": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                        "momentum_weakening": _TRI, "evidence": {"type": "string"}}),
    "commitment_candle": _obj({"present": {"type": "boolean"}, "evidence": {"type": "string"}}),
    "area_of_interest_statement": {"type": "string"},
    "watch_next": {"type": "string"},
    "cannot_read": _STR_OR_NULL,
})

BOOK_SCHEMA = _obj({
    # P1 (owner decision): which side of the book's rules was scored on this chart
    "side_scored": {"type": "string", "enum": ["long", "short"]},
    "conditions": {"type": "array", "items": _obj({
        "id": {"type": "string"}, "status": {"type": "string", "enum": ["met", "not_met", "unclear"]},
        "evidence": {"type": "string"}})},
    "levels": {"type": "array", "items": _obj({
        "kind": {"type": "string"}, "price_low": _NUM_OR_NULL, "price_high": _NUM_OR_NULL,
        "chart": {"type": "string"}, "evidence": {"type": "string"}})},
    # P2: the bar number where the book's trigger last appeared (null if never); code decides what "recent" means
    "trigger_seen": _obj({"status": _TRI, "bar": {"anyOf": [{"type": "integer"}, {"type": "null"}]}, "evidence": {"type": "string"}}),
    # P3: invalidation of the side_scored read only
    "invalidated": _obj({"status": _TRI, "evidence": {"type": "string"}}),
    "statement": {"type": "string"},
    "cannot_read": _STR_OR_NULL,
})

# ---------------------------------------------------------------- sanitizer (owner rules C.3 / C.4, SEBI wording)
# Sentences carrying trade parameters or calls (any form of buy / sell / hold; owner rule) are removed; clock/date framing is flagged.
FORBIDDEN = re.compile(
    r"\b(stop[- ]?loss|SL|target(?:s)?|\d+\s*lots?|lot size|position size|risk[- ]?(?:to[- ]?)?reward|R\s*:\s*R|strike(?:s)?|"
    r"buy|buys|buying|bought|sell|sells|selling|sold|hold|holds|holding|held|go long|go short|enter (?:long|short)|entry order)\b", re.IGNORECASE)
TIME_FRAMING = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|yesterday|expiry day|"
    r"opening (?:hour|bell)|closing (?:hour|bell)|session|\d{1,2}:\d{2}\s*(?:am|pm)?|"
    r"\d{1,2}\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?))\b", re.IGNORECASE)
_SENT = re.compile(r"(?<=[.!?;])\s+")


@dataclass
class Sanitized:
    data: dict
    removed: list[str] = field(default_factory=list)
    time_flags: list[str] = field(default_factory=list)


def _clean_text(text: str, path: str, out: Sanitized, ignore: tuple[str, ...] = ()) -> str:
    kept = []
    for sent in _SENT.split(text):
        probe = sent
        for phrase in ignore:  # the book's own name (e.g. "Saturday Evening Post") is a label, not time framing
            probe = probe.replace(phrase, " ")
        if FORBIDDEN.search(probe):
            out.removed.append(f"{path}: {sent}")
            continue
        if TIME_FRAMING.search(probe):
            out.time_flags.append(f"{path}: {sent}")
        kept.append(sent)
    return " ".join(kept)


def sanitize(data: dict, ignore: tuple[str, ...] = ()) -> Sanitized:
    """Strip trade-parameter / call sentences from every string; flag time framing (kept, but reported).
    `ignore`: label phrases (the book's name) that are not checked."""
    out = Sanitized(data={})

    def walk(node, path):
        if isinstance(node, str):
            return _clean_text(node, path, out, ignore)
        if isinstance(node, list):
            return [walk(v, f"{path}[{i}]") for i, v in enumerate(node)]
        if isinstance(node, dict):
            return {k: walk(v, f"{path}.{k}" if path else k) for k, v in node.items()}
        return node

    out.data = walk(data, "")
    return out


# ---------------------------------------------------------------- book strategies (independent, by book name)
_SPEC_JSON = re.compile(r"^## 8\..*?```json\s*\n(.*?)```", re.S | re.M)
_REQUIRED_SPEC_KEYS = {"id", "book", "author", "edition", "summary", "conditions", "trigger", "invalidation", "not_coded"}


def load_strategy(strategy_id: str, folder: Path | None = None) -> dict:
    """Section 8 JSON of strategies/<ID>.md."""
    path = (folder or STRATEGY_DIR) / f"{strategy_id}.md"
    if not path.is_file():
        raise FileNotFoundError(f"no strategy spec {path}")
    m = _SPEC_JSON.search(path.read_text(encoding="utf-8"))
    if not m:
        raise ValueError(f"{path}: section 8 json block not found")
    spec = json.loads(m.group(1))
    missing = _REQUIRED_SPEC_KEYS - set(spec)
    if missing or spec["id"] != strategy_id:
        raise ValueError(f"{path}: bad spec (missing {sorted(missing)} or id != file name)")
    return spec


def list_strategies(folder: Path | None = None) -> list[dict]:
    out = []
    folder = folder or STRATEGY_DIR
    for p in sorted(folder.glob("*.md")):
        if p.name.startswith("_") or p.stem.upper() == "README":
            continue
        try:
            s = load_strategy(p.stem, folder)
            out.append({"id": s["id"], "book": s["book"], "author": s["author"], "edition": s["edition"],
                        "conditions": len(s["conditions"])})
        except (ValueError, json.JSONDecodeError) as e:
            out.append({"id": p.stem, "error": str(e)})
    return out


def needs_two_charts(spec: dict) -> list[str]:
    """P6: condition ids that can only be checked with a second chart (another average / group / market)."""
    return [c["id"] for c in spec["conditions"] if "two" in str(c.get("needs", "")).lower()]


def format_spec(spec: dict) -> str:
    lines = [f"Strategy id: {spec['id']}",
             f"Book: {spec['book']} - {spec['author']} ({spec['edition']})",
             f"Summary: {spec['summary']}",
             f"Sides the book states: {' and '.join(spec.get('sides', ['long', 'short']))}", "Conditions:"]
    lines += [f"- [{c['id']}] {c['text']} (needs: {c.get('needs', 'price')}; book {c.get('source', '')})" for c in spec["conditions"]]
    if spec["trigger"].get("stated", True) is False:
        lines.append("The book states NO trigger of its own; the text below is only its nearest description.")
    lines.append(f"Trigger (the book's own signal): {spec['trigger']['text']} (book {spec['trigger'].get('source', '')})")
    lines.append("Invalidation:")
    lines += [f"- {i['text']} (book {i.get('source', '')})" for i in spec["invalidation"]]
    return "\n".join(lines)


# ---------------------------------------------------------------- prompt building
# A chart is (label, image_bytes, media_type); only the label enters the prompt text.
Chart = tuple[str, bytes, str]


def _template(name: str) -> str:
    text = (PROMPT_DIR / name).read_text(encoding="utf-8")
    return re.sub(r"^<!--.*?-->\s*", "", text, flags=re.S)


def build_prompts(instrument: str, charts: list[Chart], facts: str, strategy: str = ABHI) -> tuple[str, str]:
    chart_list = ", ".join(f"{i + 1}) {c[0]}" for i, c in enumerate(charts))
    facts = facts.strip() or "(none)"
    if strategy == ABHI:
        return _template("system_v1.md"), _template("user_v1.md").format(instrument=instrument, chart_list=chart_list, facts=facts)
    spec = load_strategy(strategy)
    system = _template("system_book_v1.md").format(book=spec["book"], author=spec["author"], edition=spec["edition"])
    user = _template("user_book_v1.md").format(instrument=instrument, chart_list=chart_list, facts=facts,
                                               strategy=format_spec(spec), book=spec["book"])
    return system, user


def image_block(data: bytes, media_type: str) -> dict:
    if media_type not in MEDIA_TYPES.values():
        raise ValueError(f"unsupported image type: {media_type}")
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("chart image must be non-empty bytes")
    encoded = base64.standard_b64encode(bytes(data)).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": encoded}}


def build_request(instrument: str, charts: list[Chart], facts: str, strategy: str = ABHI, effort: str = "high",
                  model: str = MODEL) -> dict:
    system, user = build_prompts(instrument, charts, facts, strategy)
    content: list[dict] = []
    for label, data, media_type in charts:
        content.append({"type": "text", "text": f"Chart: {label}"})
        content.append(image_block(data, media_type))
    content.append({"type": "text", "text": user})
    schema = ABHI_SCHEMA if strategy == ABHI else BOOK_SCHEMA
    return {
        "model": model,
        "max_tokens": 16000,
        # Frozen system prompt first so repeated reads hit the prompt cache.
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": content}],
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        # Server-side refusal fallback (Anthropic-recommended routing by refusal category).
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }


def _label(strategy: str) -> dict:
    if strategy == ABHI:
        return {"id": ABHI, "name": "Abhi's method"}
    s = load_strategy(strategy)
    return {"id": s["id"], "name": f"{s['book']} ({s['author']}, {s['edition']})", "independent_book_strategy": True}


# ---------------------------------------------------------------- call
def read_charts(instrument: str, charts: list[Chart], facts: str = "", strategy: str = ABHI,
                effort: str = "high", client=None, model: str = MODEL) -> dict:
    """One read with the caller's (sync) anthropic client. The client is never built here and no key is read."""
    import anthropic

    if client is None:
        raise ValueError("read_charts needs the caller's anthropic client")
    req = build_request(instrument, charts, facts, strategy, effort, model)
    label = _label(strategy)
    two = needs_two_charts(load_strategy(strategy)) if strategy != ABHI else []
    version = PROMPT_VERSION[ABHI if strategy == ABHI else "BOOK"]
    try:
        resp = client.beta.messages.create(**req)
    except anthropic.RateLimitError as e:
        return {"status": "error", "strategy": label, "error": f"rate limited (retry-after {e.response.headers.get('retry-after', '?')}s)"}
    except anthropic.APIStatusError as e:
        return {"status": "error", "strategy": label, "error": f"API error {e.status_code}: {e.message}"}
    except anthropic.APIConnectionError:
        return {"status": "error", "strategy": label, "error": "network error"}

    usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens,
             "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", None), "model": resp.model}
    if resp.stop_reason == "refusal":
        det = resp.stop_details
        return {"status": "refused", "strategy": label, "category": getattr(det, "category", None), "usage": usage}
    if resp.stop_reason == "max_tokens":
        return {"status": "error", "strategy": label, "error": "output cut at max_tokens", "usage": usage}
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "error", "strategy": label, "error": "model did not return JSON", "usage": usage}
    clean = sanitize(raw, ignore=(load_strategy(strategy)["book"],) if strategy != ABHI else ())
    return {"status": "ok", "strategy": label, "prompt_version": version, "read": clean.data,
            "two_chart_conditions": two, "second_chart_missing": bool(two) and len(charts) < 2,
            "removed": clean.removed, "time_flags": clean.time_flags, "usage": usage}
