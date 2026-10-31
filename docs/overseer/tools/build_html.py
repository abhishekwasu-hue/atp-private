import sys,json,base64;sys.path.insert(0,'/home/claude/ak/lib');from mr1 import MR
items=json.load(open('/home/claude/ak/batch1.json'))
css="""body{font-family:system-ui,'Noto Sans Devanagari',sans-serif;max-width:1180px;margin:auto;padding:16px;background:#f7f7f5;color:#222}
.it{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px;margin:18px 0}
h1{font-size:22px}h2{font-size:17px;margin:4px 0}.v{font-weight:700;color:#7a1f1f}.k{color:#555;font-size:14px}
img{width:100%;border:1px solid #eee;border-radius:6px}.r{font-size:15px;line-height:1.55}.en{font-size:13px;color:#555}
.ans label{margin-right:18px;font-size:16px}textarea{width:100%;height:44px}.rule{background:#fff8e1;border:1px solid #f0d58c;padding:12px;border-radius:8px}
button{font-size:15px;padding:8px 14px}"""
h=[f"<!doctype html><html lang=mr><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Answer key batch 1</title><style>{css}</style></head><body>",
"<h1>Answer key · Batch 1 — Lifecycle (8 items)</h1>",
"""<div class=rule><b>मी वापरलेला BREAK-1 (b) अर्थ (हाच तपासा):</b><br>
• <b>BROKEN</b> = band पलीकडे close <b>आणि</b> पलीकडे एक <b>pullback swing</b> (support साठी खाली swing high, resistance साठी वर swing low) तयार होऊन तो पलीकडेच राहतो. तो swing confirm झाला तो bar = 'कळलेला' bar.<br>
• पलीकडचं <b>टोक</b> (फक्त low / high) एकटं broken नाही — X01 (11 Sep) हाच पुरावा ⇒ <b>SWEEP</b>, object जिवंत.<br>
• Flip झालेला object परत तोडायला (broken back ⇒ DEAD) तोच नियम. Dead नंतर दुसरा flip नाही.<br>
• Swing = 15M चा confirm swing (2 bars दोन्ही बाजूला). Band = reader चाच घेतला; band बरोबर आहे का हा प्रश्न पुढच्या batch मध्ये.</div>"""]
for it in items:
    v,kn,rs=MR[it['id']]
    b=base64.b64encode(open(it['chart'],'rb').read()).decode()
    h.append(f"""<div class=it id={it['id']}><h2>{it['id']} · {it['title']}</h2><div class=v>निकाल: {v}</div><div class=k>{kn}</div>
<img src='data:image/png;base64,{b}'><p class=r>{rs}</p>
<div class=ans><label><input type=radio name={it['id']} value=ok> ✓ बरोबर</label><label><input type=radio name={it['id']} value=no> ✗ चूक</label></div>
<textarea id=c_{it['id']} placeholder='चूक असेल तर बरोबर काय (फक्त तिथेच लिहा)'></textarea></div>""")
h.append("""<button onclick="let o={};document.querySelectorAll('.it').forEach(d=>{let id=d.id,r=d.querySelector('input:checked');o[id]={ans:r?r.value:'',note:document.getElementById('c_'+id).value}});let t=JSON.stringify(o);navigator.clipboard.writeText(t).then(()=>alert('उत्तरं copy झाली — chat मध्ये paste करा'),()=>prompt('copy करा:',t))">उत्तरं copy करा</button></body></html>""")
open('/home/claude/ak/ANSWER_KEY_BATCH1.html','w').write("".join(h))
# JSON for session (English)
out=[{"id":i["id"],"concept":"lifecycle","object":{"tf_band":i["band"][3],"lo":i["band"][0],"hi":i["band"][1]},"window":i["win"],"verdict":i["verdict"],"known_at":i["known"],"reason":i["reason"],"owner_check":"pending"} for i in items]
json.dump({"key_version":"batch1-draft","rule":"BREAK-1 (b): broken = close beyond AND a pullback swing (swing high below for support / swing low above for resistance) confirmed on the far side while price stays beyond; the far-side extreme alone is a sweep. Same test for broken-back => dead; no second flip. Swing = confirmed 15M swing (2 bars each side) — the swing size is a setting.","items":out},open('/home/claude/ak/answer_key_batch1.json','w'),indent=1)
