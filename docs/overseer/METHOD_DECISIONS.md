# Method decisions (overseer, research-based) — for the Trade engine port (M65/M66)

Source: the overseer's handover (private trade-data repo, overseer/OVERSEER_HANDOVER.md §3-§4) and RESEARCH_LOG.md (R1-R32).
Every rule here was decided from web research (see the R-numbers) and confirmed by the owner's answer keys; the engine
snapshot must reproduce them. Parity reference: answer_key_batch1_v4.json (8/8 matched by Trade).

Additional decisions after this summary was written:
- SW: swing = confirmed pivot + k x ATR, k = 3 (working value, settings); BOS = a candle CLOSE beyond the last external
  swing in the new direction (a wick = sweep, never a BOS); TRANSITION (between CHoCH and BOS) = range rules.
- Sweep has ONE meaning everywhere: a wick through a level/swing without a candle close beyond it.
- Invalidation of an E4(b) on a broken area = the farther of the retest extreme and the band's far edge (never inside the band).
- Closing-auction bars never form a 1H candle or a swing/zone; one shared helper for every price builder.
- Risk management, sizing, SL/target/lots/exits are the user's own settings in ATP (owner rule); the engine never sets them.

## 3. Trade — method decisions in force (research-based)
- **BREAK-2:** broken = close beyond the object AND a reading-TF (15M) candle CLOSES beyond the **next EXTERNAL swing** of the object's own TF (Daily→Daily, 1H→1H(D1), Weekly→Weekly, line→its TF). Wick through that swing = sweep. States: ALIVE / FALSE BREAK (back inside before break known; known at first close inside) / BEYOND_NOT_BROKEN (no flip entry) / BROKEN (flip) / DEAD (broken back by same test; no second flip). Swings made while testing the object (incl. false-break extremes) are INTERNAL, labelled "FALSE BREAK extreme". (R1–R3, R6)
- **R6:** trade only with the Daily trend; E4(b) only after a with-trend break, first return; counter-trend break ⇒ E4(a) fade of the false break; range ⇒ edge fades only.
- **Data:** NSE closing auction since 3 Aug 2026 ⇒ 15:15–15:30 flat + one print: flagged DP-2; auction-extended Daily extremes flagged DP-1; flagged bars never make swings/zones (R9).
- Refined base = origin base on 15M (R5-2 flipped area: location = original base, invalidation = far edge opposite the trade).
- Owner fixture 13 Oct state line = BEYOND_NOT_BROKEN (DECISIONS 85, approved). F2 29 Sep golden updated (not an owner fixture).
- Answer key batch 1 **v4** (overseer/answer_key_batch1_v4.json) = 8/8 matched by the session.

## 4. Trade — state and queue
- MERGED + deployed (25 Oct, main fb22b35): #385 BREAK-2, #386 S1-precise, #387 V1 fix. Answer key v4 8/8. V1 vision run: $0.35, vision says Daily sideways where reader says DOWN. **M41 given:** SW starts now; V1 cap $2 + state words in vision questions; lookback = all history (L03); confirm 13 Oct next swing 22,809.35.
- **Order of work (M16):** BREAK-2 → V1 vision VPS run ($1 cap) → **SW** (swings ATR filter + external/internal labels + trend from external structure) → **Z** (zone construction, M7: base before impulsive departure, RBR/DBD too, departure test, quality labels, width sanity) → **EN** (entry only with the required set, else WATCH alert; invalidation = distal edge / false-break extreme; one entry per cluster per visit; line break ≠ entry) → C (RSI) → D+E. One PR per layer.
- **25 Oct 20:50 Trade report:** main 478569f (#385–#388 merged, no PR open); V1 run2 8/8 $0.35; SW-c half done locally, 69 synthetic tests fail → M50 (classify A/B/C, parity fixtures first, k by evidence, send k charts). Owner-deploy: nothing now.
- **SW in progress (M42):** state between CHoCH and BOS = TRANSITION (range rules); external swing size by evidence (k that reproduces NIFTY Daily DOWN 12–13 Oct fixture + answer-key swings), 3 ATR provisional; then wire-in PR.
- Full reader review: `READER_REVIEW_2026-10-24.md` (❌ swings, ❌ trend, ❌ entries without required set).
- Owner options NOT ordered (wait for Abhi): pullback-volume confirming piece; hidden RSI divergence.

