from dataclasses import asdict,dataclass
import pandas as pd

@dataclass
class Trade:
    symbol:str; timeframe:str; side:str; signal_time:str; entry_time:str; exit_time:str; entry_price:float; exit_price:float; stop_price:float; target_price:float; quantity:float; gross_pnl:float; fees:float; net_pnl:float; pnl_r:float; exit_reason:str; score:float

def run_backtest(frame:pd.DataFrame,*,symbol:str,timeframe:str,initial_balance:float=1000.0,risk_per_trade_percent:float=1.0,fee_rate:float=.0004,slippage_rate:float=.0002,stop_atr_multiple:float=1.2,reward_risk:float=1.5,maximum_holding_bars:int=48)->dict:
    data=frame.dropna().reset_index(drop=True); balance=float(initial_balance); curve=[balance]; trades=[]; i=0
    while i<len(data)-2:
        row=data.iloc[i]; side=str(row.get('research_direction','HOLD'))
        if side not in {'BUY','SELL'}: i+=1; continue
        entry_row=data.iloc[i+1]; raw=float(entry_row['open']); entry=raw*(1+slippage_rate if side=='BUY' else 1-slippage_rate); atr=float(row['atr14'])
        if atr<=0:i+=1;continue
        dist=atr*stop_atr_multiple; stop=entry-dist if side=='BUY' else entry+dist; target=entry+dist*reward_risk if side=='BUY' else entry-dist*reward_risk
        risk=balance*risk_per_trade_percent/100; qty=risk/dist; exit_price=float(entry_row['close']); reason='TIME_EXIT'; exit_i=min(i+1+maximum_holding_bars,len(data)-1)
        for j in range(i+1,exit_i+1):
            c=data.iloc[j]; high=float(c['high']); low=float(c['low'])
            if side=='BUY':
                if low<=stop: exit_price=stop*(1-slippage_rate); reason='STOP_LOSS'; exit_i=j; break
                if high>=target: exit_price=target*(1-slippage_rate); reason='TAKE_PROFIT'; exit_i=j; break
            else:
                if high>=stop: exit_price=stop*(1+slippage_rate); reason='STOP_LOSS'; exit_i=j; break
                if low<=target: exit_price=target*(1+slippage_rate); reason='TAKE_PROFIT'; exit_i=j; break
        else: exit_price=float(data.iloc[exit_i]['close'])
        direction=1 if side=='BUY' else -1; gross=(exit_price-entry)*qty*direction; fees=(entry*qty+exit_price*qty)*fee_rate; net=gross-fees; balance+=net; curve.append(balance)
        trades.append(Trade(symbol,timeframe,side,str(row['open_time']),str(entry_row['open_time']),str(data.iloc[exit_i]['close_time']),entry,exit_price,stop,target,qty,gross,fees,net,net/risk if risk else 0,reason,float(row['research_score'])))
        i=exit_i+1
    return {'symbol':symbol,'timeframe':timeframe,'initial_balance':initial_balance,'final_balance':balance,'equity_curve':curve,'trades':[asdict(t) for t in trades]}
