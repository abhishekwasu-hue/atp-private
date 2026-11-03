# GIBSON_ELEMENTS_1913: The Elements of Speculation (Thomas Gibson, 1913)
Book file: books/public-domain/34_Gibson_The-Elements-of-Speculation_1913.pdf  |  Note: books/notes/34_Gibson_The-Elements-of-Speculation.md
Status: independent book strategy; not part of Abhi's method; reference/testing only.

**Label: the chart-player method as described (and criticised) by Gibson.** This is not Gibson's own method. Gibson forecasts from fundamentals (crops, money, foreign trade, clearings) and buys securities he judges cheap on a scale down (p.14-18, p.116). He reports the chart method in Ch IX in order to reject it.

Page refs are PDF pages (PDF page = printed page + 8).

## 1. The book's idea in one paragraph
Gibson's Chapter IX describes how the "chart players" of his day traded. The method he describes most fully is the double top. A stock or the general market advances fast to a high (his figures: 100), declines a few points (to 95), and comes back to the same high. That is the point to watch. If the market stops at the double top again and turns down, a considerable break is expected. If it goes through the double top into new ground (102 or 103), the trend is taken to continue upward and buying is warranted at the higher level (p.112). The players often enter with a buy-stop order placed above the market (p.114-115). Gibson grants the read an "elementary basis": buyers discouraged at the first top sell when price returns, and if their selling is absorbed and the advance continues, demand is shown (p.112-113). He then calls it "entirely insufficient". It buys after a rise, it defeats itself when crowds use it, and manipulators push prices through the double top to catch the followers (p.113). He also describes the volume-counting method, which reads hesitation after an advance on heavy cumulative volume as distribution (p.111-112). Gibson rejects that as well.

## 2. What the book reads on the market (trend, levels, volume, bar/tape) - with p.NN
- **Trend (chart players):** a continuing advance through a prior high means the trend is still upward; a stop at the prior high and a turn down means a break (p.112). Gibson's own trend comes from fundamentals, and he says intermediate fluctuations of a few points have no bearing on the trend (p.15-16, p.116-117).
- **Levels:** the first top and the double top at the same price (p.112). The level just above the double top where the buy-stop sits (p.115).
- **Volume:** the share count during an advance. A large total, then hesitation or decline, is read as distribution (p.111-112).
- **Bar / tape:** Book is silent on single-bar signals. Gibson calls "tape appearances" gambling (p.157).

## 3. Setup conditions (numbered S1..Sn; each one observable on a price/volume chart; each with p.NN)
- **S1** Price advances rapidly to a high (the first top) (p.112).
- **S2** Price then declines a few points from that high (the book's figures: 100 to 95) (p.112).
- **S3** Price resumes the advance and comes back to about the same high, making a "double top" (p.112).
- **S4** Volume-counting read (a separate method, used as a warning): the advance was made on large cumulative volume, and price then hesitates or begins to decline (p.111-112).

## 4. Trigger (the book's own signal to act, as the book states it, even if it differs from Abhi's method) - with p.NN
- **Chart players' buy signal:** price goes through the double top into new ground (the book's figures: to 102 or 103 after tops at 100), and purchases are made at that higher level. This is often done with a "stop loss" order to buy placed above the market at the breakout price (p.112, p.114-115).
- **Chart players' bearish read:** price stops again at the double top and begins declining, and "a considerable break may be expected" (p.112).
- Gibson's own verdict on the trigger: buying after the price has risen is "intensely illogical" (p.115-116).

## 5. Invalidation (what the book says proves the read wrong) - with p.NN
- The move through the double top is pushed by manipulators to draw in chart buyers and does not hold (p.113).
- Crowd buying on the breakout creates a weak technical position that invites bear raids (p.113).
- Under the volume-counting read, the hesitation proves to be only a plateau or minor profit-taking, and the advance resumes (p.112).
- A sharp drop catches the stop orders below the market, then the market recovers to new highs (the American Tobacco example) (p.117).
- The buy-stop fills above its price, or does not fill, when the market jumps past it; an overnight drop fills a sell stop far below its price (p.118-119).

## 6. Book's own exits / stops / size (book text only; in ATP these are the user's dashboard settings, never defaults)
- **The chart players' stops, as described:** a sell stop two points below a profitable position, raised as price rises ("raise the stop": buy 100, market 105, stop 103; market 110, stop 108) (p.114). A stop placed with the entry two points away (buy 100, stop 98; short 100, stop 102) (p.114). A buy-stop above the market as the entry itself (p.114-115).
- **Gibson's own view:** the stop-loss order is "an abomination in most cases" and worst with charts (p.113). The only partly acceptable use is protecting profits in a speculative run above values (p.115). Stops are "make loss" orders (p.120).
- **Gibson's alternative:** the scale order, buying more at set intervals on moderate declines (e.g. 100, 98, 96, 94, 92, 90, for an average of 95) in a security judged cheap (p.116, p.124).
- **Size:** "Don't over-speculate": take only what can be carried through a decline caused by accident or manipulation (p.156).
- **Exit:** take a loss at once if the original reasons prove wrong or conditions change; do not sell only because of a profit, or because of a decline with no change in conditions (p.129, p.156-157).

