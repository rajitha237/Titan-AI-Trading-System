"""TitanAI Self-Learning v2 market_regime performance engine."""
from __future__ import annotations
from app.learning.experience_store import list_experiences
from app.learning.learning_statistics import bounded_performance_adjustment, performance_metrics

def evaluate_market_regime_performance(market_regime: str, *, limit: int = 10000) -> dict:
    key = str(market_regime or "UNKNOWN").upper()
    experiences = list_experiences(market_regime=key, limit=limit)
    metrics = performance_metrics(experiences)
    evidence = bounded_performance_adjustment(metrics)
    return {"status": "success", "dimension": "market_regime", "key": key, "metrics": metrics, **evidence}
