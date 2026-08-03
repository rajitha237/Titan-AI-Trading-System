"""Normalize historical research evidence for live decision use."""
from __future__ import annotations
from typing import Any

def _f(v:Any,d=0.0):
    try:return float(v)
    except (TypeError,ValueError):return d

def evaluate_research_confluence(historical_edge:dict|None)->dict:
    edge=historical_edge or {}
    decision=str(edge.get("decision","NEUTRAL")).upper()
    report=edge.get("report") or {}
    test=report.get("test_report") or report
    similarity=report.get("pattern_similarity") or {}
    probability=report.get("probability") or {}
    sample=int(edge.get("sample_size") or test.get("trade_count") or 0)
    expectancy=_f(test.get("expectancy_r")); pf=_f(test.get("profit_factor")); drawdown=_f(test.get("maximum_drawdown_percent"))
    lower=_f(probability.get("confidence_lower_bound_percent")); sim_prob=_f(similarity.get("positive_probability_percent"),50.0)
    sim_return=_f(similarity.get("average_forward_return_percent"))
    score=50.0; reasons=[]; hard_block=False
    if decision=="SUPPORT": score += 18; reasons.append("Research engine supports the setup")
    elif decision=="OPPOSE": score -= 25; reasons.append("Unseen-test evidence opposes the setup"); hard_block = sample >= 8
    elif decision=="WATCH": reasons.append("Research evidence is mixed")
    else: reasons.append("No approved historical edge is available")
    if expectancy>0: score += min(12,expectancy*18)
    elif expectancy<0: score -= min(15,abs(expectancy)*18)
    if pf>=1.25: score += 8
    elif 0<pf<0.9: score -= 10
    if lower>=50: score += 7
    if sim_prob>=55 and sim_return>0: score += 7
    elif sim_prob<45 and sim_return<0: score -= 7
    if drawdown>20: score -= 10
    if sample<8: score=min(score,55); reasons.append("Historical sample is below institutional minimum")
    score=max(0.0,min(100.0,score))
    return {"status":"ready","decision":decision,"score":round(score,2),"sample_size":sample,
            "expectancy_r":expectancy,"profit_factor":pf,"maximum_drawdown_percent":drawdown,
            "probability_lower_bound_percent":lower,"similarity_probability_percent":sim_prob,
            "similarity_average_return_percent":sim_return,"hard_block":hard_block,"reasons":reasons}
