import sys;sys.path.insert(0,'/home/claude/ak/lib');import ak,json
h=ak.load('1H'); d=ak.load('D')
G,R,B,K="#1a7f37","#b2182b","#2166ac","#6a3d9a"
items=[
dict(id="L01",title="X01 · Daily support 56,023.6–56,169.4 · 11 Sep gap below",tf=h,win=("2026-09-08","2026-09-14"),band=(56023.6,56169.4,B,"Daily support"),
 marks=[("2026-09-11 09:15",55699.4,"gap below, low 55,699\n(no held swing below)",R,"^"),("2026-09-11 10:15",56220,"back inside / above",G,"v")],
 verdict="SWEEP — object ALIVE (support)",known="known 11 Sep 10:15 (first 1H close back inside; no swing high formed below the band)",
 reason="Close below the band, but price never built a swing on the far side: no pullback high below 56,023.6. It went straight back inside and closed the day at 56,606. BREAK-1 (b) ⇒ sweep. Reader's E4(b) bear call 11 Sep 10:15 (treats it as a broken support) must NOT exist."),
dict(id="L02",title="Same Daily support 56,023.6–56,169.4 · 15–16 Sep closes below",tf=h,win=("2026-09-14","2026-09-19"),band=(56023.6,56169.4,B,"Daily support"),
 marks=[("2026-09-15 15:15",55794.8,"low 55,795",R,"^"),("2026-09-16 09:15",55812.2,"low 55,812",R,"^"),("2026-09-16 12:15",56300,"back above",G,"v")],
 verdict="SWEEP — object ALIVE (support)",known="known 16 Sep ~12:15 (back above the band; no held swing below)",
 reason="Several 15M/1H closes below (15 Sep 14:00 → 16 Sep 10:00) and two lows below, but no pullback high that stayed below the band. Two lows below the band are still the extreme, not acceptance. ⇒ sweep, support stays alive."),
dict(id="L03",title="1H support 55,699.5–55,970.2 (base of the 11 Sep rally)",tf=h,win=("2026-09-22","2026-09-29"),band=(55699.45,55970.15,B,"1H support"),
 marks=[("2026-09-24 09:15",55505.8,"gap + close below",R,"^"),("2026-09-24 11:15",55670.8,"pullback high 55,671\nstays BELOW ✓",R,"v")],
 verdict="BROKEN (24 Sep) ⇒ FLIPPED to resistance",known="known 24 Sep 11:45 (15M swing high 55,670.8 at 11:15 confirmed, below the band)",
 reason="Close below + a swing high formed on the far side (55,671 < 55,699) and price stayed below. BREAK-1 (b) ⇒ broken. From 11:45 it is a flipped resistance; a later retest from below (25 Sep) can be a bear-call location."),
dict(id="L04",title="Same 1H 55,699.5–55,970.2, now flipped resistance · 15 Oct closes above",tf=h,win=("2026-10-12","2026-10-19"),band=(55699.45,55970.15,R,"flipped resistance"),
 marks=[("2026-10-15 13:15",56065.5,"closes above, high 56,066\nno held swing above",R,"v"),("2026-10-16 09:15",55989.6,"",R,"v")],
 verdict="SWEEP — flipped resistance still ALIVE (not dead)",known="state unchanged through 19 Oct",
 reason="4 × 15M closes above on 15 Oct, but no pullback low formed above 55,970 and price came back inside. Broken back needs the same (b) test ⇒ not met ⇒ the flip is NOT dead."),
dict(id="L05",title="1H supply 58,078.9–58,252.0 (7–8 Jul top) · 17 Jul close above",tf=h,win=("2026-07-13","2026-07-22"),band=(58078.9,58251.95,R,"1H supply"),
 marks=[("2026-07-17 15:15",58596.8,"late close above 58,576",R,"v"),("2026-07-20 09:15",57590,"gap back below",G,"^")],
 verdict="SWEEP — supply ALIVE",known="known 20 Jul 09:15 (gap back inside/below; no swing low ever formed above 58,252)",
 reason="Strong close above on 17 Jul, but the only swing above is the high itself; no pullback low held above the band. Next day gap back below. ⇒ sweep. Reader marked it BROKEN and took an E4(b) on 20 Jul 14:15 — wrong label (if anything it is a test of a live supply, E1/E3 logic, not E4(b))."),
dict(id="L06",title="E26 · 1H supply 57,611.7–57,799.2 · 26 Aug gap candle",tf=h,win=("2026-08-21","2026-09-02"),band=(57611.7,57799.15,R,"1H supply"),
 marks=[("2026-08-26 09:15",57996,"gap candle closes above",G,"v"),("2026-08-26 10:15",57824.4,"pullback low 57,824\nHOLDS above ✓",G,"^"),("2026-08-28 10:15",57596.4,"pullback high 57,596\nholds BELOW ✓ ⇒ DEAD",R,"v")],
 verdict="BROKEN 26 Aug (flip to support) → DEAD 28 Aug",known="broken known 26 Aug 10:45; dead known 28 Aug 11:15",
 reason="26 Aug: close above + swing low 57,824 above the band ⇒ broken, flipped support. 27–28 Aug: closes back below + swing high 57,596 below the band ⇒ broken back ⇒ DEAD (no second flip; the 31 Aug spike to 58,025 does not revive it). So the E26 bear-call entry on 26 Aug 09:15 at this 'supply' must NOT exist, and no trade off this band after 28 Aug 11:15."),
dict(id="L07",title="1H resistance 56,474.4–56,570.5 (the duplicate-id band 288/289) · 21–23 Sep",tf=h,win=("2026-09-17","2026-09-25"),band=(56474.4,56570.45,R,"1H resistance"),
 marks=[("2026-09-21 14:15",56668.2,"closes above, high 56,668",R,"v"),("2026-09-22 09:15",56671.1,"",R,"v"),("2026-09-23 11:15",56623.8,"",R,"v")],
 verdict="SWEEP ×3 — resistance ALIVE; ONE object (one id)",known="state unchanged until 24 Sep gap down",
 reason="17 closes above across 21–23 Sep, yet no pullback low ever held above 56,570 — each push fell back inside. ⇒ sweeps; still alive. It is one band = one id (288 and 289 must be the same object)."),
dict(id="L08",title="Weekly support 54,891.3–56,098.7 · 28 Sep break",tf=h,win=("2026-09-24","2026-10-19"),band=(54891.25,56098.7,B,"Weekly support"),
 marks=[("2026-09-28 09:15",54494.4,"close below",R,"^"),("2026-09-28 11:15",54660.6,"pullback high 54,661\nholds below ✓",R,"v")],
 verdict="BROKEN 28 Sep ⇒ FLIPPED resistance; never broken back (alive)",known="broken known 28 Sep 12:15",
 reason="Close below + swing high 54,661 below 54,891 ⇒ broken. October rally re-entered the (very wide) band but never closed above 56,098.7 ⇒ flip alive. Note: a 1,207-pt Weekly band is too wide to trade as one location — band width is a separate item (area band)."),
]
for it in items:
    lo,hi,col,lab=it["band"]
    fn=f"/home/claude/ak/charts/{it['id']}.png"
    ak.plot(it["tf"],*it["win"],fn,f"{it['id']} · {it['title']}",bands=[it["band"]],marks=[tuple(m) for m in it["marks"] if m[2]],texts=[f"VERDICT: {it['verdict']}",it["known"]],figsize=(12,5.6))
    it["chart"]=fn
json.dump([{k:v for k,v in i.items() if k!="tf"} for i in items],open("/home/claude/ak/batch1.json","w"),indent=1)
print("ok")
