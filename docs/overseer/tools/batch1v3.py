import sys;sys.path.insert(0,'/home/claude/ak/lib');import ak,json
h=ak.load('1H'); d=ak.load('D')
G,R,B,P="#1a7f37","#b2182b","#2166ac","#6a3d9a"
I=lambda **k:k
items=[
I(id="L01",title="X01 · Daily support 56,023.6–56,169.4 · 11 Sep gap below",win=("2026-09-08","2026-09-14"),band=(56023.6,56169.4,B,"Daily support"),
 marks=[("2026-09-11 09:15",55699.4,"gap below, low 55,699",R,"^"),("2026-09-11 10:15",56220,"back inside",G,"v")],nx=[],
 verdict="SWEEP / retest — ALIVE (support)",known="back inside 11 Sep 10:15; next Daily swing low 53,027 (3 Jun) never reached",
 reason="Close below the band (gap), but price never ran to the next Daily swing low (53,027) and came straight back inside. BREAK-2 ⇒ not broken. Reader's E4(b) bear call 11 Sep 10:15 must NOT exist."),
I(id="L02",title="Same Daily support · 15–16 Sep closes below",win=("2026-09-14","2026-09-19"),band=(56023.6,56169.4,B,"Daily support"),
 marks=[("2026-09-15 15:15",55794.8,"low 55,795",R,"^"),("2026-09-16 09:15",55812.2,"low 55,812",R,"^"),("2026-09-16 12:15",56300,"back above",G,"v")],nx=[],
 verdict="SWEEP / retest — ALIVE (support)",known="next Daily swing low 53,027 never reached",
 reason="Closes below on 15–16 Sep, lows 55,795 / 55,812, far from the next Daily swing low 53,027; back above on 16 Sep. ⇒ sweep, alive."),
I(id="L03",title="1H support 55,699.5–55,970.2 · 24–28 Sep",win=("2026-09-22","2026-09-30"),band=(55699.45,55970.15,B,"1H support"),
 marks=[("2026-09-24 09:15",55505.8,"close below (beyond, not broken)",R,"^"),("2026-09-28 09:15",54600,"28 Sep reaches 55,097.6 ⇒ BROKEN",R,"^")],nx=[(55097.6,P,"next 1H swing low 55,097.6 (11 Jun)")],
 verdict="BROKEN only on 28 Sep (not 24 Sep) ⇒ then FLIPPED resistance",known="known 28 Sep 09:15; 24–27 Sep = 'beyond, not broken'",
 reason="24 Sep closes below and price stays below, but the next 1H swing low (55,097.6) is closed beyond only on 28 Sep 09:15. Until then: 'beyond, not broken' ⇒ no flip entry, so the 25 Sep E4(b) bear call = NO. From 28 Sep 09:15 broken ⇒ flipped resistance."),
I(id="L04",title="Same band, flipped resistance · 15 Oct closes above",win=("2026-10-12","2026-10-19"),band=(55699.45,55970.15,R,"flipped resistance"),
 marks=[("2026-10-15 13:15",56065.5,"closes above, high 56,066",R,"v")],nx=[(56623.8,P,"next 1H swing high 56,623.8 (23 Sep)")],
 verdict="SWEEP / retest — flip still ALIVE (not dead)",known="next 1H swing high 56,623.8 never reached",
 reason="15 Oct closes above, high 56,066, but the next 1H swing high 56,623.8 is never reached and price falls back. ⇒ retest of the flip, not broken back ⇒ not dead."),
I(id="L05",title="1H supply 58,078.9–58,252.0 (7–8 Jul top) · 17 Jul spike",win=("2026-07-13","2026-07-22"),band=(58078.9,58251.95,R,"1H supply"),
 marks=[("2026-07-17 15:15",58596.8,"wick to 58,597 but CLOSE 58,576 < 58,581",R,"v"),("2026-07-20 09:15",57590,"gap back below",G,"^")],nx=[(58581.1,P,"next 1H swing high 58,581.1 (7 Jul)")],
 verdict="SWEEP / retest — supply ALIVE",known="17 Jul 15:15 only a WICK beyond the next swing; close 58,576 below it ⇒ no break",
 reason="17 Jul closes above the band, and the last bar's wick (58,596.8) pokes past the next 1H swing high 58,581.1, but that bar CLOSES at 58,576, below the swing. Research: a wick through a swing that closes back = sweep (SFP), not a break. ⇒ never broken; next day gap back below. Supply alive. Reader marked it BROKEN and took E4(b) 20 Jul 14:15 — wrong label (it would be a test of a live supply, not E4(b))."),
I(id="L06",title="E26 · 1H supply 57,611.7–57,799.2 · 26–31 Aug",win=("2026-08-21","2026-09-02"),band=(57611.7,57799.15,R,"1H supply"),
 marks=[("2026-08-26 09:15",57996,"26 Aug passes 57,874 ⇒ BROKEN",G,"v"),("2026-08-31 10:30",57187,"31 Aug 10:30 closes below 57,252 ⇒ DEAD",R,"^")],nx=[(57873.8,G,"next 1H swing high 57,873.8 (24 Aug)"),(57251.6,R,"next 1H swing low 57,251.6 (25 Aug)")],
 verdict="BROKEN 26 Aug 09:15 (flip to support) → DEAD 31 Aug 10:30",known="broken known 26 Aug 09:15; dead known 31 Aug 10:30 (not 28 Aug)",
 reason="26 Aug gap candle closes above and closes beyond the next 1H swing high 57,873.8 ⇒ broken, flipped support. 27–28 Aug closes back below, but the next 1H swing low 57,251.6 is closed beyond only on 31 Aug 10:30 ⇒ DEAD from 31 Aug 10:30. No bear call at this band after 26 Aug 09:15 (the E26 E1 at 09:20 sits on another band, 1H 57,738–57,964)."),
I(id="L07",title="1H resistance 56,474.4–56,570.5 (dup ids 288/289) · 21–23 Sep",win=("2026-09-17","2026-09-25"),band=(56474.4,56570.45,R,"1H resistance"),
 marks=[("2026-09-21 14:15",56668.2,"closes above, high 56,668",R,"v"),("2026-09-23 11:15",56623.8,"",R,"v")],nx=[(56996.4,P,"next 1H swing high 56,996.4 (15 Sep)")],
 verdict="SWEEP ×3 — resistance ALIVE; ONE object (one id)",known="next 1H swing high 56,996.4 never reached",
 reason="17 closes above across 21–23 Sep, highs 56,668 / 56,671 / 56,624, never near the next 1H swing high 56,996.4 ⇒ retests/sweeps; alive. One band = one id."),
I(id="L08",title="Weekly support 54,891.3–56,098.7 · 28–29 Sep",win=("2026-09-24","2026-10-19"),band=(54891.25,56098.7,B,"Weekly support"),
 marks=[("2026-09-29 09:15",53785.7,"low 53,786",R,"^")],nx=[(52783.45,P,"next Weekly swing low 52,783 (May) — never reached")],
 verdict="SWEEP — Weekly support ALIVE (not broken)",known="next Weekly swing low 52,783 never reached",
 reason="Closes below on 28–29 Sep, low 53,786, but the next Weekly swing low 52,783 is never reached; October back inside. BREAK-2 ⇒ not broken. Band 1,207 pt wide — a separate area-band item."),
]
for it in items:
    fn=f"/home/claude/ak/charts/v3_{it['id']}.png"
    ak.plot(h,*it["win"],fn,f"{it['id']} · {it['title']}",bands=[it["band"]],marks=[tuple(m) for m in it["marks"] if m[2]],hlines=it["nx"],texts=[f"VERDICT: {it['verdict']}",it["known"]],figsize=(12,5.6))
    it["chart"]=fn
json.dump(items,open("/home/claude/ak/batch1v3.json","w"),indent=1); print("ok")
