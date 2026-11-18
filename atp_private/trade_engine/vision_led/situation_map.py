"""vision_led/situation_map.py — KB भाग I (बाजारातल्या परिस्थितींचा नकाशा, Abhi G-MAP1 2026-10-09) चा English सारांश, vision playbooks
साठी (M56 V3: structure only — no clock / day framing and no numbers in the text) (मजकूर फक्त, images नाहीत; ~1k tokens, system prompt मध्ये cached). पूर्ण नकाशा: docs/knowledge/KNOWLEDGE_BASE.md भाग I."""

MAP_TEXT = """SITUATION MAP (KB Part I, approved). Name the situation BEFORE judging the setup.
Principles: P1 degree first: trade only in the PARENT direction (the motive sequence the traded correction belongs to); the grandparent
degree (Daily/Weekly) is evidence only. Exceptions: S4 flip retest, G7 exhaustion gap, G10 range edge. P2 always keep a primary AND an
alternate count, each with invalidation and confirmation; an alternate is not gray. P3 a strong counter-move's meaning comes from the
REACTION after it. P4 measure relative to the impulse being corrected; depth is evidence, displacement weak evidence, overlap/legs
notes only; the impulse ORIGIN (start) BROKEN (OBJECT STATES) => not a pullback. P5 each situation has its own area, and the area must exist
at the decision bar. P6 closed commitment candle only. P9 money/sentiment (FII, VIX, macro) is context, not a rule.
Situations: S1 normal three-wave overlapping pullback -> trade C-end at area. S2 deep pullback: valid with an area and a sweep there; the deeper toward the impulse origin, the weaker.
S3 strong counter-move that leaves the last confirmed 1H LH/HL BROKEN inside the impulse (origin intact) -> GRAY-1, wait for the reaction:
corrective reaction that does not reclaim the broken area then commitment in the counter-move direction = new trend (trade the reaction
end); impulsive reaction that leaves the counter-move start BROKEN = old trend. S4 the impulse origin BROKEN (testing) -> only the
flip retest in the break direction; MAGNET (closes chopping around the level) = no setup. S5 shallow flag in a strong trend
(G8) -> flag edge / broken swing / displacement base; a single candle is not a flag. S6 sideways triangle/flat -> only E-end/C-end, never
inside B/D/X. S7 expanded flat / spring: sweep beyond A then reclaim -> enter after the reclaim close. S8 trend tiring (smaller
with-trend legs, bigger pullbacks, divergence) -> lower confidence, no fade. S9 range (trade degree RANGE) -> G10 at the edges only
(lower edge bull put, upper edge bear call; with a parent trend only the trend-side edge); never mid-range. S10 gap: decide by
acceptance/rejection on the closed bars after the gap candle. S11 inside a B wave -> no trade. S12 a spike with no pullback yet =
no setup (no automatic entry).
GRAY: Gray-1 = parent direction not settled by structure (S3 reaction open, S4 testing unresolved). Gray-2 = correction end not
decidable at the commitment bar (zigzag/flat needs A, B and a C reaching A's extreme; triangle all five legs; flag = G8 structure; a five-wave
counter-move is only A). Never trade gray (Gray-1 also needs Abhi's direction). Mid-range is not
gray - there is simply no area. If the situation is unclear, say which two counts compete and what would decide between them.
"""
