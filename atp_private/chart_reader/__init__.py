"""atp_private.chart_reader: the book-knowledge chart reader that ATP's AI chart reading loads (owner order M86, W1).

The reader logic is `chart_read.py`, a faithful port of trade-data `books/ai/chart_read.py` (commit 6dd8bf4); the
prompts and the 17 book strategy specs are byte-for-byte copies in `prompts/` and `strategies/` (another folder holding
both can be named with the env ATP_CHART_READER_DIR). This module adds only ATP's contract:

    get_reader() -> Reader
    Reader.strategies()                     labels only: ABHI first, then the books
    Reader.two_chart_conditions(strategy)   condition ids that need a second chart
    Reader.read(instrument=, charts=, facts=, strategy=, model=, effort=, client=)

`read` uses the caller's sync anthropic client; this package never builds a client and never reads an API key.
The AI only describes the chart. It never places, blocks or changes an order (ADR-0006); this module has no order,
broker or execution import.
"""
from __future__ import annotations

from . import chart_read as _cr

NAME = "chart_reader"
VERSION = f"{_cr.PROMPT_VERSION[_cr.ABHI]}+{_cr.PROMPT_VERSION['BOOK']}"
EFFORTS = ("low", "medium", "high", "xhigh", "max")


class Reader:
    """ATP's chart reader: Abhi's method (ABHI) or one independent book strategy, never mixed."""

    name = NAME
    version = VERSION
    ABHI = _cr.ABHI

    def strategies(self) -> list[dict]:
        """Labels only (no spec text): ABHI first, then each book in file order."""
        out: list[dict] = [{"id": _cr.ABHI, "name": "Abhi's method"}]
        for item in _cr.list_strategies():
            if "error" in item:
                continue
            spec = _cr.load_strategy(item["id"])
            out.append({"id": spec["id"], "name": _cr._label(spec["id"])["name"], "book": spec["book"],
                        "author": spec["author"], "edition": spec["edition"],
                        "two_chart": bool(_cr.needs_two_charts(spec)), "sides": list(spec.get("sides", []))})
        return out

    def two_chart_conditions(self, strategy: str) -> list[str]:
        if strategy == _cr.ABHI:
            return []
        return _cr.needs_two_charts(_cr.load_strategy(strategy))

    def read(self, *, instrument: str, charts: list[tuple[str, bytes, str]], facts: str, strategy: str, model: str,
             effort: str, client) -> dict:
        if effort not in EFFORTS:
            raise ValueError(f"effort must be one of {', '.join(EFFORTS)}")
        if not model:
            raise ValueError("model is required")
        return _cr.read_charts(instrument, charts, facts or "", strategy, effort, client=client, model=model)


def get_reader() -> Reader:
    return Reader()
