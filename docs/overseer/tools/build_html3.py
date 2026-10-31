import sys,json,base64;sys.path.insert(0,'/home/claude/ak/lib');from mr3 import MR
items=json.load(open('/home/claude/ak/batch1v3.json'))
css="""body{font-family:system-ui,'Noto Sans Devanagari',sans-serif;max-width:1180px;margin:auto;padding:16px;background:#f7f7f5;color:#222}
.it{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px;margin:18px 0}
h1{font-size:22px}h2{font-size:17px;margin:4px 0}.v{font-weight:700;color:#7a1f1f}.k{color:#555;font-size:14px}
img{width:100%;border:1px solid #eee;border-radius:6px}.r{font-size:15px;line-height:1.55}.en{font-size:13px;color:#555}
.ans label{margin-right:18px;font-size:16px}textarea{width:100%;height:44px}.rule{background:#fff8e1;border:1px solid #f0d58c;padding:12px;border-radius:8px}
button{font-size:15px;padding:8px 14px}"""
h=[f"<!doctype html><html lang=mr><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Answer key batch 1</title><style>{css}</style></head><body>",
"<h1>Answer key · Batch 1 v3 — Lifecycle (8 items, BREAK-2)</h1>",
"""<div class=rule><b>BREAK-2 (तुमचा नियम, 24 Oct):</b><br>
• <b>BROKEN</b> = zone पलीकडे close <b>आणि</b> price <b>पुढच्या swing च्या पलीकडे close करते</b> (zone च्या स्वतःच्या TF चा सगळ्यात जवळचा swing; फक्त wick = त्या swing चा sweep, break नाही). तो bar = 'कळलेला' bar.<br>
• त्याआधी आत परत आली ⇒ <b>RETEST / sweep</b>, zone जिवंत (इथे entry). पलीकडे आहे पण swing गाठला नाही ⇒ 'पलीकडे, broken नाही' — flip entry नाही.<br>
• Flip झालेला zone परत तोडायला (DEAD) तोच नियम, उलट्या बाजूच्या पुढच्या swing पर्यंत. Dead नंतर दुसरा flip नाही.<br>
• जांभळी / रंगीत आडवी रेषा = पुढचा swing. Band = reader चा.</div>"""]
for it in items:
    v,kn,rs=MR[it['id']]
    b=base64.b64encode(open(it['chart'],'rb').read()).decode()
    h.append(f"""<div class=it id={it['id']}><h2>{it['id']} · {it['title']}</h2><div class=v>निकाल: {v}</div><div class=k>{kn}</div>
<img src='data:image/png;base64,{b}'><p class=r>{rs}</p>
<div class=ans><label><input type=radio name={it['id']} value=ok> ✓ बरोबर</label><label><input type=radio name={it['id']} value=no> ✗ चूक</label></div>
<textarea id=c_{it['id']} placeholder='चूक असेल तर बरोबर काय (फक्त तिथेच लिहा)'></textarea></div>""")
h.append("""<button onclick="let o={};document.querySelectorAll('.it').forEach(d=>{let id=d.id,r=d.querySelector('input:checked');o[id]={ans:r?r.value:'',note:document.getElementById('c_'+id).value}});let t=JSON.stringify(o);navigator.clipboard.writeText(t).then(()=>alert('उत्तरं copy झाली — chat मध्ये paste करा'),()=>prompt('copy करा:',t))">उत्तरं copy करा</button></body></html>""")
open('/home/claude/ak/ANSWER_KEY_BATCH1_v3.html','w').write("".join(h))
# JSON for session (English)
out=[{"id":i["id"],"concept":"lifecycle","object":{"tf_band":i["band"][3],"lo":i["band"][0],"hi":i["band"][1]},"window":i["win"],"verdict":i["verdict"],"known_at":i["known"],"reason":i["reason"],"owner_check":"pending"} for i in items]
json.dump({"key_version":"batch1-v3","rule":"BREAK-2: broken = close beyond AND price then closes beyond the next swing (nearest prior confirmed swing of the object's own TF on the far side; a 15M close; a wick only = sweep of that swing); known at that bar. Back inside before that = retest/sweep, object alive. Beyond but not reached = beyond-not-broken (no flip entry). Same test for broken-back => dead; no second flip. Fresh ground (no prior swing beyond): broken when a new own-TF swing forms beyond and price passes it.","items":out},open('/home/claude/ak/answer_key_batch1v3.json','w'),indent=1)
