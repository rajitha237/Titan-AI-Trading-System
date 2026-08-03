import numpy as np
import pandas as pd
import ta

def generate_features(candles:pd.DataFrame)->pd.DataFrame:
    f=candles.copy()
    if f.empty:return f
    for col in ('open','high','low','close','volume'):f[col]=pd.to_numeric(f[col],errors='coerce')
    c,h,l,v=f['close'],f['high'],f['low'],f['volume']
    f['ema20']=ta.trend.EMAIndicator(c,20).ema_indicator(); f['ema50']=ta.trend.EMAIndicator(c,50).ema_indicator(); f['ema200']=ta.trend.EMAIndicator(c,200).ema_indicator()
    f['rsi14']=ta.momentum.RSIIndicator(c,14).rsi(); macd=ta.trend.MACD(c); f['macd']=macd.macd(); f['macd_signal']=macd.macd_signal(); f['macd_hist']=macd.macd_diff()
    f['atr14']=ta.volatility.AverageTrueRange(h,l,c,14).average_true_range(); f['atr_percent']=f['atr14']/c.replace(0,np.nan)*100
    typical=(h+l+c)/3; f['vwap']=(typical*v).cumsum()/v.cumsum().replace(0,np.nan)
    f['volume_sma20']=v.rolling(20).mean(); f['volume_ratio']=v/f['volume_sma20'].replace(0,np.nan)
    f['return_1']=c.pct_change(); f['volatility_20']=f['return_1'].rolling(20).std()*100
    taker=pd.to_numeric(f.get('taker_buy_base',pd.Series(index=f.index,dtype=float)),errors='coerce')
    f['taker_buy_ratio']=taker/v.replace(0,np.nan); f['order_flow_delta_proxy']=f['taker_buy_ratio']*2-1
    f['rolling_high_20']=h.shift(1).rolling(20).max(); f['rolling_low_20']=l.shift(1).rolling(20).min(); f['bullish_bos']=c>f['rolling_high_20']; f['bearish_bos']=c<f['rolling_low_20']
    f['trend_regime']=np.select([(f['ema20']>f['ema50'])&(f['ema50']>f['ema200']),(f['ema20']<f['ema50'])&(f['ema50']<f['ema200'])],['BULLISH','BEARISH'],default='RANGING')
    f['volatility_regime']=np.where(f['atr_percent']>f['atr_percent'].rolling(100).median(),'HIGH','LOW')
    return f
