"""Conservative LONG/SHORT/NO-TRADE probability allocator."""
from __future__ import annotations

def calculate_institutional_probabilities(*, ai_score:dict, regime:dict, strategy:dict, research:dict)->dict:
    raw=float(ai_score.get("score",50) or 50)
    direction=str(ai_score.get("signal") or ("BUY" if raw>=50 else "SELL")).upper()
    bull=max(0.0,min(100.0,raw)); bear=100.0-bull
    if regime.get("direction")=="BUY": bull += regime.get("confidence",0)*0.18
    elif regime.get("direction")=="SELL": bear += regime.get("confidence",0)*0.18
    if strategy.get("eligible"): 
        if strategy.get("direction")=="BUY": bull += strategy.get("strategy_score",0)*0.10
        elif strategy.get("direction")=="SELL": bear += strategy.get("strategy_score",0)*0.10
    research_score=float(research.get("score",50))
    research_delta=(research_score-50)*0.35
    if regime.get("direction")=="BUY": bull += research_delta
    elif regime.get("direction")=="SELL": bear += research_delta
    no_trade=20.0
    if not regime.get("tradeable"): no_trade += 35
    if not strategy.get("eligible"): no_trade += 25
    if research.get("hard_block"): no_trade += 50
    if research.get("sample_size",0)<8: no_trade += 10
    bull=max(0.0,bull); bear=max(0.0,bear); no_trade=max(0.0,no_trade)
    total=bull+bear+no_trade or 1.0
    long_p=bull/total*100; short_p=bear/total*100; no_p=no_trade/total*100
    dominant=max(("BUY",long_p),("SELL",short_p),("NO_TRADE",no_p),key=lambda x:x[1])
    return {"status":"ready","long_probability":round(long_p,2),"short_probability":round(short_p,2),
            "no_trade_probability":round(no_p,2),"dominant_outcome":dominant[0],"dominant_probability":round(dominant[1],2),
            "institutional_threshold_passed":dominant[0] in {"BUY","SELL"} and dominant[1]>=55 and no_p<35}