## 7. Not coded: time-based rules (C.4) and anything not visible on a chart (news, tips, fundamentals)
- Seasonal and calendar rules: crop months July to September, August as a "bull month" (Gibson calls blind use of this chart playing), seasonal money rates and clearings (p.43, p.63, p.106).
- History-repeat charts that project past years onto the future (the 1896-1902 pattern ending in the 1903 panic) (p.111).
- "Fluctuations of a few points are matters of weekly occurrence" (p.116). Time framing, not coded.
- Fundamentals: crops, money conditions, currency reserves, foreign trade, bank clearings, railroad prospects, commodity price levels (Ch III-VIII, XI-XII).
- Value judgement that a security is "cheap", which is the basis of Gibson's scale buying (p.115-116).
- News events: the American Tobacco decision, R. P. Flower's death, dividend cuts, political agitation (p.117, p.119, p.122-127).
- Manipulators' and bears' intentions behind a move (p.113, p.117). Not visible on a chart.
- Order-fill mechanics (limits skipped, partial fills) (p.118-119).

## 8. Machine spec (one fenced json block, exactly these keys)
```json
{
  "id": "GIBSON_ELEMENTS_1913",
  "book": "The Elements of Speculation",
  "author": "Thomas Gibson",
  "edition": "1913, The Gibson Publishing Company",
  "summary": "The chart-player method as described (and criticised) by Gibson: after a fast rise, a pullback and a return to the same high (double top), a move through the double top into new ground is read as a long-side signal and a second stop at the top as a coming break; Gibson rejects the method.",
  "conditions": [
    {
      "id": "S1",
      "text": "Price advances rapidly to a high (the first top)",
      "needs": "price",
      "source": "p.112"
    },
    {
      "id": "S2",
      "text": "Price then declines a few points from that high (book example 100 to 95)",
      "needs": "price",
      "source": "p.112"
    },
    {
      "id": "S3",
      "text": "Price resumes the advance and returns to about the same high, making a double top",
      "needs": "price",
      "source": "p.112"
    },
    {
      "id": "S4",
      "text": "Warning read (volume counting): the advance was made on large cumulative volume and price then hesitates or begins to decline",
      "needs": "price+volume",
      "source": "p.111-p.112"
    }
  ],
  "trigger": {
    "text": "Chart players take the long side when price goes through the double top into new ground (book example: tops at 100, take the long side at 102-103), often by a stop order above the market; if price stops again at the double top and turns down, a considerable break is expected. Gibson calls entering long after a rise illogical.",
    "source": "p.112, p.114-p.116"
  },
  "invalidation": [
    {
      "text": "The move through the double top is pushed by manipulators and does not last",
      "source": "p.113"
    },
    {
      "text": "Under the volume read, the hesitation is only a plateau or minor profit-taking and the advance resumes",
      "source": "p.112"
    },
    {
      "text": "A sharp drop runs the stops below the market and the market then recovers to new highs",
      "source": "p.117"
    },
    {
      "text": "A gap past the order level: the stop order above the market fills above its price or not at all, or a gap down fills a stop order far below it",
      "source": "p.118-p.119"
    }
  ],
  "not_coded": [
    "Seasonal and calendar rules: crop months, August as a bull month, seasonal money rates and clearings (p.43, p.63, p.106)",
    "History-repeat charts projecting past years forward (p.111)",
    "Few-point fluctuations as weekly occurrences (p.116)",
    "Fundamentals: crops, money, currency reserves, foreign trade, clearings, railroad prospects, commodity prices (Ch III-VIII, XI-XII)",
    "Value judgement that a security is cheap, the basis of scale buying (p.115-p.116)",
    "News events: court decisions, deaths, dividend cuts, political agitation (p.117, p.119, p.122-p.127)",
    "Intentions of manipulators and bears (p.113, p.117)",
    "Order-fill mechanics: skipped limits and partial fills (p.118-p.119)"
  ],
  "sides": [
    "long"
  ]
}
```

## 9. Open points / limits of the book
- This is the chart players' method in Gibson's report, not a method Gibson recommends. He says it has an "elementary basis" but is "entirely insufficient" (p.112). A test of this spec tests the method he criticises.
- Gibson's objections, as he states them: waiting for higher prices before buying is illogical (p.113, p.116); mass use defeats the method and invites bear raids and manipulation through the double top (p.113); mechanical devices would work only if the market were a machine (p.117); fixed-price fills are assumed in the chart players' tables but are not guaranteed (p.118-119).
- "Double bottoms" are named but not explained (p.112). Gibson says his illustrations also apply to short sales (p.116), so the mirror case is implied, not described. It is not coded.
- The book gives only one numeric example (100, 95, 100, 102-103). Book is silent on pullback depth, breakout margin or volume levels beyond that.
- S4 comes from a different chart method (volume counting) on the same page. It is kept as a warning read and is not part of the double-top trigger.
- OCR letter and fraction errors are common (e.g. "102J^" = 102 1/2, p.118). The page refs are checked.
- Review 2026-11-03: machine spec reworded to the owner's neutral vocabulary (no buy/sell/hold words; the book's own words stay in sections 3-5), `sides` added, `needs` and time words corrected where listed in the strategies README.
