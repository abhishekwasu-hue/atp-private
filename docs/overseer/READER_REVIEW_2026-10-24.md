# Chart reader — सगळ्या concepts चा research-आधारित review (24 Oct)

स्रोत: trade-data मधले reader चे reports (layers 1–6a, entry models, area map) आणि खाली दिलेले web स्रोत.
निशाणी: ✅ standard प्रमाणे · ⚠️ सुधारणा हवी · ❌ मोठी चूक.

| # | Concept | Reader आज काय करतो | Standard (research) | निकाल | प्रस्ताव |
|---|---|---|---|---|---|
| 1 | **Swings** (layer 1) | "Leg मधल्या सगळ्यात मोठ्या pullback पेक्षा मोठी चाल" + D0/D1/D2 आकार points मध्ये (उदा. D0 = 153.5 pt). Layer 1 ला ✅ नाही; नियम 12 पैकी 4 cases मध्येच जुळला. | Swing = fractal pivot + आकाराचा filter. ATR च्या पटीत आकार volatility प्रमाणे बदलतो; points चा आकडा बदलत नाही. Confirmed swing बदलत नाही; शेवटचा leg तात्पुरता. Swings ची external / internal अशी विभागणी. | ❌ | Swing = pivot + ATR-पट आकार (setting) प्रत्येक TF वर. प्रत्येक swing ला external / internal label. BREAK-2 (S1) आणि zones याच्यावर अवलंबून. **सगळ्यात आधी.** |
| 2 | **Trend / Daily side** | Statistical regime: H_sigma, net_ratio, "drift / transition". | Trend = external swings ची रचना: HH+HL = up, LH+LL = down, मिश्र = range. Trend तेव्हा बदलतो जेव्हा संरक्षक swing (शेवटचा HL / LH) close ने तुटतो (CHoCH), आणि नवीन दिशेचा BOS त्याला confirm करतो. मोठ्या TF चा फक्त बंद झालेला bar. | ❌ | Daily side = Daily external structure. Statistical regime फक्त माहिती म्हणून. Range = मिश्र रचना ⇒ फक्त edge trades. |
| 3 | **Zones** | Swing candle चा wick-to-body; BOS origin base. | Departure आधीचा base; RBR/DBD पण; departure ची ताकद; freshness. | ⚠️ | M7 (आधीच तयार, BREAK-2 नंतर). |
| 4 | **Lifecycle** | BREAK-2 + external swing (S1) — आज ठरलं. | Close + follow-through; false break; internal swings मोजायचे नाहीत. | ✅ | PR येतोय. |
| 5 | **Lines (trendlines)** | दोन reactions, मधे उलट swing; touch = wick पोहोचतो, body बाजूला; break = close + पलीकडे swing (जुना नियम). | दोन prominent swings रेषा काढतात, तिसरा touch ती valid करतो; wick की body हा नियम एकदा ठरवून कायम; break = close + follow-through/retest; रेषा तुटणे म्हणजे वेग बदल, reversal नाही. | ⚠️ | Anchors = external swings. Line break = BREAK-2 (M6 मध्ये "area or line" आहे — session ने lines ला लावलं याची खात्री). Line break एकटा entry/reversal नाही. |
| 6 | **Confluence** | रेषा area ला भेटते किंवा Daily/Weekly overlap ⇒ confirming पुरावा. | स्वतंत्र level बरोबर overlap ⇒ दर्जा वाढतो. | ✅ | — |
| 7 | **Handover / commitment / absorption** | Push नाकारला + dominant candle; commitment चा volume approach leg च्या सरासरीपेक्षा जास्त; absorption ⇒ trade नाही. | Wyckoff effort vs result: volume स्वतःच्या baseline शी तुलना; मोठा volume पण progress नाही = absorption; displacement candle = commitment. | ✅ | — |
| 8 | **Pullback volume** | "Zone मध्ये selling volume वाढणं" = confirming. | Pullback कमी volume ने आणि impulse जास्त volume ने = trend पुढे जाण्याचं लक्षण. | ⚠️ | पर्याय (तुमचा निर्णय): "approach leg चा volume impulse पेक्षा कमी" हा confirming पुरावा. नवीन नियम म्हणून आपोआप नाही. |
| 9 | **5M trigger (LTF CHoCH)** | Area मध्ये आल्यावर 5M उलटी रचना close ने तुटणे. | Zone + LTF CHoCH = सगळ्यात विश्वासार्ह confirmation; किंमत: entry उशिरा. | ✅ | CHoCH ने तोडायचा swing = शेवटचं टोक बनवणारा 5M swing (external on 5M). |
| 10 | **Entry models E1–E4** | E1 aggressive, E2 confirmation, E3 structure, E4a sweep, E4b retest. Required set (handover + commitment + volume + 5M CHoCH) नसताना पण E1/E3/E4b entries होतात (label नाही). | Aggressive entry = confirmation शिवाय ("blind"); फक्त backtest केलेल्या levels साठी. | ❌ | **तुमचा स्वतःचा 6a नियम:** "Required set पूर्ण झाला तरच entry". Code मात्र required set नसतानाही entry देतो. 13 Oct चे 5 bear calls असेच होते, आणि पाचही stop-out झाले. ⇒ required set नसलेली entry = फक्त "watch" alert, position नाही. |
| 11 | **RSI divergence** | Zone कडे येणाऱ्या चालीतले pushes; दोन pushes असलेली सगळ्यात मोठी degree; RSI टोकाच्या bar वर; confirmed pivots; gate नाही, confirming पुरावा. | Price आणि oscillator चे swings त्याच चालीचे जोडायचे; फक्त confirmed pivots; divergence वेळ ठरवत नाही — BOS / reversal candle ने confirm. Hidden divergence = trend पुढे जाण्याचं लक्षण. | ✅ / ⚠️ | पद्धत standard प्रमाणे. पर्याय (तुमचा निर्णय): hidden divergence (pullback चं टोक vs आधीचा trend swing) confirming पुरावा म्हणून. Degree आता D0/D1 ऐवजी external/internal वर (#1 नंतर). |
| 12 | **Invalidation / stop** | Refined base ची दूरची कडा / sweep चं टोक. | Stop external swing / zone च्या distal कडेपलीकडे; internal levels नेहमी sweep होतात. | ⚠️ | Invalidation = zone ची distal कडा किंवा sweep टोक (जे पलीकडे असेल). Zone च्या आतली internal कडा कधीच नाही (A7 #1 सारखी 10 pt invalidation नाही). |
| 13 | **पुढचा area (target)** | Outcome मोजण्यासाठी पुढचा उलट area. | Seiden: पुढच्या उलट zone पर्यंत जागा = odds वाढवणारा घटक. | ✅ | Zone label वर "room" दाखवायचा (M7 Z5 मध्ये आहे). |
| 14 | **Duplicate signals** | जवळजवळ सारख्या areas ⇒ एकाच bar वर अनेक entries. | Overlap असलेले zones: एकच location म्हणून trade. | ⚠️ | Merge नाही; पण एका location वरून एकाच visit मध्ये एकच entry (overlap असलेले objects = एक cluster). |
| 15 | **Data** | Closing auction flag, FUT volume नसेल तर fail-closed, holdout sealed. | Reliable volume data आवश्यक; out-of-sample चाचणी. | ✅ | — |

## सुचवलेला क्रम (एका वेळी एक थर)
1. BREAK-2 PR (चालू) → 2. **Swings + trend (#1, #2)** → 3. Zones (M7) → 4. Entry gate + invalidation + duplicates (#10, #12, #14) → 5. RSI (C) → 6. Trigger / next area (D + E).
कारण: swings हा पाया आहे; BREAK-2 चा "external swing" आणि zones दोन्ही त्याच्यावर उभे आहेत. Session चा आत्ताचा क्रम (C → D+E → Z) पायाआधी वरचे थर बांधतो.

## स्रोत
- Swing magnitude filters — https://www.luxalgo.com/library/concept/swing-magnitude-filters.md
- Internal vs external structure — https://www.luxalgo.com/library/concept/internal-vs-external-structure.md
- Market structure (trend/range/CHoCH) — https://crosstrade.io/learn/price-action/market-structure
- HTF trend filter — https://www.luxalgo.com/library/concept/higher-timeframe-trend-filter.md
- Trendline — https://www.luxalgo.com/library/concept/trendline.md
- Supply & demand zones / scoring — https://www.luxalgo.com/library/concept/supply-and-demand-zones.md · https://www.luxalgo.com/library/concept/zone-scoring-and-refinement.md
- Effort vs result (Wyckoff) — https://www.luxalgo.com/library/concept/effort-vs-result/
- Entry confirmation — https://www.quantum-algo.com/academy/entry-confirmation-techniques/
- RSI divergence — https://www.luxalgo.com/library/indicator/RRp1xOWb-rsi-divergence/
- Pullback triggers — https://tradingsetupsreview.com/4-price-action-trading-strategies-pullback-traders
- Departure strength — https://www.fxstreet.com/education/lesson-from-the-pros-stocks-201504280000
