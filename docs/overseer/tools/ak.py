import pandas as pd, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
D="/home/claude/ak/data/"
def load(tf):
    if tf in ("15m","5m"):
        df=pd.read_csv(D+f"BANKNIFTY_{tf}.csv.gz")
        df["ts"]=pd.to_datetime(df.timestamp.str[:19])
        return df.set_index("ts")[["open","high","low","close"]]
    if tf=="1H":
        m=load("15m"); m=m.copy()
        day=m.index.normalize(); mins=(m.index-day).total_seconds()/60-555
        b=day+pd.to_timedelta(555+(mins//60)*60,unit="m")
        return m.groupby(b).agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"))
    if tf=="D":
        d=pd.read_csv(D+"BANKNIFTY_D.csv.gz"); d["ts"]=pd.to_datetime(d.iloc[:,0]); d=d.set_index("ts")[["open","high","low","close"]]
        m=load("15m"); md=m.groupby(m.index.normalize()).agg(open=("open","first"),high=("high","max"),low=("low","min"),close=("close","last"))
        d=d[d.index<md.index[0]]
        return pd.concat([d,md])
def rsi(c,n=14):
    d=c.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean(); dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/dn)
def plot(df,start,end,fn,title="",bands=(),marks=(),vlines=(),hlines=(),with_rsi=False,figsize=(13,6.5),texts=()):
    """bands: (lo,hi,color,label,x0ts or None); marks:(ts,price,text,color,'^'/'v'); vlines:(ts,color,label)"""
    full=df; r=rsi(full.close) if with_rsi else None
    s=df.loc[start:end]; x=np.arange(len(s)); idx={t:i for i,t in enumerate(s.index)}
    def xi(t):
        t=pd.Timestamp(t); 
        if t in idx: return idx[t]
        pos=s.index.searchsorted(t,side='right')-1; return max(0,min(pos,len(s)-1))
    if with_rsi: fig,(ax,ax2)=plt.subplots(2,1,figsize=figsize,sharex=True,gridspec_kw={"height_ratios":[3.2,1]})
    else: fig,ax=plt.subplots(figsize=figsize)
    for i,(t,row) in enumerate(s.iterrows()):
        c="#1a9850" if row.close>=row.open else "#d73027"
        ax.plot([i,i],[row.low,row.high],color="#333",lw=0.7,zorder=2)
        ax.add_patch(Rectangle((i-0.33,min(row.open,row.close)),0.66,max(abs(row.close-row.open),0.5),color=c,zorder=3))
    for b in bands:
        lo,hi,col,lab=b[:4]; x0=xi(b[4]) if len(b)>4 and b[4] is not None else 0
        ax.add_patch(Rectangle((x0-0.5,lo),len(s)-x0,hi-lo,color=col,alpha=0.18,zorder=1))
        ax.text(len(s)-0.5,hi,f" {lab}",color=col,fontsize=8,va="bottom",ha="right",weight="bold")
    for h in hlines:
        y,col,lab=h; ax.axhline(y,color=col,lw=0.8,ls="--"); ax.text(0,y,f"{lab}",color=col,fontsize=7.5,va="bottom")
    for v in vlines:
        t,col,lab=v; i=xi(t); ax.axvline(i,color=col,lw=1,ls=":"); ax.text(i,ax.get_ylim()[1],lab,color=col,fontsize=7.5,rotation=90,va="top",ha="right")
    rng=s.high.max()-s.low.min()
    for m in marks:
        t,p,txt,col,sh=m; i=xi(t)
        off=rng*0.07*(1 if sh=="v" else -1)
        ax.annotate(txt,(i,p),(i,p+off),color=col,fontsize=7.5,ha="center",va=("bottom" if sh=="v" else "top"),weight="bold",arrowprops=dict(arrowstyle="->",color=col,lw=0.9),bbox=dict(boxstyle="round,pad=0.15",fc="white",ec="none",alpha=0.8))
    for tx in texts: ax.text(0.01,0.98-0.04*texts.index(tx),tx,transform=ax.transAxes,fontsize=8,va="top",color="#222")
    ax.set_xlim(-1,len(s)); ax.set_ylim(s.low.min()-rng*0.22,s.high.max()+rng*0.22)
    n=max(1,len(s)//14); ticks=x[::n]
    lab=[t.strftime("%d-%b" if (s.index[1]-s.index[0])>=pd.Timedelta("1D") else "%d-%b %H:%M") for t in s.index[::n]]
    tgt=ax2 if with_rsi else ax
    tgt.set_xticks(ticks); tgt.set_xticklabels(lab,rotation=35,fontsize=7.5,ha="right")
    ax.grid(alpha=0.25); ax.set_title(title,fontsize=10,loc="left"); ax.tick_params(labelsize=8)
    if with_rsi:
        rr=r.loc[start:end].values; ax2.plot(x,rr,color="#5e3c99",lw=1); ax2.axhline(70,color="#aaa",lw=.6); ax2.axhline(30,color="#aaa",lw=.6); ax2.set_ylabel("RSI14",fontsize=8); ax2.grid(alpha=.25); ax2.tick_params(labelsize=8)
    fig.tight_layout(); fig.savefig(fn,dpi=88); plt.close(fig); return fn
def swings(df,k=2):
    """confirmed fractal pivots: pivot at i known at i+k"""
    H,L=df.high.values,df.low.values; out=[]
    for i in range(k,len(df)-k):
        if H[i]==max(H[i-k:i+k+1]) and H[i]>max(H[i-k:i]): out.append((df.index[i],"H",H[i],df.index[i+k]))
        if L[i]==min(L[i-k:i+k+1]) and L[i]<min(L[i-k:i]): out.append((df.index[i],"L",L[i],df.index[i+k]))
    return out
