"""Internal Self-Learning v2 metrics snapshot."""
from __future__ import annotations
from app.learning.experience_store import list_experiences
from app.learning.learning_statistics import group_metrics, performance_metrics

def build_self_learning_dashboard(*, limit: int = 10000) -> dict:
    experiences = list_experiences(limit=limit)
    return {
        "status": "success",
        "version": "self_learning_v2",
        "overall": performance_metrics(experiences),
        "by_symbol": group_metrics(experiences, lambda item: item.get("symbol")),
        "by_strategy": group_metrics(experiences, lambda item: item.get("strategy")),
        "by_regime": group_metrics(experiences, lambda item: item.get("market_regime")),
        "by_session": group_metrics(experiences, lambda item: item.get("session")),
    }
