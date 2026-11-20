"""Stand-in for Trade's `signals` (a TRADE-ONLY module): only `compute_atr`, which engine_service (trade_monitor's ATR helper) uses,
verbatim (Trade signals.py L778-794)."""
import pandas as pd

__srv2_io__ = True


def compute_atr(df, period=14):
    """
    दिलेल्या OHLC डेटाच्या शेवटच्या bar साठी Average True Range (ATR) काढणे — Trailing SL साठी वापरला जातो.
    Wilder's Smoothing Method वापरते (TradingView/जवळपास सर्व platforms हीच वापरतात) — आधी इथे फक्त
    शेवटच्या period bars ची साधी सरासरी होती (RSI मध्ये सापडलेल्याच bug चा प्रकार), जी प्रत्यक्ष
    TradingView च्या ATR पेक्षा वेगळी यायची — खऱ्या पैशाच्या Trailing SL वर याचा थेट परिणाम व्हायचा.
    पुरेसा डेटा (किमान period+1 bars) नसेल तर None परत करतो.
    """
    n = len(df)
    if n < period + 1:
        return None
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    prev_close.iloc[0] = df["open"].iloc[0]  # आधीच्याच convention नुसार — पहिल्या bar साठी prev_close=open
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr_series = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    return float(atr_series.iloc[-1])
