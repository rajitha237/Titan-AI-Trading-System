from math import inf

def summarize_backtest(backtest:dict)->dict:
    trades=backtest.get('trades',[]); pnls=[float(t.get('net_pnl',0)) for t in trades]; rs=[float(t.get('pnl_r',0)) for t in trades]; wins=[x for x in pnls if x>0]; losses=[x for x in pnls if x<0]
    curve=[float(x) for x in backtest.get('equity_curve',[])]; peak=curve[0] if curve else 0; max_dd=0
    for value in curve:
        peak=max(peak,value); max_dd=max(max_dd,((peak-value)/peak*100) if peak else 0)
    total=len(trades); gp=sum(wins); gl=abs(sum(losses)); initial=float(backtest.get('initial_balance',1)); final=float(backtest.get('final_balance',0))
    return {'symbol':backtest.get('symbol'),'timeframe':backtest.get('timeframe'),'trade_count':total,'wins':len(wins),'losses':len(losses),'win_rate_percent':len(wins)/total*100 if total else 0,'profit_factor':gp/gl if gl>0 else (inf if gp>0 else 0),'net_pnl':sum(pnls),'return_percent':(final/initial-1)*100 if initial else 0,'expectancy_r':sum(rs)/total if total else 0,'average_win':sum(wins)/len(wins) if wins else 0,'average_loss':sum(losses)/len(losses) if losses else 0,'maximum_drawdown_percent':max_dd,'initial_balance':initial,'final_balance':final}
