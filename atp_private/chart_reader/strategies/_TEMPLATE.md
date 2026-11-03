# Book strategy template (one file per book, English)

**Owner rule (Abhi, 2 Nov 2026):** strategies built from the book knowledge are kept **independent**, each **named after its book**. They are never merged into Abhi's own method (trend -> buyer/seller area -> correction with weakening momentum -> commitment candle), never used as filters or gates on it, and never presented as his method. Each one is a separate, labelled strategy for reference and testing until Abhi decides to adopt it.

Rules that still apply to every book strategy:
- **C.4:** no chart-reading logic framed by day, date, weekday, session, clock time, time cycles, anniversaries or day counts. The book's time rules are listed in section 7 as "not coded".
- **C.3:** stops, targets, R:R, lots and position size are the trader's own dashboard settings. The book's own exit/stop/size rules are recorded in section 6 as book text only, and never become defaults.
- **A.3:** write only what the book says, with PDF page refs (`p.NN`) taken from the note in `books/notes/`. Where the book is silent, write "Book is silent".
- The AI only reads and explains. No buy/sell calls (ATP: "area of interest").

File name: `books/strategies/<ID>.md`, where ID is e.g. `WYCKOFF_TAPE_1910`.

```
# <ID>: <Book title> (<Author>, <edition year>)
Book file: books/public-domain/<file>  |  Note: books/notes/<file>
Status: independent book strategy; not part of Abhi's method; reference/testing only.

## 1. The book's idea in one paragraph
## 2. What the book reads on the market (trend, levels, volume, bar/tape) - with p.NN
## 3. Setup conditions (numbered S1..Sn; each one observable on a price/volume chart; each with p.NN)
## 4. Trigger (the book's own signal to act, as the book states it, even if it differs from Abhi's method) - with p.NN
## 5. Invalidation (what the book says proves the read wrong) - with p.NN
## 6. Book's own exits / stops / size (book text only; in ATP these are the user's dashboard settings, never defaults)
## 7. Not coded: time-based rules (C.4) and anything not visible on a chart (news, tips, fundamentals)
## 8. Machine spec (one fenced json block, exactly these keys)
## 9. Open points / limits of the book
```

Section 8 format (valid JSON; `chart_read.py --strategy <ID>` loads it). **Vocabulary rule (owner, 3 Nov 2026):** the section 8 texts go into the AI prompt, so they use the neutral vocabulary only: "take the long side / short side", "exit", "stays / is defended", "supply / demand"; never buy, sell, hold (any form), target or stop-loss. The book's own words stay in sections 3-6. `sides` = the sides the book itself states; `"stated": false` marks a book that gives no trigger of its own. Conditions that need another chart (another average, the group, the general market) carry `"needs": "two charts"`. No day / week / month / session words inside conditions, trigger or invalidation (C.4). Position, P&L or tape rules are not chart conditions: they belong in section 6, not in `invalidation`.

```json
{
  "id": "WYCKOFF_TAPE_1910",
  "book": "Studies in Tape Reading",
  "author": "Richard D. Wyckoff",
  "edition": "1910, Ticker Publishing Co.",
  "summary": "one sentence",
  "sides": ["long", "short"],
  "conditions": [
    {"id": "S1", "text": "observable condition", "needs": "price|volume|price+volume", "source": "p.NN"}
  ],
  "trigger": {"text": "the book's signal", "source": "p.NN", "stated": true},
  "invalidation": [{"text": "...", "source": "p.NN"}],
  "not_coded": ["time rules and other excluded items, one line each"]
}
```
