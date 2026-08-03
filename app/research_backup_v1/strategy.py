import numpy as np
import pandas as pd

def build_strategy_signals(features:pd.DataFrame,*,minimum_score:float=70.0)->pd.DataFrame:
    f=features.copy()
    buy=(f['trend_regime']=='BULLISH').astype(int)*20+(f['close']>f['vwap']).astype(int)*10+(f['macd_hist']>0).astype(int)*15+f['rsi14'].between(42,68).astype(int)*10+(f['volume_ratio']>1).astype(int)*10+(f['order_flow_delta_proxy']>0).astype(int)*10+f['bullish_bos'].astype(int)*10+f['sk_bull_golden_pocket'].astype(int)*15
    sell=(f['trend_regime']=='BEARISH').astype(int)*20+(f['close']<f['vwap']).astype(int)*10+(f['macd_hist']<0).astype(int)*15+f['rsi14'].between(32,58).astype(int)*10+(f['volume_ratio']>1).astype(int)*10+(f['order_flow_delta_proxy']<0).astype(int)*10+f['bearish_bos'].astype(int)*10+f['sk_bear_golden_pocket'].astype(int)*15
    f['research_buy_score']=buy; f['research_sell_score']=sell; f['research_score']=np.maximum(buy,sell)
    f['research_direction']=np.select([(buy>=minimum_score)&(buy>sell),(sell>=minimum_score)&(sell>buy)],['BUY','SELL'],default='HOLD')
    return f
