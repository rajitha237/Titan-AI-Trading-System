"""Combine live, regime, strategy, research, and probability evidence."""
from __future__ import annotations

def build_adaptive_score(*, ai_score:dict, regime:dict, strategy:dict, research:dict, probabilities:dict)->dict:
    raw=float(ai_score.get("score",50) or 50)
    direction="BUY" if raw>=50 else "SELL"
    directional_raw=raw if direction=="BUY" else 100-raw
    regime_component=float(regime.get("confidence",0)) if regime.get("direction")==direction else 0.0
    strategy_component=float(strategy.get("strategy_score",0)) if strategy.get("direction")==direction else 0.0
    research_component=float(research.get("score",50))
    probability_component=float(probabilities.get("long_probability" if direction=="BUY" else "short_probability",0))
    final=(directional_raw*0.45 + regime_component*0.15 + strategy_component*0.12 + research_component*0.13 + probability_component*0.15)
    blocks=[]
    if research.get("hard_block"): blocks.append("Historical unseen-test evidence strongly opposes this setup")
    if not regime.get("tradeable"): blocks.append("Live market regime is not tradeable")
    if strategy.get("selected_strategy")=="NO_TRADE": blocks.append("No institutional strategy matches the current regime")
    if not probabilities.get("institutional_threshold_passed"): blocks.append("Institutional probability threshold did not pass")
    final=max(0.0,min(100.0,final))
    action="REJECT" if blocks else ("TRADE" if final>=82 else "SMALL_TRADE" if final>=75 else "WATCH")
    allowed=action in {"TRADE","SMALL_TRADE"}
    adjusted=dict(ai_score)
    adjusted["raw_score"]=raw
    adjusted["score"]=round(final if direction=="BUY" else 100-final,2)
    adjusted["institutional_directional_score"]=round(final,2)
    adjusted["signal"]=direction if allowed else "HOLD"
    adjusted["institutional_action"]=action
    adjusted["institutional_block_reasons"]=blocks
    adjusted["institutional_breakdown"]={"live":round(directional_raw,2),"regime":round(regime_component,2),"strategy":round(strategy_component,2),"research":round(research_component,2),"probability":round(probability_component,2)}
    return {"status":"ready","direction":direction,"final_score":round(final,2),"action":action,"allowed":allowed,"block_reasons":blocks,"adjusted_ai_score":adjusted}
