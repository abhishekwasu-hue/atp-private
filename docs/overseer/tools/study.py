import sys;sys.path.insert(0,'/home/claude/ak/lib');import ak,pandas as pd
def events(tf,start,end,lo,hi,k=2):
    df=ak.load(tf).loc[start:end]
    out=[]
    for t,r in df.iterrows():
        if r.close<lo: out.append((t,"close BELOW",round(r.close,1)))
        elif r.close>hi: out.append((t,"close ABOVE",round(r.close,1)))
        elif r.low<lo: out.append((t,"wick below",round(r.low,1)))
        elif r.high>hi: out.append((t,"wick above",round(r.high,1)))
    sw=[s for s in ak.swings(df,k)]
    return out,sw
def lifecycle(tf,start,end,lo,hi,k=2,brk="down"):
    """brk='down': support broken downward. Report closes beyond, counter-swings beyond (swing HIGH with high<lo), confirm ts, returns inside."""
    df=ak.load(tf).loc[start:end]; sw=ak.swings(df,k); rows=[]
    for t,r in df.iterrows():
        if brk=="down" and r.close<lo: rows.append((str(t),"close<lo",round(r.close,1)))
        if brk=="up" and r.close>hi: rows.append((str(t),"close>hi",round(r.close,1)))
    cs=[(str(a),typ,round(p,1),str(c)) for a,typ,p,c in sw if (brk=="down" and typ=="H" and p<lo) or (brk=="up" and typ=="L" and p>hi)]
    ext=[(str(a),typ,round(p,1),str(c)) for a,typ,p,c in sw if (brk=="down" and typ=="L" and p<lo) or (brk=="up" and typ=="H" and p>hi)]
    return rows,cs,ext
