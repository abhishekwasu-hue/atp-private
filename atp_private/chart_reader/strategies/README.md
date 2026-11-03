# Independent book strategies (M85)

**Owner rule (Abhi, 2 Nov 2026):** every strategy built from the books is kept **independent** and **named after its book**. None of them is part of Abhi's method, none filters or gates it, and their results are never merged with his read. They are for reference and testing until Abhi decides to adopt one.

| Strategy id | Book | Author | Edition | Conditions |
|---|---|---|---|---|
| `BROWNE_TIDALSWINGS_1918` | Tidal Swings of the Stock Market | Scribner Browne | 1918, The Magazine of Wall Street | 8 |
| `CARRET_SPECULATION_1927` | The Art of Speculation | Philip L. Carret | 1927, Barron's | 5 |
| `COWEN_COMMONSENSE_1922` | Common Sense in Stock Speculation | Maurice Cowen | 1922, Weiss Publishing Co., New York | 5 |
| `CWMORGAN_SPECULATE_1900` | How to Speculate Successfully in Wall Street (brokerage promotional pamphlet, chart theory section) | C. W. Morgan & Co., Bankers and Brokers | c1900 (copyright 1900), C. W. Morgan & Co., New York | 7 |
| `DICE_STOCKMARKET_1926` | The Stock Market | Charles Amos Dice | 1926, A. W. Shaw Company (scan: 4th printing, July 1928) | 8 |
| `DOW_HAMILTON_1922` | The Stock Market Barometer | William Peter Hamilton | 1922, Harper & Brothers, first edition | 7 |
| `DOW_NELSON_1902` | The ABC of Stock Speculation (includes Charles H. Dow's editorials, Ch V-XIX) | S. A. Nelson (compiler); Charles H. Dow (Ch V-XIX) | 1902, S. A. Nelson, Nelson's Wall Street Library Vol. V | 10 |
| `GANN_SELECTOR_1930` | Wall Street Stock Selector | W. D. Gann | 1930, Financial Guardian Publishing Co. | 9 |
| `GANN_TRUTH_1923` | Truth of the Stock Tape | W. D. Gann | 1923, Financial Guardian Publishing Co. | 9 |
| `GIBSON_ELEMENTS_1913` | The Elements of Speculation | Thomas Gibson | 1913, The Gibson Publishing Company | 4 |
| `LEFEVRE_REMINISCENCES_1922` | The Reminiscences of a Stock Operator (Saturday Evening Post serial) | Edwin Lefevre | 1922-1923, The Saturday Evening Post (Curtis Publishing Co.), first publication | 5 |
| `SCHABACKER_THEORY_1930` | Stock Market Theory and Practice | R. W. Schabacker | 1930, B. C. Forbes Publishing Co. | 12 |
| `SELDEN_PSYCHOLOGY_1912` | Psychology of the Stock Market | G. C. Selden | 1912, Ticker Publishing Company | 6 |
| `VANRIPER_INSOUTS_7ED` | The Ins and Outs of Wall Street | Lewis C. Van Riper | 7th edition, revised (c.1899), New York; publisher not stated | 10 |
| `VANSTRUM_FORECASTING_1927` | Forecasting Stock Market Trends | Kenneth S. Van Strum | 1927, Barron's | 6 |
| `WYCKOFF_HOWITRADE_1925` | How I Trade and Invest in Stocks and Bonds | Richard D. Wyckoff | 1925, 5th edition (first published 1922), The Magazine of Wall Street | 6 |
| `WYCKOFF_TAPE_1910` | Studies in Tape Reading | Richard D. Wyckoff | 1910, Ticker Publishing Co. | 10 |

No strategy for Mackay (1841), Bean (1927) or Butler (1922): their methods cannot be checked on a chart. Each note's section 8 explains why.

- Spec format: `_TEMPLATE.md`. Section 8 JSON is what the code loads.
- Run: `python3 books/ai/chart_read.py --instrument NIFTY --chart 1H=chart.png --strategy <ID>`. Results are labelled with the book name.
- Every spec lists the book's time-based rules as "not coded" (owner rule C.4) and its stops, R:R and sizing as book text only (C.3).
- Known limits across the books: volume words ("large", "light", "narrow") have no numeric thresholds. Point figures are 1900-1930 stock points with no scaling rule. Conditions marked `"needs": "two charts"` cannot be checked from one chart. Wyckoff 1925, Selden 1912 and the Lefevre serial have no complete chart strategy; their specs say so.

## Review 2026-11-03 (all 17 specs, in depth; prompt book_strategy_read_v5)

| # | Finding | Fix |
|---|---|---|
| 1 | 102 buy/sell/hold words sat in the section-8 texts of 15 specs. Those texts go straight into the prompt, which tells the model never to use those words, and `sanitize()` deletes evidence that echoes them. | Section-8 texts reworded to the neutral vocabulary (72 edits, every sentence read). The books' own words stay in sections 3-6. Regression test: no forbidden word in any spec's prompt text. |
| 2 | Five conditions that need a second chart were marked `price`, so P6 never attached one: Gann Selector S9, Gann Truth S9, Wyckoff 1925 S4, Lefevre S1 and S2. | `needs: two charts`. Regression test added. |
| 3 | Time words inside conditions (C.4): Browne S5 "a day or two", Hamilton S7 "same day", Gann Selector trigger "months or years", Van Riper trigger "selling day", Gibson "overnight". | Reworded in bars / chart stretch. |
| 4 | Six invalidations were position, P&L or tape rules, not chart conditions (Browne, Cowen, Hamilton, Dice "tape does not second", Lefevre, Wyckoff 1925). | Moved to section 6 as book text (C.3); removed from the machine spec. |
| 5 | Which sides a book states was implicit, so the model guessed on down charts (P1). | `sides` field in every spec (long only: Browne, Cowen, Gibson, Selden). Prompt uses it. |
| 6 | Several books list 2-5 trigger variants, but the output has one `trigger_seen`. | Prompt: judge each variant; status yes if any is on the latest bars; name the letter in the evidence. |
| 7 | Selden and Wyckoff 1925 state no trigger of their own. | `"stated": false`; prompt answers trigger "unclear" and says so. |
| 8 | Two mirror cases had been written as "sell" where the book means the short side (Dice, Van Riper, Lefevre, Gann Truth). | Fixed by hand: "take the short side". |

Not changed (book limits, left "unclear" by design): absolute point sizes (P5) and volume words without thresholds. Next step: re-run the real API on the 2019 pair with the v5 prompt (18 reads, about $1.30) and compare with `api_results_v3`.
