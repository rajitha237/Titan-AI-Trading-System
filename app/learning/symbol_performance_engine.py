"""TitanAI Self-Learning v2 symbol performance engine."""
from __future__ import annotations
from app.learning.experience_store import list_experiences
from app.learning.learning_statistics import bounded_performance_adjustment, performance_metrics

def evaluate_symbol_performance(symbol: str, *, limit: int = 10000) -> dict:
    key = str(symbol or "UNKNOWN").upper()
    experiences = list_experiences(symbol=key, limit=limit)
    metrics = performance_metrics(experiences)
    evidence = bounded_performance_adjustment(metrics)
    return {"status": "success", "dimension": "symbol", "key": key, "metrics": metrics, **evidence}
