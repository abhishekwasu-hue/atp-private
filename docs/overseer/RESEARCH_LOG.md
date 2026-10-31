# RESEARCH LOG — Abhi's projects (Trade reader + ATP)

Purpose: every web research done for a decision, with sources, the conclusion, and where it was applied. Future sessions read the relevant section instead of researching again. Append new entries at the end (R-number, date, topic). Never put server addresses, credentials or strategy secrets here.

Format: **Question** · **Findings (with sources)** · **Decision** · **Applied in** (order / prompt ID from the overseer handover).

---

## R1 · 24 Oct 2026 · Break vs retest (zones / levels)
**Question:** when is a zone/level broken, when is it a retest?
**Findings:**
- A wick beyond = test / sweep (SFP, spring/upthrust), not a break — [LuxAlgo SFP](https://www.luxalgo.com/library/concept/swing-failure-pattern.md), [LuxAlgo upthrust](https://www.luxalgo.com/library/concept/upthrust.md).
- Real break = close beyond + acceptance + follow-through; quick reclaim = false break — [Strike BOS](https://www.strike.money/technical-analysis/break-of-structure), [LuxAlgo BOS](https://www.luxalgo.com/library/concept/break-of-structure.md).
- First return after a real break = retest (role reversal); accepted back inside ⇒ break was false — [LuxAlgo role reversal](https://www.luxalgo.com/library/concept/role-reversal.md), [IG false breakout](https://www.ig.com/au/trading-strategies/what-is-a-false-breakout-and-how-can-you-avoid-it--230130).
- Supply/demand school: close through the distal edge and stays = broken — [The Right Trader](https://therighttrader.com/learn/price-action/supply-and-demand-zones).
- Use a meaningful swing; minor swings give false alarms; keep one convention — [LuxAlgo CHoCH](https://www.luxalgo.com/library/concept/change-of-character.md).
- No source says "must reach the next swing" literally; follow-through is qualitative.
**Decision:** BREAK-2 = close beyond the object AND a reading-TF candle closes beyond the next swing on the far side (objective follow-through). Matches owner anchors (X01, NIFTY 22,731.8).
**Applied in:** M6 v4 (Trade), answer key batch 1 v3+.

## R2 · 24 Oct · Wick vs close at the next swing
**Findings:** wait for a body close to confirm a structure break; a wick beyond that closes back = sweep — [XS.com SMC](https://www.xs.com/en/courses/smart-money-concept-strategy/what-is-market-structure), [LuxAlgo SFP](https://www.luxalgo.com/library/concept/swing-failure-pattern.md), [daytradingtoolkit failed breakout](https://daytradingtoolkit.com/strategies/failed-breakout-bull-bear-trap-strategy).
**Decision:** break known at the first reading-TF CLOSE beyond the next swing; false break known at the first close back inside.
**Applied in:** answer key v3 (L05 = sweep), M11 Q2.

## R3 · 24 Oct · False breakouts of zones and swings
**Findings:**
- ~50% of first breakouts after a range fail; channel breakouts ~75%; failures usually within 1–5 bars; failure = no follow-through — [Brooks forum](https://www.brookstradingcourse.com/support-forum/12-market-cycle/breakout-fail/).
- False break of a level = the classic fade (spring/upthrust, Sperandeo 2B, Raschke turtle soup, SFP): entry back inside, stop beyond the false-break extreme — [LuxAlgo false breakout](https://www.luxalgo.com/library/concept/false-breakout.md), [FBS Trader Vic](https://fbs.eu/en/analytics/tips/trader-vics-false-breakout-method-24711), [LuxAlgo turtle soup](https://www.luxalgo.com/library/concept/turtle-soup.md).
**Decision:** false break of an alive object = E4(a) sweep-candle entry, invalidation at the sweep extreme; E4(b) only after a confirmed break.
**Applied in:** M6 v4 R3.

## R4 · 24 Oct · Reclaimed broken zone; counter-trend breaks
**Findings:** a level reclaimed after a decisive close does not regain its role; a level crossed both ways repeatedly loses information — [LuxAlgo support level](https://www.luxalgo.com/library/concept/support-level.md). Major-trend-reversal attempts ≈40% (forum) ⇒ trend resumption more likely — [Brooks forum](https://brookstradingcourse.com/support-forum/22-major-trend-reversals/probability-of-breakout-vs-mtr). First counter-trend break (CHoCH) = warning; wait for BOS; LTF signals against HTF need caution — [heygotrade CHoCH](https://www.heygotrade.com/en/blog/change-of-character-choch-trading).
**Decision:** before confirmed break, back inside = false break (alive); after break, back inside = retest; break back ⇒ DEAD; E4(b) only for with-trend breaks; range ⇒ edge fades only.
**Applied in:** R6 (Trade).

## R5 · 24 Oct · How a zone is built
**Findings:** zone = compact base (1–few overlapping candles) before an impulsive departure; distal = base wick extreme, proximal = bodies; RBD/DBR/RBR/DBD all valid; quality = departure strength, short time at base, freshness, room to next opposing zone, HTF context; wide zone = large stop → refine on lower TF — [LuxAlgo S&D zones](https://www.luxalgo.com/library/concept/supply-and-demand-zones.md), [LuxAlgo zone scoring](https://www.luxalgo.com/library/concept/zone-scoring-and-refinement.md), [LuxAlgo order block](https://www.luxalgo.com/library/concept/order-block-anatomy-and-refinement.md), [FXStreet departure](https://www.fxstreet.com/education/lesson-from-the-pros-stocks-201504280000).
**Decision:** reader gaps G1–G5 (swing candle ≠ base, no departure test, no continuation bases, no width sanity, freshness unused).
**Applied in:** M7 (Z1–Z8).

## R6 · 24 Oct · Internal vs external structure; HTF direction
**Findings:** external swings define trend/range; internal swings sit inside one leg; an internal break against the bias is a pullback until external points break; stops beyond external swings — [LuxAlgo internal vs external](https://www.luxalgo.com/library/concept/internal-vs-external-structure.md). HTF sets direction; LTF pullback shift back with trend = entry — [LuxAlgo HTF filter](https://www.luxalgo.com/library/concept/higher-timeframe-trend-filter.md).
**Decision:** "next swing" = most recent EXTERNAL swing of the object's own TF; swings made while testing the object (false-break extremes) are internal, labelled "FALSE BREAK extreme".
**Applied in:** M15 S1 (Trade), answer key v4.

## R7 · 24 Oct · Vision models reading candlestick charts
**Findings:** VLMs capture short-term visual signals, weak on long-term trend and precise timing; models have directional biases — [besthub summary](https://www.besthub.dev/articles/can-large-vision-language-models-really-understand-candlestick-charts-743b57154783). VLM value accuracy decays later in long outputs — [NeurIPS 2026 grounding decay](https://neurips.cc/virtual/2026/173750).
**Decision:** vision = second opinion only; short structured answers; every price validated against data; annotations drawn by code.
**Applied in:** V1 (Trade), CP-V CV1–CV14 (ATP).

## R8 · 24 Oct · Full reader review vs standards
**Findings:**
- swing magnitude filters (ATR multiple adapts; fractal admits tiny swings; confirmed vs provisional) — [LuxAlgo swing filters](https://www.luxalgo.com/library/concept/swing-magnitude-filters.md);
- trend = HH/HL vs LH/LL, change when protecting swing breaks — [CrossTrade](https://crosstrade.io/learn/price-action/market-structure);
- trendlines: 2 touches draw, 3rd validates, break = pace change — [LuxAlgo trendline](https://www.luxalgo.com/library/concept/trendline.md);
- RSI divergence on confirmed pivots of the same move — [LuxAlgo RSI divergence](https://www.luxalgo.com/library/indicator/RRp1xOWb-rsi-divergence/);
- Wyckoff effort vs result — [LuxAlgo](https://www.luxalgo.com/library/concept/effort-vs-result/);
- zone + LTF CHoCH = most reliable entry confirmation — [Quantum Algo](https://www.quantum-algo.com/academy/entry-confirmation-techniques/).
**Decision:** ❌ swings, ❌ trend, ❌ entries without required set; ⚠️ zones, lines, invalidation, duplicates. File READER_REVIEW_2026-10-24.md.
**Applied in:** M16 (SW + EN).

## R9 · 24 Oct · NSE Closing Auction Session (data fault)
**Findings:** from 3 Aug 2026 continuous trading 09:15–15:15, CAS order entry 15:20–~15:30, closing price set by auction; index close from constituents' auction closes; derivatives till 15:40 — [Motilal Oswal](https://www.motilaloswal.com/learning-centre/2026/8/introduction-of-closing-auction-session-cas-from-03-august-2026), [Sahi](https://www.sahi.com/blogs/closing-auction-session-cas-explained-nse-bse-closing-price-rules-2026).
**Decision:** flag flat 15:15+ bars and auction-extended Daily extremes; never build swings/zones from them; keep official close.
**Applied in:** DP-1/DP-2 (Trade), DATA-H DH3 (ATP).

## R10 · 24 Oct · UI tabs / segmented controls / scroll cues
**Findings:** segmented control 2–5 short equal-width options; 6+ → dropdown or other — [eleken](https://www.eleken.co/blog-posts/segmented-control-ui). Primary tabs vs secondary tabs; scrollable tabs for many — [SAP Fiori tabs](https://www.sap.com/design-system/fiori-design-android/v26-4/components/m3-standard-components/tabs/usage). Partially visible next tab + edge fade = scroll cue — [uxcel](https://uxcel.com/lessons/horizontal-navigation-242), [OutSystems forum](https://www.outsystems.com/forums/discussion/15505/silk-tabs-scrolling-on-mobile-not-obvious-enough).
**Applied in:** M9 (W0-1/W0-2), M10.

## R11 · 24 Oct · Order crash recovery / idempotency
**Findings:** after timeout/crash don't resubmit blindly — query open orders by your client id; found ⇒ adopt, not found ⇒ resubmit with same id — [tastytrade idempotency](https://developer.tastytrade.com/docs/guides/idempotency-and-retries/); resolve unknown-state orders right after ack timeout — [nexustrader](https://nexustrader.readthedocs.io/en/latest/quickstart/reliable_orders.html).
**Decision:** reconcile FIRING orders immediately on start, exits first; no fixed 60 s wait.
**Applied in:** M13 (TM-2).

## R12 · 24 Oct · Spread order sequence and margin
**Findings:** hedge margin benefit applies whichever leg first; buy hedge first to avoid margin shortfall; basket legs go one after another (second not guaranteed); exit short first, hedge last — [tradingqna](https://tradingqna.com/t/margin-benifit-in-f-o/84457). Option chain columns that matter: OI, ΔOI, volume, IV, LTP vs bid/ask, delta — [AlgoTest](https://algotest.in/blog/how-to-read-bankex-option-chain.md).
**Applied in:** M23 (T1-3, T1-4), M27 (#524).

## R13 · 24 Oct · Combined stop-loss / strategy exits / trailing
**Findings:** traders want exits on combined MTM, separate up/down triggers, candle-close check to avoid spikes, shorts closed before longs; Zerodha lacks it (May 2026) — [tradingqna request](https://tradingqna.com/t/feature-request-smart-exit-based-on-combined-position-p-l/182267), [combined premium SL](https://tradingqna.com/t/combined-stoploss-in-option-premium/100920). Strategy-level Overall SL/Target/Trail SL; trail X→Y; lock / lock-and-trail — [AlgoTest terms](https://algotest.in/blog/definition-of-terms-used-in-backtesting-platform.md), [AlgoTest lock & trail](https://algotest.in/blog/broker-level-lock-and-trail-sl.md). SL/target on order screen, OCO, trail only in favour — [Groww](https://groww.in/blog/f-and-o-risk-management-on-groww).
**Applied in:** M24 (CX), M25 (SX).

## R14 · 24 Oct · Trader-protection features
**Findings:** SEBI study FY24-25: 91% of individual F&O traders lost money; losses ₹1.05 lakh cr — [Moneylife](https://moneylife.in/article/91-percentage-of-retail-traders-lost-money-in-derivatives-losses-in-fo-surged-41-percentage-to-rs105-lakh-crore-in-fy25-sebi-study/77613.html). Competitors focus on analytics — [AlgoTest Opstra vs Sensibull](https://algotest.in/blog/opstra-vs-sensibull.md). Common mistakes + prevention (stop, sizing, revenge → loss limit/cooldown, overtrading, moving stops, journal) — [TradeZella](https://www.tradezella.com/blog/trading-mistakes).
**Applied in:** M26-final (TP-1…TP-8).

## R15 · 24 Oct · SEBI rules for tools showing levels
**Findings (not legal advice):** public buy/sell calls need SEBI RA licence; one-to-one advice needs IA; SEBI looks at what a tool does; fact-surfacing chart tools where trader decides are fine — [Sahi](https://www.sahi.com/blogs/is-ai-trading-legal-in-india).
**Decision:** "area of interest" with factors, no buy/sell words, no entry/stop/target numbers; lawyer review before public launch (owner task).
**Applied in:** CV12 (ATP).

## R16 · 24 Oct · Broker historical data depth
**Findings:** Upstox historical API gives ~5 years of 30-min candles; 1-min not 5 years — [Upstox community](https://community.upstox.com/t/historical-intraday-candlechart-data-of-a-security-stock-of-previous-5-years-or-more/6800).
**Applied in:** M17 (DATA-H).

## R17 · 25 Oct · Colour in UI
**Findings:** 60-30-10 rule (neutral base / surfaces / accent); gradients only for hero, key CTA, new badges, tinted data cards — never text, dense UI, tables, forms; check contrast on phones — [eggradients 2026](https://www.eggradients.com/blog/gradient-ui-in-2026). Never colour alone; AA contrast; colour-blind simulation — [hedgehoglab](https://hedgehoglab.com/how-to-improve-colour-accessibility-in-financial-services-apps/).
**Decision:** brand blue + one violet accent + blue→violet gradient (accents only); section tints; tinted summary cards with sign/icon/word; project-wide via tokens.
**Applied in:** M29, M31.

---
## How to add an entry
`## R<n> · <date> · <topic>` → Question · Findings (bullet + source link each) · Decision · Applied in (prompt ID). Keep each entry ≤15 lines; link, don't copy articles.

## R18 · 25 Oct · Phone looks dim (dark theme)
**Question:** owner finds the phone view dim — darken/brighten what?
**Findings:**
- Measured ATP colour_v2 dark tokens (frontend/src/styles/tokens.css): primary text 17.9:1 and muted text 10.4–11.9:1 — text is NOT the problem.
- Card vs page only 1.15:1; borders 1.9–2.2:1 — below the 3:1 non-text contrast that WCAG 2.x (1.4.11) asks for UI boundaries ⇒ cards melt into the page, the screen looks flat and dim.
- Page colour (7,11,22) is darker than Material's #121212 dark-surface advice; depth should come from lighter surfaces for higher layers; desaturated tones read better; limit saturated colour to key elements — [uxcel dark mode](https://uxcel.com/blog/12-principles-of-dark-mode-design-627), [Material dark theme](https://m2.material.io/design/color/dark-theme).
- Outdoor phone use: aim ≥5:1, ideally 7:1 for key actions — [GrowthSuite](https://www.growthsuite.net/questions/is-color-contrast-sufficient-on-ctas-for-mobile-outdoors-use).
**Decision:** lift page and card surfaces a step, borders ≥3:1 vs their surface, card ≥1.3:1 vs page, icons/inactive tabs ≥4.5:1, primary actions ≥7:1; add a "High contrast" display option.
**Applied in:** M32.

## R19 · 25 Oct · "100% functional" ATP: screeners, custom indicators, indicator algos, AI, SEBI algo rules
**Question:** what must a screener / custom-indicator / indicator-algo / AI platform include to count as fully functional, and what rules apply to live automation?
**Findings:**
- Screener standard (Chartink): SMA/EMA/MACD/BB/RSI/Aroon/Ichimoku…, daily→yearly and intraday TFs, comparisons + crossovers, math functions, custom indicators saved and reused in scans, segments (cash, futures, indices, watchlists), ANY/ALL logic, predefined scans, saved/private scans, alerts by SMS/email/push/webhook — [Chartink FAQ](https://chartink.com/articles/scanner/stock-screener-faq).
- Indicator algo platform: indicator conditions (RSI, MACD cross, BB, SuperTrend), AND/OR builder, optional AI from plain English, separate entry/exit rules, backtest (win rate, avg return, drawdown, CSV), paper forward test on live data, logs of every entry/exit, several strategies in parallel, go live after paper matches backtest — [AlgoTest](https://algotest.in/blog/paper-trading-apps-for-indicator-algo-strategies-in-india.md).
- Definition of done: unit/integration/e2e tests of critical journeys, user docs, flags rolled out or removed, validated in production under expected load, logs/metrics/alerts, no sev-1/2 bugs — [GitLab DoD](https://docs.gitlab.com/development/definition_of_done/).
- SEBI retail algo framework from 1 Apr 2026: orders only from an App ID tied to a whitelisted static IP; 2FA once every trading day (no endless refresh tokens); ≤10 orders/sec; market orders converted to price-protected orders; third-party platforms must be empanelled and hosted within the broker's infrastructure — [FYERS notice](https://fyers.in/notice-board/new-sebi-framework-for-retail-algo-trading-from-april-01-2026/); algo orders carry an exchange Algo-ID; white-box algos registered, black-box providers need RA licence; brokers responsible for algos on their platform — [Sahi](https://www.sahi.com/blogs/sebi-algo-trading-rules-2026-what-every-retail-trader-must-know-before-april).
**Decision:** P2-F functional-completeness phase with a per-feature definition of done; screener/custom indicator/strategy/AI specs as M34; LIVE automation needs a compliance path (static IP, daily 2FA, OPS cap, empanelment) — owner + lawyer task; PAPER unaffected.
**Applied in:** M34.

## R20 · 25 Oct · Timeframe selector (professional pattern)
**Findings:** TradingView: a dropdown with the full list grouped by type (minutes, hours, days, weeks, months), "+ Add custom interval", and a star to favourite intervals; starred favourites appear as one-click buttons in the top toolbar — [friendofthetrend](https://friendofthetrend.com/tradingview/how-to-change-timeframes/), [TradingView favourites](https://ru.tradingview.com/support/solutions/43000662392/).
**Decision:** TF control = grouped dropdown + user-starred favourites (default 5m, 15m, 1H, D) as quick buttons; replaces the 9-button row and the "More" variant everywhere (Charts, Terminal, Multi-chart).
**Applied in:** M36.

## R21 · 25 Oct · Terminal panel layout and option-chain columns
**Findings:** pro option chains let users pick/add/remove/reorder/resize columns and auto-fit (TradeStation) — [TradeStation OptionStation](https://help.tradestation.com/09_01/tsoptionpro/topics/formatting_columns_in_optionstation.htm); brokers admit not every column fits, users ask for OI change %, OI bar inside the OI column, ATM/ITM/OTM shading, bid/ask, volume — [Kite option chain thread](https://tradingqna.com/t/introducing-the-native-option-chain-on-kite-web-beta/179074?page=5).
**Decision:** chain in the Terminal gets a compact default column set + a column picker (saved per user), ATM centred; chart panel interactive in place (no navigation on click); default panel widths favour the chart; order panel compact until a price is picked.
**Applied in:** M39.

## R22 · 25 Oct · Above the fold — what goes first
**Findings:** eyetracking: the 100 px just above the fold get ~102% more views than just below; NN/g estimates ~84% average attention difference; put the most valuable content and actions above the fold — [NN/g page fold manifesto](https://nngroup.com/articles/page-fold-manifesto).
**Decision:** on data pages, key numbers (summary cards) and the main action (e.g. Ask AI) sit at the top; explanatory text goes below or behind (?).
**Applied in:** M40.

## R23 · 25 Oct · Trend state between CHoCH and BOS; choosing the swing size
**Findings:** an uptrend ends when the most recent higher low breaks (CHoCH); a lower high alone doesn't end it — [CrossTrade market structure](https://crosstrade.io/learn/price-action/market-structure). CHoCH is an early warning, not confirmation; wait for BOS in the new direction — [heygotrade CHoCH](https://www.heygotrade.com/en/blog/change-of-character-choch-trading). HTF filter has three states; in neutral, stand aside or reduce size — [LuxAlgo HTF trend filter](https://www.luxalgo.com/library/concept/higher-timeframe-trend-filter.md). Swing size: match the threshold to the holding period / the scale you trade, calibrate until plotted swings match it, then keep it stable — [LuxAlgo swing magnitude filters](https://www.luxalgo.com/library/concept/swing-magnitude-filters.md).
**Decision:** after a CHoCH and before a BOS the old trend has ended and the new one is unconfirmed ⇒ TRANSITION = range rules (edge fades only), not "old trend continues". External swing size chosen by evidence, not taste: the k that reproduces the owner's own Daily reads (NIFTY fixture: Daily DOWN on 12–13 Oct, price below the 5–6 Oct highs) and the answer-key swing items; 3 ATR stays provisional until then.
**Applied in:** M42.

## R24 · 25 Oct · Why ATP still looks dated — modern trading-app UI standard
**Findings:** live price first in large high-contrast type, secondary metrics smaller; progressive disclosure for retail, density for active traders; real-time feedback (connection, order progress, stale state, subtle motion); TF selector next to the chart; simple default ticket with advanced types secondary; summary before confirm with a deliberate gesture — [Lollypop trading app design 2026](https://lollypop.design/blog/2026/june/trading-app-design/?p=25070). Kite: zero clutter, calm, fast, watchlist-centred — [tradingqna Kite minimal](https://tradingqna.com/t/why-is-kite-built-with-such-a-minimal-interface/6373). Tabular numerals so prices align; Inter / IBM Plex / Source Sans 3 — [fontalternatives](https://fontalternatives.com/blog/best-fonts-legible-numerals-ui/). Native select only for short plain lists; ~12+ options or searchable items (symbols, expiries) → custom combobox with filter, recent/grouped, bottom sheet on phone — [saasui](https://www.saasui.design/blog/saas-dropdown-select-menu-ux-patterns).
**Decision:** UX-2 "pro look" order M43: symbol-first search, watchlist rail, typography + tabular numbers, custom comboboxes, remove page-top help text, live-feel states, density setting; resume UI-H page waves.
**Applied in:** M43.

## R25 · 25 Oct · Multiple broker accounts: Primary / Secondary and per-group order routing
**Question:** ATP user connects several broker accounts, one Primary and others Secondary; a setting decides which orders/exits run on which group. What is the standard design and what are the legal limits?
**Findings:**
- Copiers use a leader (parent) and followers (children). Quantity per follower is set by a multiplier (parent qty x coefficient) or by percentage of account balance; B2Broker lists six methods: proportional to balance, to equity, either x ratio, fixed lot, ratio multiplier. Size outside instrument min/max is clamped. https://help.quantower.com/quantower/trading-panels/copy-trading · https://b2broker.com/products/b2copy/knowledge-base/concepts/allocation-methods-copy-and-mam/
- The copier mirrors new orders, modifications, cancellations, attached SL/target and position closes. Follower can fail (insufficient funds, rejection, disconnect); parent and follower actions are not simultaneous so positions can misalign; the user gets a log/notification and a manual-action path; inactive connections are skipped with a notice. (Quantower page above)
- Indian retail context: broker APIs are meant for the user's own account; providers who place trades into other people's accounts raise concerns (credential sharing, unregistered advice, manipulation if many accounts trade one instrument, liability). Forum commentary, not legal advice. https://kite.trade/forum/discussion/comment/47734/ SEBI retail algo framework from 1 Apr 2026 (static IP, 2FA, OPS limit, empanelment) is per account/per broker => each connected broker account needs its own compliant link.
**Decision:** (1) Multi-account only for accounts owned by the SAME logged-in user (own accounts / own family set-up the user authorises with the broker); no copying to other ATP users, no strategy-provider/subscriber mode (lawyer first). (2) Roles: exactly one Primary; Secondary accounts grouped into user-named groups; per-account sizing mode (fixed lots / multiplier / % of capital), default multiplier 1. (3) Routing matrix in settings: order class (entry, adjustment, exit, combined/strategy exit) x target (Primary / Secondary groups). (4) EXITS FOLLOW POSITIONS: an exit/stop always runs on every account that actually holds that position, regardless of routing rules; routing only governs new entries. (5) Per-account independent execution with own client-order-id, own result row; no automatic rollback of accounts that succeeded; failed account => alert + retry/manual action; setting "secondaries only after Primary accepted" (default ON for entries). (6) Pre-send per-account margin/freeze-limit/lot checks; a failing account is skipped with an alert, others continue. (7) Shorts-first per account. (8) Aggregated "All accounts" view plus per-account view. (9) PAPER = LIVE logic; LIVE stays OFF until owner switch.
**Applied in:** M45.

## R26 · 25 Oct · Page redesign: purpose-first screens, progressive disclosure, bot builder flow, bot naming
**Question:** Pages feel monotone and crowded; user must scroll around to learn what each thing is for; Paper bot page overloaded; "Paper bot" is the wrong name.
**Findings:** Progressive disclosure (Nielsen): show only the few most important options first, reveal specialised ones on request; whatever shows first is read as important; improves learnability, efficiency and error rate; the link to the next level must be clearly labelled. https://brajeshwar.com/2006/progressive-disclosure-by-jakob-nielsen-usability-expert/ Bot-builder users complain when settings are spread across a long form and they scroll up/down to see the effect; they ask for related settings grouped in one place with live preview. https://community.gainium.io/t/streamline-dca-bot-settings-layout/1748 (Earlier: R24 modern trading-app standard; colour v3 mockup.)
**Decision:** (1) One naming rule: the product is "AI Trading Bot"; Paper vs Live is a MODE chip on the bot (same logic both; Live only behind the owner switch), not a different product. Copy must state that the bot executes the user's own saved strategy rules; AI only helps draft strategies/explain (AI never places/blocks/changes orders). (2) Every page = purpose line + master-detail: pick on the left/top, next card opens for that choice; collapsed otherwise. (3) Bot builder = 3-step flow with sticky summary, related risk values grouped together, no page-top help. (4) Colour v3 (per-section accent + gradient hero + tinted nav chips) applied to ALL pages, not one.
**Applied in:** M47.

## R27 · 25 Oct · OI build-up reference (why ATP shows all zeros)
**Question:** Build-up table/chart shows 0.00 / "No clear change" for all strikes. What reference should OI change and price change use?
**Findings:** "Change in OI" = current session OI minus previous session OI (NSE-style). Build-up = price direction x OI change: price up + OI up = long build-up; price down + OI up = short build-up; price up + OI down = short covering; price down + OI down = long liquidation (unwinding). Use with volume/context, not alone. https://www.sahi.com/blogs/open-interest-change-in-oi-nse-guide
**Decision:** ATP compares against the PREVIOUS SESSION close (OI and price) as the default; "since first stored snapshot" only as an optional intraday view, and only when snapshots differ. If nothing changed, show one line, not an empty chart/table.
**Applied in:** M48.

## R28 · 25 Oct · Proper UI design brief for ATP (mobile-first fintech/trading)
**Question:** How should ATP be designed as a whole (not piecemeal) so it feels modern, varied in colour, purpose-first and not crowded?
**Findings:** Mobile dashboards: clear visual hierarchy, essential first; bottom navigation for key destinations, search + notifications in the top bar; stacked cards instead of wide tables when rows need not be compared, or fewer columns + swipe; tap-to-reveal chart details, fewer bars; touch targets >= 48dp; progressive disclosure; visible enabled/disabled and loading states. https://www.toptal.com/designers/dashboard-design/mobile-dashboard-ui Fintech 2026: restrained colour reserved for meaningful states, avoid alarming red unless real danger, calm copy and clear recovery paths; task-based navigation, core tasks within one tap; plain-language disclosure of risk before commit; single-step forms with save-progress; WCAG 2.2 contrast; label charts directly + drill-down; brief microinteractions; explain why a suggestion appears. https://www.onething.design/post/top-10-fintech-ux-design-practices-2026 Summary-to-detail: one primary summary, compact secondary metrics, detail below (superdesign pattern page, thin). Earlier: R24 (modern trading-app standard), R26 (progressive disclosure, bot flow).
**Decision:** One consolidated design brief (M49) that supersedes M43/M46/M47/M48 as the UI source of truth: design-first (spec + mockups approved by owner), then waves. Colour: several section accents for identity, but semantic colours (profit/loss/status) kept consistent and restrained.
**Applied in:** M49.

## R29 · 26 Oct · Broker login: Upstox analytics token vs daily token; why "Practice only" on Kotak Neo / Groww
**Question:** Abhi is asked for the Upstox analytics token repeatedly and the login is confusing; do all brokers log in smoothly; why are Kotak Neo and Groww marked "Practice only"?
**Findings:** Upstox Analytics Token = read-only (GET only, no orders), valid ONE year, one per account, generated once in Developer Apps > Analytics without OAuth; market data/option chain/historical need no static IP; orders/portfolio/user need a whitelisted static IP. https://upstox.com/developer/api-documentation/analytics-token/ The Upstox access token (trading) dies at 03:30 IST next day regardless of issue time; daily login by OAuth code or by TOTP+PIN (/v2/totp-login, needs TOTP on the account); a new token revokes the active one. https://upstox.com/developer/api-documentation/get-token Groww access token expires daily 06:00 IST; generated by API key + checksum approval flow or TOTP. https://apis.io/apis/groww/groww-authentication-api/ Kotak Neo: TOTP + MPIN login (docs not fully confirmed). ATP code review (public repo @e5abf39): Upstox analytics token is already modelled as 1-year with 7-day expiry warnings and daily-token detection; "Practice only" for Kotak Neo and Groww is a deliberate gate (gates.py): live orders/prices stay closed until the lawyer's opinion and the broker's written confirmation (TM-5/TM-6).
**Decision:** (1) Two separate, clearly named things in the UI: "Market data link" (analytics token, once a year) and "Daily trading login" (every morning, one tap; only needed for orders/positions). (2) If Abhi is asked for the analytics token repeatedly, diagnose from stored state (expiry, last probe, refusal hook) instead of guessing — most likely a DAILY access token was pasted as the analytics token, or a refusal re-probe marks it unusable. (3) Keep the Practice-only gate (it is a legal safeguard) but change the wording/visual. (4) Per-broker login test matrix before LIVE.
**Applied in:** M52.

## R30 · 26 Oct · Trading-bot Telegram messages: clarity, severity, noise
**Question:** Telegram messages from the Trade bot confuse Abhi (mixed languages, raw codes, error alarms at 09:21, dashboard disagrees).
**Findings:** Low-noise alert design: one severity per alert type tied to an action and response window (Critical interrupts; Warning check; Digest later); notify only on meaningful state changes, dedupe by a stable key (entity+state), repeated events update one incident; each message carries severity, entity, impact with value and threshold, evidence/timestamp, concrete action, status; "no events" must be distinguishable from a broken pipeline (heartbeat). https://www.agensi.io/skills/low-noise-alert-system-design Notification practice: short scannable messages, combine related events into one, batch non-urgent into digests, one channel only, thread/edit updates instead of new messages. https://knock.app/manuals/slack-notifications/best-practices-for-slack-notifications
**Decision:** Message catalogue with 3 tiers; one language (Marathi, English only for symbols/terms); no raw codes or internal names; Indian number format; expected waits are silent or INFO; state-change only + dedupe; position status edited in place or sent at fixed times; heartbeat; dashboard and Telegram read the same source.
**Applied in:** M53.

## R31 · 30 Oct · Trading journal: what a working one needs
**Findings:** Common core of journal tools (Tradervue, TradeZella, Edgewonk, RizeTrade): automatic trade import from the broker; tags + filters to drill into trades; chart with entries/exits marked; stats (win rate, profit factor, MFE/MAE, by setup/time); periodic review (weekly); playbooks = strategy rules with adherence tracking; mistakes/emotion logging (revenge, FOMO). https://www.tradervue.com/blog/best-trading-journal
**ATP today (code):** backend/app/journal = "discipline engine" (auto-capture hooks, behaviour-tag detectors, weekly 0-100 score, review) behind flag `discipline_engine` OFF by default; routes: settings, week, review, trade detail, add/patch tags; no manual entry, no notes editing route, no screenshot/chart attach, no export; frontend JournalPage + SimilarSetupsV2. So the page exists but is empty for every tenant until the flag is on, and even then it is capture-only.
**Decision:** M62 — turn the engine on for the owner, then make the journal a real journal: per-trade notes + plan-vs-execution + mistake tags + chart snapshot at entry/exit + manual trades, stats by setup, weekly review, export; numbers only, no advice.
**Applied in:** M62.

## R32 · 30 Oct · Order-time risk checks: what blocks, what the prevalent practice is
**ATP today (code main 43f0e1f):** risk_engine/risk_manager.py validate_and_size runs on every entry: NO_TRADE/levels finite; min R:R (only if set; legacy org default 1.2 in routes.py:22, config default 1.5); max trades/day; max open positions; max consecutive losses; daily loss limit; then SIZING from risk-per-trade ÷ (entry−stop) in units of the contract lot — a short with no stop is REFUSED ("No stop-loss is set…"), and a size below one lot is REFUSED ("below one lot for the configured risk per trade"). Extra layers: by_default "My limits" (risk_per_trade_pct 1%, daily_loss 2%, max_trades 10, min_rr 1.5, sector/correlated caps), loss_streak, guardian, hierarchy (org > user), portfolio caps (flag), VIX gate (flag), kill switch, margin safety 0.8 (contract_execution.py:34), MAX_LOTS 500 (paper/fno_ticket). For an options seller the risk-%÷stop-distance sizing on option premium rarely yields ≥1 lot and short legs without a stop are blocked — hence "too many issues at order time".
**Findings (web):** Guides describe stop-loss (fixed % or structural), targets (R-multiple or structural), trailing stops, volatility/performance-based sizing, diversification; platform docs list position size as a QUANTITY (contracts/lots — "% of equity" can size to 0 contracts), per-trade max loss in money, trading-hours window, end-of-day flatten; no public source gives standard default numbers. https://www.shareindia.com/knowledge-center/algo/how-to-set-up-smart-risk-management-in-algo-trading-targets-stop-losses-more · https://help.edgeful.com/en/articles/12858383-customizable-algo-parameters-and-risk-controls
**Decision:** Prevalent practice for Indian F&O = size in LOTS; per-day money/percent loss limit; max open positions; max lots per order ≤ exchange freeze; optional streak cool-down; no R:R filter unless the user sets one (owner rule C3). Every check = a user setting with a default; every block = one plain sentence + "Change limit" link; nothing silent; exits never checked.
**Applied in:** M64.
