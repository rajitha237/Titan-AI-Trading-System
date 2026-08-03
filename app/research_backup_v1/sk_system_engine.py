import pandas as pd

def calculate_sk_features(frame:pd.DataFrame,*,swing_window:int=5)->pd.DataFrame:
    f=frame.copy(); high,low,close=f['high'],f['low'],f['close']
    f['swing_high']=high.eq(high.rolling(swing_window*2+1,center=True).max()); f['swing_low']=low.eq(low.rolling(swing_window*2+1,center=True).min())
    ch=high.where(f['swing_high']).ffill().shift(swing_window); cl=low.where(f['swing_low']).ffill().shift(swing_window); rng=(ch-cl).abs()
    b618=ch-rng*.618; b786=ch-rng*.786; s618=cl+rng*.618; s786=cl+rng*.786
    f['sk_bull_golden_pocket']=close.between(pd.concat([b618,b786],axis=1).min(axis=1),pd.concat([b618,b786],axis=1).max(axis=1))&(f['trend_regime']=='BULLISH')
    f['sk_bear_golden_pocket']=close.between(pd.concat([s618,s786],axis=1).min(axis=1),pd.concat([s618,s786],axis=1).max(axis=1))&(f['trend_regime']=='BEARISH')
    f['sk_bull_invalidation']=cl; f['sk_bear_invalidation']=ch
    return f
