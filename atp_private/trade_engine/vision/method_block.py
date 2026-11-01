"""vision/method_block.py — M56 V2 (C2): ONE method block with the object-state words exactly as BREAK-2 (DECISIONS 76 / 77 / 82 / 86 /
110), shared verbatim by the engine trader prompt (vision/engine_audit.METHOD_BLOCK ⇒ TRADER_SYSTEM and the engine_check SYSTEM_PROMPT)
and the level-bot signal_check prompt (vision/signal_audit.SYSTEM_PROMPT). One meaning everywhere: an area, a line and a level use the
same words. Text only — no number, no day / clock framing (tests/test_vision_method_block.py pins the wording).
"""

OBJECT_STATES = """OBJECT STATES (one meaning everywhere: an area, a line and a level use the same words)
- ALIVE = fresh or tested. An object dies only by structure, never by being touched or entered.
- A sweep = a wick through the object without a close beyond it: the object stays ALIVE and the visit continues.
- FALSE BREAK = a 15M (reading-TF) candle close beyond the object, then a 15M (reading-TF) candle close back inside before it is
  BROKEN: the object stays ALIVE and the visit continues.
- BEYOND_NOT_BROKEN = a 15M (reading-TF) candle close beyond the object with no follow-through yet: not broken, not flipped, and no
  entry of any model off it.
- BROKEN = a 15M (reading-TF) candle close beyond the object AND a 15M (reading-TF) candle close beyond the most recent EXTERNAL
  swing of the object's TF lying beyond it (a swing made while price was testing the object is internal and never counts; a wick
  through that swing without a close beyond is a sweep of it; with no such swing, a new swing of the object's TF forms beyond and a
  15M (reading-TF) candle closes beyond it): the role flips. Only BROKEN breaks an object.
- DEAD = a BROKEN (flipped) object broken back by the same test: never a trade location, no second flip.
"""
