"""TitanAI Self-Learning v2 strategy performance engine."""
from __future__ import annotations
from app.learning.experience_store import list_experiences
from app.learning.learning_statistics import bounded_performance_adjustment, performance_metrics

def evaluate_strategy_performance(strategy: str, *, limit: int = 10000) -> dict:
    key = str(strategy or "UNKNOWN").upper()
    experiences = list_experiences(strategy=key, limit=limit)
    metrics = performance_metrics(experiences)
    evidence = bounded_performance_adjustment(metrics)
    return {"status": "success", "dimension": "strategy", "key": key, "metrics": metrics, **evidence}
