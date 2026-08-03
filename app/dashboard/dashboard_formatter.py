"""Compact dashboard text formatter v31."""
from __future__ import annotations
from app.dashboard.dashboard_models import safe_dict


def format_dashboard_summary(dashboard: dict | None) -> str:
    dashboard = safe_dict(dashboard)
    system = safe_dict(safe_dict(dashboard.get("system")).get("data"))
    execution = safe_dict(dashboard.get("execution"))
    execution_data = safe_dict(execution.get("data"))
    return (
        f"TitanAI health={dashboard.get('overall_health', 'unknown')} "
        f"mode={system.get('mode', 'unknown')} "
        f"exchange={safe_dict(dashboard.get('exchange')).get('status', 'unknown')} "
        f"watchdog={safe_dict(dashboard.get('watchdog')).get('status', 'unknown')} "
        f"execution={execution.get('status', 'unknown')} "
        f"submitted={execution_data.get('submitted', False)}"
    )
